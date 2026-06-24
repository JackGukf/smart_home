#!/usr/bin/env python3
"""Scan nearby Bluetooth devices for Govee LED strips from the Raspberry Pi."""
from __future__ import annotations

import asyncio
import json


async def main() -> None:
    try:
        from bleak import BleakScanner
    except Exception as exc:
        raise SystemExit(f"Install bleak first: python -m pip install bleak ({exc})")

    try:
        devices = await BleakScanner.discover(timeout=10.0)
    except Exception as exc:
        print(json.dumps({
            "devices": [],
            "error": str(exc),
            "fix": [
                "sudo /usr/sbin/rfkill unblock bluetooth",
                "sudo systemctl restart bluetooth",
                "sudo bluetoothctl power on",
                "bluetoothctl show",
            ],
        }, indent=2))
        raise SystemExit(2)
    matches = []
    for device in devices:
        name = device.name or ""
        text = f"{name} {device.address}".lower()
        if "govee" not in text and "h613a" not in text and "h6054" not in text:
            continue
        matches.append({"name": name, "address": device.address, "rssi": getattr(device, "rssi", None)})

    print(json.dumps({"devices": matches}, indent=2))
    if not matches:
        print("No Govee BLE devices found. Make sure Bluetooth is enabled on the Pi and the strips are powered nearby.")


if __name__ == "__main__":
    asyncio.run(main())
