from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = PROJECT_ROOT / "snapshot.json"
CONFIG_PATH = PROJECT_ROOT / "configs" / "devices.local.yaml"


def main() -> None:
    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    discovered = list(_iter_devices(snapshot))
    if not discovered:
        raise SystemExit("No Tuya devices found in snapshot.json")

    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) if CONFIG_PATH.exists() else {}
    config = config or {}
    tuya = config.setdefault("tuya", {})
    devices = tuya.setdefault("devices", [])
    existing_ids = {str(device.get("device_id")) for device in devices}

    added = 0
    for device in discovered:
        device_id = str(device["device_id"])
        if device_id in existing_ids:
            continue
        devices.append(
            {
                "name": f"Tuya {device.get('host', device_id)}",
                "device_id": device_id,
                "host": device.get("host"),
                "local_key_env": _local_key_env(device_id),
                "version": device.get("version", 3.3),
                "category": "tuya_device",
                "model": device.get("product_id"),
            }
        )
        added += 1

    CONFIG_PATH.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    print(f"Imported {added} new Tuya device(s); {len(devices)} total configured.")


def _iter_devices(value: Any):
    if isinstance(value, dict):
        maybe = _device_from_dict(value)
        if maybe:
            yield maybe
        for child in value.values():
            yield from _iter_devices(child)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_devices(item)


def _device_from_dict(value: dict[str, Any]) -> dict[str, Any] | None:
    device_id = value.get("gwId") or value.get("id") or value.get("device_id")
    host = value.get("ip") or value.get("host") or value.get("address")
    if not device_id or not host:
        return None
    return {
        "device_id": device_id,
        "host": host,
        "version": value.get("version") or value.get("ver") or 3.3,
        "product_id": value.get("productKey") or value.get("product_id") or value.get("productID"),
    }


def _local_key_env(device_id: str) -> str:
    suffix = re.sub(r"[^A-Za-z0-9]+", "_", device_id).upper().strip("_")
    return f"TUYA_{suffix}_LOCAL_KEY"


if __name__ == "__main__":
    main()
