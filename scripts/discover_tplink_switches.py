from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from kasa import Discover


@dataclass(frozen=True)
class DiscoveredSwitch:
    name: str
    host: str
    alias: str | None
    model: str | None
    device_type: str | None
    is_on: bool | None


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
    devices = await Discover.discover(timeout=timeout)
    switches: list[DiscoveredSwitch] = []

    try:
        for host, device in sorted(devices.items()):
            try:
                await device.update()
            except Exception:
                pass

            if not _looks_like_light_switch(device):
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
                )
            )
    finally:
        for device in devices.values():
            disconnect = _safe_getattr(device, "disconnect")
            if disconnect:
                await disconnect()

    return switches


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Discover TP-Link/Kasa light switches on the LAN.")
    parser.add_argument("--output", type=Path, default=Path("tplink_switches.json"))
    parser.add_argument("--timeout", type=int, default=10)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    switches = asyncio.run(discover_switches(args.timeout))
    payload = {
        "count": len(switches),
        "switches": [asdict(switch) for switch in switches],
    }
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"count": len(switches), "output": str(args.output)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
