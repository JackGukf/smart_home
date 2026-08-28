"""A switch that gets a new DHCP lease should be found again, not written off.

Switches are addressed by IP, so a lease change looks exactly like a dead
device: it stops answering. These tests pin the recovery path - repeated
failures trigger a MAC-keyed broadcast scan, and the new address is persisted.
"""

import asyncio
import json
from pathlib import Path

import pytest

from src.python import web_app as web_app_module
from src.python.tplink_discovery import apply_discovered_hosts, normalize_mac
from src.python.tplink_switch import SwitchState
from src.python.web_app import (
    SWITCH_REDISCOVER_AFTER_FAILURES,
    _device_cards,
    create_app,
)

OLD_HOST = "192.168.0.208"
NEW_HOST = "192.168.0.207"
MAC = "1C:61:B4:F9:B1:1C"


def _write_discovery(path: Path, host: str = OLD_HOST, mac: str | None = MAC) -> None:
    switch = {
        "alias": "North bedroom night light",
        "device_type": "DeviceType.Plug",
        "host": host,
        "is_on": False,
        "model": "HS103",
        "name": "North bedroom night light",
    }
    if mac is not None:
        switch["mac"] = mac
    path.write_text(json.dumps({"count": 1, "switches": [switch]}), encoding="utf-8")


class MovedSwitchController:
    """Answers only on `reachable`; anything else times out like a dead host."""

    def __init__(self, reachable: str) -> None:
        self.reachable = reachable
        self.forgotten: list[str] = []

    async def status(self, switch) -> SwitchState:
        if switch.host != self.reachable:
            await asyncio.sleep(3600)
        return SwitchState(
            name=switch.name, host=switch.host, is_on=True,
            alias=switch.name, model=switch.model,
        )

    async def forget(self, host: str) -> None:
        self.forgotten.append(host)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("1c:61:b4:f9:b1:1c", MAC),
        ("1C-61-B4-F9-B1-1C", MAC),
        ("1c61b4f9b11c", MAC),
        ("not-a-mac", None),
        (None, None),
        ("", None),
    ],
)
def test_normalize_mac(raw, expected) -> None:
    assert normalize_mac(raw) == expected


def test_apply_discovered_hosts_only_moves_matched_macs() -> None:
    switches = [
        {"name": "Moved", "host": OLD_HOST, "mac": MAC},
        {"name": "Still put", "host": "192.168.0.51", "mac": "00:5F:67:B2:48:6F"},
        {"name": "Offline", "host": "192.168.0.99", "mac": "AA:BB:CC:DD:EE:FF"},
        {"name": "No MAC recorded", "host": "192.168.0.98"},
    ]

    moves = apply_discovered_hosts(
        switches, {MAC: NEW_HOST, "00:5F:67:B2:48:6F": "192.168.0.51"}
    )

    assert moves == [("Moved", OLD_HOST, NEW_HOST)]
    # A switch that did not answer the broadcast keeps its address: it may just
    # be powered off, and must never be pointed at another device.
    assert [s["host"] for s in switches] == [
        NEW_HOST, "192.168.0.51", "192.168.0.99", "192.168.0.98",
    ]


def test_repeated_failures_rediscover_and_persist_the_new_address(
    tmp_path: Path, monkeypatch
) -> None:
    discovery = tmp_path / "tplink_switches.json"
    _write_discovery(discovery)
    controller = MovedSwitchController(reachable=NEW_HOST)
    app = create_app(discovery_path=discovery, controller=controller)

    scans = []

    async def fake_scan(timeout: int = 8) -> dict[str, str]:
        scans.append(timeout)
        return {MAC: NEW_HOST}

    monkeypatch.setattr(web_app_module, "discover_hosts_by_mac", fake_scan)
    monkeypatch.setattr(web_app_module, "SWITCH_STATUS_TIMEOUT", 0.05)

    async def scenario() -> list[dict]:
        for _ in range(SWITCH_REDISCOVER_AFTER_FAILURES):
            await _device_cards(app)
        # The scan runs in the background so polling never blocks on it.
        await app.state.rediscovery["task"]
        return await _device_cards(app)

    cards = asyncio.run(scenario())

    assert scans, "repeated failures did not trigger a rediscovery scan"
    # The switch is reachable again at its new address...
    assert cards[0]["host"] == NEW_HOST
    assert cards[0]["is_on"] is True
    # ...and the move is on disk, so a restart does not go back to the old one.
    stored = json.loads(discovery.read_text(encoding="utf-8"))["switches"][0]
    assert stored["host"] == NEW_HOST
    assert stored["mac"] == MAC
    assert stored["alias"] == "North bedroom night light"


def test_rediscovery_is_rate_limited(tmp_path: Path, monkeypatch) -> None:
    discovery = tmp_path / "tplink_switches.json"
    _write_discovery(discovery)
    app = create_app(discovery_path=discovery, controller=MovedSwitchController(reachable="none"))

    scans = []

    async def fake_scan(timeout: int = 8) -> dict[str, str]:
        scans.append(timeout)
        return {}

    monkeypatch.setattr(web_app_module, "discover_hosts_by_mac", fake_scan)
    monkeypatch.setattr(web_app_module, "SWITCH_STATUS_TIMEOUT", 0.05)

    async def scenario() -> None:
        for _ in range(SWITCH_REDISCOVER_AFTER_FAILURES * 3):
            await _device_cards(app)
            task = app.state.rediscovery.get("task")
            if task is not None:
                await task

    asyncio.run(scenario())

    # A switch that is genuinely off keeps failing; without the floor every
    # poll cycle would start another broadcast scan.
    assert len(scans) == 1, f"expected one scan, got {len(scans)}"


def test_rediscovery_is_skipped_when_no_macs_are_recorded(tmp_path: Path, monkeypatch) -> None:
    discovery = tmp_path / "tplink_switches.json"
    _write_discovery(discovery, mac=None)
    app = create_app(discovery_path=discovery, controller=MovedSwitchController(reachable="none"))

    scans = []

    async def fake_scan(timeout: int = 8) -> dict[str, str]:
        scans.append(timeout)
        return {}

    monkeypatch.setattr(web_app_module, "discover_hosts_by_mac", fake_scan)
    monkeypatch.setattr(web_app_module, "SWITCH_STATUS_TIMEOUT", 0.05)

    async def scenario() -> None:
        for _ in range(SWITCH_REDISCOVER_AFTER_FAILURES):
            await _device_cards(app)
        task = app.state.rediscovery.get("task")
        if task is not None:
            await task

    asyncio.run(scenario())

    # Nothing to match on, so scanning could only guess. It must not.
    assert scans == []
    assert json.loads(discovery.read_text(encoding="utf-8"))["switches"][0]["host"] == OLD_HOST
