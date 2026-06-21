from __future__ import annotations

import os
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    env_values = _env_file_values(PROJECT_ROOT / ".env")
    payload = yaml.safe_load((PROJECT_ROOT / "configs" / "devices.local.yaml").read_text(encoding="utf-8")) or {}
    devices = payload.get("tuya", {}).get("devices", [])
    with_key_env = [device for device in devices if device.get("local_key_env")]
    with_host = [device for device in devices if device.get("host")]
    missing = [device for device in with_key_env if not env_values.get(str(device.get("local_key_env")))]

    print(f"devices={len(devices)}")
    print(f"with_host={len(with_host)}")
    print(f"with_local_key_env={len(with_key_env)}")
    print(f"local_key_env_missing_in_env={len(missing)}")
    for device in missing[:20]:
        print(f"missing {device.get('name')} {device.get('local_key_env')}")

    loaded = 0
    for device in devices:
        key = str(device.get("local_key_env") or "")
        if key and env_values.get(key):
            os.environ.setdefault(key, env_values[key])
            loaded += 1
    print(f"loadable_local_keys={loaded}")


def _env_file_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


if __name__ == "__main__":
    main()
