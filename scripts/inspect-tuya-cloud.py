from __future__ import annotations

import json
import os
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    _load_env(PROJECT_ROOT / ".env")
    try:
        import tinytuya
    except ImportError as exc:
        raise SystemExit("tinytuya is required") from exc

    cloud = tinytuya.Cloud(
        apiRegion=os.environ["TUYA_API_REGION"],
        apiKey=os.environ["TUYA_ACCESS_ID"],
        apiSecret=os.environ["TUYA_ACCESS_SECRET"],
        apiDeviceID=os.getenv("TUYA_DEVICE_ID") or None,
    )
    payload = yaml.safe_load((PROJECT_ROOT / "configs" / "devices.local.yaml").read_text(encoding="utf-8")) or {}
    devices = [item for item in payload.get("tuya", {}).get("devices", []) if item.get("enabled") is not False]
    name_filter = os.getenv("TUYA_INSPECT_NAME", "").lower()
    if name_filter:
        devices = [item for item in devices if name_filter in str(item.get("name", "")).lower()]
    limit = int(os.getenv("TUYA_INSPECT_LIMIT", "4"))
    for device in devices[:limit]:
        device_id = device.get("device_id")
        print(f"DEVICE {device.get('name')} {device_id}", flush=True)
        try:
            print("CALL getstatus", flush=True)
            status = cloud.getstatus(device_id)
            print("CALL getfunctions", flush=True)
            functions = cloud.getfunctions(device_id)
        except Exception as exc:
            print(f"ERR {type(exc).__name__}: {str(exc)[:160]}")
            continue
        print("STATUS", _short_json(status), flush=True)
        print("FUNCS", _short_json(functions), flush=True)


def _short_json(value) -> str:
    return json.dumps(value, ensure_ascii=False)[:1000]


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
