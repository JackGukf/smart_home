"""Guards for the dashboard's first-paint cost.

A single unreachable switch used to add ~5s to every page load: switches were
polled one at a time with python-kasa's full default timeout. These tests pin
the three fixes - concurrent polling, a per-switch cap, and a cached device
list - so the regression cannot creep back in.
"""

import asyncio
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.python.tplink_switch import SwitchState
from src.python.web_app import SWITCH_STATUS_TIMEOUT, create_app


def _write_discovery(path: Path) -> None:
    path.write_text(
        """
{
  "count": 3,
  "switches": [
    {"alias": "One", "device_type": "DeviceType.WallSwitch", "host": "10.0.0.1",
     "is_on": false, "model": "HS200", "name": "One"},
    {"alias": "Two", "device_type": "DeviceType.WallSwitch", "host": "10.0.0.2",
     "is_on": false, "model": "HS200", "name": "Two"},
    {"alias": "Three", "device_type": "DeviceType.WallSwitch", "host": "10.0.0.3",
     "is_on": false, "model": "HS200", "name": "Three"}
  ]
}
""",
        encoding="utf-8",
    )


class SlowController:
    """Every status call takes `delay`; hosts in `dead` never answer."""

    def __init__(self, delay: float = 0.2, dead: set[str] | None = None) -> None:
        self.delay = delay
        self.dead = dead or set()
        self.status_calls: list[str] = []
        self.forgotten: list[str] = []

    async def status(self, switch) -> SwitchState:
        self.status_calls.append(switch.host)
        if switch.host in self.dead:
            await asyncio.sleep(3600)
        await asyncio.sleep(self.delay)
        return SwitchState(
            name=switch.name, host=switch.host, is_on=True,
            alias=switch.name, model=switch.model, brightness=40,
        )

    async def turn_off(self, switch) -> SwitchState:
        return SwitchState(
            name=switch.name, host=switch.host, is_on=False,
            alias=switch.name, model=switch.model,
        )

    async def forget(self, host: str) -> None:
        self.forgotten.append(host)


def test_switches_are_polled_concurrently(tmp_path: Path) -> None:
    discovery = tmp_path / "tplink_switches.json"
    _write_discovery(discovery)
    controller = SlowController(delay=0.2)
    client = TestClient(create_app(discovery_path=discovery, controller=controller))

    started = time.monotonic()
    response = client.get("/api/devices")
    elapsed = time.monotonic() - started

    assert response.status_code == 200
    assert len(controller.status_calls) == 3
    # Serial polling would cost 3 * 0.2s; concurrent stays near a single delay.
    assert elapsed < 0.5, f"switches appear to be polled serially ({elapsed:.2f}s)"


def test_one_dead_switch_does_not_stall_the_others(tmp_path: Path) -> None:
    discovery = tmp_path / "tplink_switches.json"
    _write_discovery(discovery)
    controller = SlowController(delay=0.05, dead={"10.0.0.2"})
    client = TestClient(create_app(discovery_path=discovery, controller=controller))

    started = time.monotonic()
    devices = client.get("/api/devices").json()["devices"]
    elapsed = time.monotonic() - started

    by_host = {device["host"]: device for device in devices}
    assert by_host["10.0.0.1"]["is_on"] is True
    assert by_host["10.0.0.3"]["is_on"] is True
    # The unreachable one reports unknown rather than failing the request.
    assert by_host["10.0.0.2"]["is_on"] is None
    assert elapsed < SWITCH_STATUS_TIMEOUT + 1.0


def test_repeated_failures_drop_the_cached_connection(tmp_path: Path) -> None:
    discovery = tmp_path / "tplink_switches.json"
    _write_discovery(discovery)
    controller = SlowController(delay=0.05, dead={"10.0.0.2"})
    app = create_app(discovery_path=discovery, controller=controller)

    asyncio.run(_poll_twice(app))

    # A power cycled switch only answers on a fresh connection, so the dead one
    # is released - but not on the first failure, which may just be slowness.
    assert controller.forgotten == ["10.0.0.2"]


async def _poll_twice(app) -> None:
    from src.python.web_app import _device_cards

    await _device_cards(app)
    await _device_cards(app)


def test_device_list_is_served_from_cache_after_the_first_load(tmp_path: Path) -> None:
    discovery = tmp_path / "tplink_switches.json"
    _write_discovery(discovery)
    controller = SlowController(delay=0.2)
    client = TestClient(create_app(discovery_path=discovery, controller=controller))

    client.get("/api/devices")
    calls_after_first = len(controller.status_calls)

    started = time.monotonic()
    response = client.get("/api/devices")
    elapsed = time.monotonic() - started

    assert response.status_code == 200
    assert response.json()["devices"], "cached response must still carry devices"
    assert len(controller.status_calls) == calls_after_first, "cached load re-polled devices"
    assert elapsed < 0.1, f"cached load should not wait on devices ({elapsed:.2f}s)"


def test_command_updates_the_cached_card(tmp_path: Path) -> None:
    discovery = tmp_path / "tplink_switches.json"
    _write_discovery(discovery)
    client = TestClient(create_app(discovery_path=discovery, controller=SlowController(delay=0.01)))

    assert client.get("/api/devices").json()["devices"][0]["is_on"] is True
    client.post("/api/devices/10.0.0.1/commands/off")

    # Without the cache patch this would read back the pre-command state.
    devices = {d["host"]: d for d in client.get("/api/devices").json()["devices"]}
    assert devices["10.0.0.1"]["is_on"] is False


@pytest.mark.parametrize(
    "url, expected",
    [
        ("/static/app.js?v=build107", "immutable"),
        ("/static/app.js", "max-age=300"),
    ],
)
def test_static_assets_carry_cache_headers(tmp_path: Path, url: str, expected: str) -> None:
    discovery = tmp_path / "tplink_switches.json"
    _write_discovery(discovery)
    client = TestClient(create_app(discovery_path=discovery, controller=SlowController()))

    response = client.get(url)

    assert response.status_code == 200
    assert expected in response.headers["cache-control"]


def test_text_assets_are_compressed(tmp_path: Path) -> None:
    discovery = tmp_path / "tplink_switches.json"
    _write_discovery(discovery)
    client = TestClient(create_app(discovery_path=discovery, controller=SlowController()))

    response = client.get("/static/app.js", headers={"Accept-Encoding": "gzip"})

    assert response.headers.get("content-encoding") == "gzip"
