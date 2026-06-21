from __future__ import annotations

import argparse
import os
import re
import shlex
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "devices.local.yaml"
DEFAULT_SNAPSHOT = PROJECT_ROOT / "snapshot.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Import Tuya Cloud devices into the dashboard config.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--snapshot", default=str(DEFAULT_SNAPSHOT))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    _load_env(PROJECT_ROOT / ".env")
    cloud = _tuya_cloud()
    cloud_devices = _normalize_devices(cloud.getdevices())
    if not cloud_devices:
        raise SystemExit("No Tuya Cloud devices returned. Confirm the app account is linked to the IoT project.")

    config_path = Path(args.config)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    config = config or {}
    tuya = config.setdefault("tuya", {})
    configured = tuya.setdefault("devices", [])

    snapshot_by_id = _snapshot_by_id(Path(args.snapshot))
    existing_by_id = {
        str(item.get("device_id") or item.get("id")): item
        for item in configured
        if item.get("device_id") or item.get("id")
    }

    added = 0
    updated = 0
    returned_ids: set[str] = set()
    env_updates: dict[str, str] = {}
    for cloud_device in cloud_devices:
        device_id = str(cloud_device.get("id") or cloud_device.get("dev_id") or cloud_device.get("device_id") or "")
        if not device_id:
            continue
        returned_ids.add(device_id)

        snapshot = snapshot_by_id.get(device_id, {})
        local_key = _first_present(cloud_device, "local_key", "localKey", "key")

        item = existing_by_id.get(device_id)
        if not item:
            item = {"device_id": device_id}
            configured.append(item)
            existing_by_id[device_id] = item
            added += 1
        else:
            updated += 1

        local_key_env = str(item.get("local_key_env") or f"TUYA_{_env_slug(_device_name(cloud_device, device_id))}_LOCAL_KEY")
        if local_key:
            env_updates[local_key_env] = str(local_key)

        item["name"] = _device_name(cloud_device, device_id)
        item["enabled"] = True
        item["category"] = _category(cloud_device)
        item["room"] = item.get("room") or _room_from_name(item["name"])
        item["model"] = _model(cloud_device)
        item["host"] = _host(cloud_device, snapshot)
        item["version"] = float(cloud_device.get("version") or snapshot.get("version") or item.get("version") or 3.4)
        if local_key or item.get("local_key_env"):
            item["local_key_env"] = local_key_env
        power_dp = item.get("power_dp") or _power_dp_hint(cloud_device)
        if power_dp:
            item["power_dp"] = str(power_dp)
        cloud_power_code = _cloud_power_code(cloud, device_id)
        if cloud_power_code:
            item["cloud_power_code"] = cloud_power_code
        else:
            item.pop("cloud_power_code", None)

    disabled = 0
    for item in configured:
        device_id = str(item.get("device_id") or item.get("id") or "")
        if device_id and device_id not in returned_ids:
            item["enabled"] = False
            disabled += 1

    if args.dry_run:
        print(f"Tuya Cloud returned {len(cloud_devices)} device(s); would add {added}, update {updated}, disable {disabled} stale.")
        _print_env_updates(env_updates)
        return

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    _merge_env(PROJECT_ROOT / ".env", env_updates)
    print(f"Tuya Cloud returned {len(cloud_devices)} device(s); added {added}, updated {updated}, disabled {disabled} stale.")
    print(f"Wrote {config_path}.")
    if env_updates:
        print(f"Updated .env with {len(env_updates)} Tuya local key variable(s).")


