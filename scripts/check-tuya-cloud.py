from __future__ import annotations

import inspect
import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TUYA_KEYS = [
    "TUYA_ACCESS_ID",
    "TUYA_ACCESS_SECRET",
    "TUYA_API_REGION",
    "TUYA_ENDPOINT",
    "TUYA_USERNAME",
    "TUYA_PASSWORD",
    "TUYA_COUNTRY_CODE",
    "TUYA_APP_TYPE",
]


def main() -> None:
    _load_env(PROJECT_ROOT / ".env")
    for key in TUYA_KEYS:
        value = os.getenv(key, "").strip()
        print(f"{key}={'set' if value and value != 'replace_me' else 'missing'}")

    try:
        import tinytuya
    except ImportError:
        print("tinytuya=missing")
        return

    print(f"tinytuya={getattr(tinytuya, '__version__', 'unknown')}")
    print(f"tinytuya.Cloud={'available' if hasattr(tinytuya, 'Cloud') else 'missing'}")
    if hasattr(tinytuya, "Cloud"):
        print(f"tinytuya.Cloud.signature={inspect.signature(tinytuya.Cloud)}")


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
