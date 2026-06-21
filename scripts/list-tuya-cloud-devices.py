#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    _load_env(PROJECT_ROOT / ".env")
    cloud = _tuya_cloud()
    devices = _normalize_devices(cloud.getdevices())
    terms = [term.lower() for term in os.getenv("TUYA_LIST_FILTER", "").split(",") if term.strip()]
    rows = []
    for item in devices:
        name = _device_name(item)
        category = _category(item)
        text = " ".join(str(item.get(key) or "") for key in ("id", "dev_id", "name", "custom_name", "product_name", "category", "category_name", "product_id")).lower()
        if terms and not any(term in text for term in terms):
            continue
        rows.append(
            {
                "id": item.get("id") or item.get("dev_id") or item.get("device_id"),
                "name": name,
                "category": category,
                "product_name": item.get("product_name"),
                "category_name": item.get("category_name") or item.get("category"),
                "online": item.get("online"),
            }
        )
    print(json.dumps(rows, ensure_ascii=False, indent=2))


def _tuya_cloud():
    try:
        import tinytuya
    except ImportError as exc:
        raise SystemExit("tinytuya is required") from exc
    api_region = _env("TUYA_API_REGION", "TUYA_REGION")
    api_key = _env("TUYA_ACCESS_ID", "TUYA_API_KEY")
    api_secret = _env("TUYA_ACCESS_SECRET", "TUYA_API_SECRET")
    api_device_id = _env("TUYA_DEVICE_ID", "TUYA_API_DEVICE_ID")
    missing = [name for name, value in {"TUYA_API_REGION": api_region, "TUYA_ACCESS_ID": api_key, "TUYA_ACCESS_SECRET": api_secret}.items() if not value]
    if missing:
        raise SystemExit(f"Missing Tuya Cloud setting(s): {', '.join(missing)}")
    kwargs = {"apiRegion": api_region, "apiKey": api_key, "apiSecret": api_secret}
    if api_device_id:
        kwargs["apiDeviceID"] = api_device_id
    return tinytuya.Cloud(**kwargs)


def _normalize_devices(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("devices", "result", "list"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
            if isinstance(value, dict):
                nested = _normalize_devices(value)
                if nested:
                    return nested
    return []


def _device_name(item: dict[str, Any]) -> str:
    for key in ("name", "custom_name", "icon_name", "product_name"):
        value = item.get(key)
        if value:
            return str(value)
    return str(item.get("id") or item.get("dev_id") or "Tuya device")


def _category(item: dict[str, Any]) -> str:
    raw = " ".join(str(item.get(key) or "") for key in ("category", "category_name", "product_name", "product_id", "name", "custom_name", "icon_name")).lower()
    if any(term in raw for term in ("camera", "doorbell", "door bell", "门铃")):
        return "tuya_camera"
    if any(term in raw for term in ("alarm", "siren", "gateway", "报警主机", "bao_jing")):
        return "tuya_alarm"
    if any(term in raw for term in ("switch", "plug", "outlet", "socket", "kg", "cz")):
        return "tuya_switch"
    if any(term in raw for term in ("sensor", "motion", "pir", "contact", "temperature", "humidity")):
        return "tuya_sensor"
    return "tuya_device"


def _env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name, "").strip()
        if value and value != "replace_me":
            return value
    return None


def _load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


if __name__ == "__main__":
    main()