def _tuya_cloud():
    try:
        import tinytuya
    except ImportError as exc:
        raise SystemExit("tinytuya is required. Install project Python requirements first.") from exc

    api_region = _env("TUYA_API_REGION", "TUYA_REGION")
    api_key = _env("TUYA_ACCESS_ID", "TUYA_API_KEY")
    api_secret = _env("TUYA_ACCESS_SECRET", "TUYA_API_SECRET")
    api_device_id = _env("TUYA_DEVICE_ID", "TUYA_API_DEVICE_ID")

    missing = [
        name
        for name, value in {
            "TUYA_ACCESS_ID": api_key,
            "TUYA_ACCESS_SECRET": api_secret,
            "TUYA_API_REGION": api_region,
        }.items()
        if not value
    ]
    if missing:
        raise SystemExit(f"Missing Tuya Cloud setting(s): {', '.join(missing)}")

    kwargs = {
        "apiRegion": api_region,
        "apiKey": api_key,
        "apiSecret": api_secret,
    }
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


def _snapshot_by_id(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    devices = payload.get("devices") if isinstance(payload, dict) else payload
    if not isinstance(devices, list):
        return {}
    return {
        str(item.get("gwId") or item.get("id") or item.get("device_id")): item
        for item in devices
        if isinstance(item, dict) and (item.get("gwId") or item.get("id") or item.get("device_id"))
    }


def _merge_env(path: Path, updates: dict[str, str]) -> None:
    if not updates:
        return
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    existing = {line.split("=", 1)[0].strip() for line in lines if "=" in line and not line.strip().startswith("#")}
    additions = [f"{key}={shlex.quote(value)}" for key, value in sorted(updates.items()) if key not in existing]
    if not additions:
        return
    if lines and lines[-1].strip():
        lines.append("")
    lines.extend(additions)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _print_env_updates(updates: dict[str, str]) -> None:
    for key in sorted(updates):
        print(f"{key}=<hidden>")


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


def _first_present(item: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return value
    return None


def _device_name(item: dict[str, Any], device_id: str) -> str:
    return str(_first_present(item, "name", "custom_name", "icon_name", "product_name") or f"Tuya {device_id}")


def _category(item: dict[str, Any]) -> str:
    raw = " ".join(
        str(_first_present(item, key) or "")
        for key in ("category", "category_name", "product_name", "product_id", "name", "custom_name", "icon_name")
    ).lower()
    if any(term in raw for term in ("camera", "doorbell", "door bell", "门铃")):
        return "tuya_camera"
    if any(term in raw for term in ("alarm host", "alarm system", "multi-mode gateway", "gateway", "报警主机", "bao_jing", "siren")):
        return "tuya_alarm"
    if any(term in raw for term in ("switch", "plug", "outlet", "socket", "kg", "cz")):
        return "tuya_switch"
    if any(term in raw for term in ("sensor", "motion", "pir", "contact", "temperature", "humidity")):
        return "tuya_sensor"
    return "tuya_device"


def _model(item: dict[str, Any]) -> str | None:
    value = _first_present(item, "product_name", "model", "category_name", "product_id")
    return str(value) if value else None


def _host(item: dict[str, Any], snapshot: dict[str, Any]) -> str | None:
    value = _first_present(item, "ip", "local_ip", "host") or snapshot.get("ip") or snapshot.get("host")
    return str(value) if value else None


def _power_dp_hint(item: dict[str, Any]) -> str | None:
    if _category(item) != "tuya_switch":
        return None
    return "1"


def _cloud_power_code(cloud: Any, device_id: str) -> str | None:
    try:
        payload = cloud.getfunctions(device_id)
    except Exception:
        return None
    functions = _function_list(payload)
    candidates = {"switch", "switch_1", "switch_led", "power", "power_switch"}
    for function in functions:
        code = str(function.get("code") or "")
        kind = str(function.get("type") or "").lower()
        if kind == "boolean" and code in candidates:
            return code
    return None


def _function_list(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    result = payload.get("result")
    if isinstance(result, dict):
        functions = result.get("functions")
        if isinstance(functions, list):
            return [item for item in functions if isinstance(item, dict)]
    if isinstance(result, list):
        return [item for item in result if isinstance(item, dict)]
    return []


def _room_from_name(name: str) -> str:
    return str(name).replace("_", " ").replace("-", " ").title()


def _env_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").upper()
    return slug or "DEVICE"


if __name__ == "__main__":
    main()
