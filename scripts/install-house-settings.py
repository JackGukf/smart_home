#!/usr/bin/env python3
"""Create the Home Assistant helpers behind Settings -> House rules
(src/python/house_settings.py): one input_number.house_<key> per tunable number.

A helper is set to its default only when this creates it; one that exists keeps
whatever the owner chose. Idempotent.

    python3 scripts/install-house-settings.py            # show it
    python3 scripts/install-house-settings.py --apply    # create what is missing (on the board)
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys
import urllib.error
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.python import house_settings  # noqa: E402


def _door_alerts():
    spec = importlib.util.spec_from_file_location("door_alerts", PROJECT_ROOT / "scripts" / "install-door-alerts.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ensure(base_url: str, token: str) -> list[str]:
    doors = _door_alerts()
    created = []
    for entity_id, message in house_settings.ha_helper_messages():
        try:
            doors._request(base_url, token, f"/api/states/{entity_id}")
            continue
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
        reply = doors._ws(base_url, token, [message])[0]
        if not reply.get("success"):
            raise OSError(f"could not create {entity_id}: {reply.get('error')}")
        setting = next(s for s in house_settings.SETTINGS if s.entity == entity_id)
        if setting.kind == "time":
            doors._request(base_url, token, "/api/services/input_datetime/set_datetime",
                           {"entity_id": entity_id, "time": f"{setting.default}:00"}, "POST")
        else:
            doors._request(base_url, token, "/api/services/input_number/set_value",
                           {"entity_id": entity_id, "value": setting.default}, "POST")
        created.append(f"{entity_id} = {setting.default}")
    return created


def main(argv: list[str] | None = None) -> int:
    _door_alerts().load_dotenv(PROJECT_ROOT / ".env")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--base-url", default=os.getenv("HOME_ASSISTANT_BASE_URL", "http://127.0.0.1:8123"))
    args = ap.parse_args(argv)
    for entity_id, message in house_settings.ha_helper_messages():
        print(entity_id, message)
    if not args.apply:
        print("\nNothing was written. Re-run with --apply.")
        return 0
    token = os.getenv("HOME_ASSISTANT_TOKEN")
    if not token:
        print("HOME_ASSISTANT_TOKEN is not set (looked in .env)", file=sys.stderr)
        return 1
    try:
        created = ensure(args.base_url.rstrip("/"), token)
    except (OSError, urllib.error.HTTPError) as exc:
        print(f"failed: {exc}", file=sys.stderr)
        return 1
    print("\n".join(f"created {c}" for c in created) or "all helpers exist - values left as they are")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
