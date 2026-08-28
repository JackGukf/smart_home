from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from kasa import Discover

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.python.tplink_discovery import normalize_mac  # noqa: E402


@dataclass(frozen=True)
class DiscoveredSwitch:
    name: str
    host: str
    alias: str | None
    model: str | None
    device_type: str | None
    is_on: bool | None
    # The only identifier that survives a DHCP lease change; the dashboard uses
    # it to find a switch again after its IP moves.
    mac: str | None


def _is_tapo_device(device: Any) -> bool:
    """Tapo-family devices (e.g. S505) are Matter devices managed elsewhere;
    listing them here would duplicate their Matter/Home Assistant card."""
    family = ""
    config = _safe_getattr(device, "config")
    connection = _safe_getattr(config, "connection_type") if config else None
    if connection is not None:
        family = str(_safe_getattr(connection, "device_family") or "")
    model = str(_safe_getattr(device, "model") or "")
    return "tapo" in family.lower() or model.upper().startswith("S5")


def _looks_like_light_switch(device: Any) -> bool:
    device_type = str(_safe_getattr(device, "device_type") or _safe_getattr(device, "type") or "")
    model = str(_safe_getattr(device, "model") or "")
    alias = str(_safe_getattr(device, "alias") or "")
    text = " ".join([device_type, model, alias]).lower()
    return any(token in text for token in ("switch", "dimmer", "hs", "ks"))


def _safe_getattr(device: Any, name: str, default: Any = None) -> Any:
    try:
        return getattr(device, name)
    except Exception:
        return default


async def discover_switches(timeout: int) -> list[DiscoveredSwitch]:
    # Newer Kasa firmware (KLAP protocol, e.g. recent HS103) only reveals the
    # alias after authenticating with the TP-Link cloud account credentials.
    kwargs: dict[str, Any] = {}
    username = os.getenv("TPLINK_USERNAME")
    password = os.getenv("TPLINK_PASSWORD")
    if username and password:
        kwargs["username"] = username
        kwargs["password"] = password
    devices = await Discover.discover(timeout=timeout, **kwargs)
    switches: list[DiscoveredSwitch] = []

    try:
        for host, device in sorted(devices.items()):
            try:
                await device.update()
            except Exception:
                pass

            if _is_tapo_device(device) or not _looks_like_light_switch(device):
                continue

            alias = _safe_getattr(device, "alias")
            switches.append(
                DiscoveredSwitch(
                    name=alias or host,
                    host=host,
                    alias=alias,
                    model=_safe_getattr(device, "model"),
                    device_type=str(_safe_getattr(device, "device_type") or _safe_getattr(device, "type") or "") or None,
                    is_on=_safe_getattr(device, "is_on"),
                    mac=normalize_mac(_safe_getattr(device, "mac")),
                )
            )
    finally:
        for device in devices.values():
            disconnect = _safe_getattr(device, "disconnect")
            if disconnect:
                await disconnect()

    return switches


def merge_previous_aliases(
    switches: list[dict[str, Any]], previous: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Keep a previously known alias when a re-discovery could not read one.

    KLAP devices report no alias without credentials; without this, re-running
    discovery would replace manually assigned names with bare IP addresses.

    Matched on MAC before host, so a switch that changed address keeps its name
    instead of reverting to a bare IP - which is exactly when a device is least
    recognisable and the name matters most.
    """
    previous_by_mac = {
        mac: item for item in previous if (mac := normalize_mac(item.get("mac")))
    }
    previous_by_host = {item.get("host"): item for item in previous}
    merged = []
    for item in switches:
        if not item.get("alias"):
            old = previous_by_mac.get(normalize_mac(item.get("mac"))) or previous_by_host.get(item.get("host"))
            if old and old.get("alias"):
                item = {**item, "alias": old["alias"], "name": old["alias"]}
        merged.append(item)
    return merged


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Discover TP-Link/Kasa light switches on the LAN.")
    parser.add_argument("--output", type=Path, default=Path("tplink_switches.json"))
    parser.add_argument("--timeout", type=int, default=10)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    switches = [asdict(switch) for switch in asyncio.run(discover_switches(args.timeout))]
    if args.output.exists():
        try:
            previous = json.loads(args.output.read_text(encoding="utf-8")).get("switches", [])
        except Exception:
            previous = []
        switches = merge_previous_aliases(switches, previous)
    payload = {
        "count": len(switches),
        "switches": switches,
    }
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"count": len(switches), "output": str(args.output)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
