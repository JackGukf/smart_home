#!/usr/bin/env python3
"""Install the Voice Panel's scenes as Home Assistant scripts.

Scenes live in Home Assistant, not on the panel, so the same Movie mode runs
from a tap on the panel, from "Okay Nabu, movie mode" and from the dashboard,
and is changed in one place (docs/design/voice-panel-screens.html, Decisions).

    All lights on / off   the six lights on the panel's Home page
    Movie mode            Living room switch 2 and cabinet LED off,
                          Living room ambient light on

Written through Home Assistant's config API, like install-living-room-lighting.py:
the same validator the UI uses runs first and scripts are reloaded, so a bad
action is refused with a message instead of being written to scripts.yaml.
The two scenes already in Home Assistant ("Turn on all lights" and its pair)
are not reused: they are not in scenes.yaml, and what they switch is not visible.

    python3 scripts/install-panel-scenes.py            # show what would be installed
    python3 scripts/install-panel-scenes.py --apply    # install (run on the board)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# The panel's Home page cards, in the same entities it binds to
# (configs/esphome/voice-panel.yaml). tests/python/test_install_panel_scenes.py
# checks the two lists agree.
LIGHTS = [
    "light.bedroom_master_bedroom_light",
    "light.living_room_living_room_switch_2",
    "light.kitchen_light_switch",
    "light.family_room_switch",
    "light.bedroom_north_bedroom_light_switch",
    "light.stick_s3",
]

MOVIE_OFF_LIGHTS = ["light.living_room_living_room_switch_2"]
MOVIE_OFF_SWITCHES = ["switch.living_room_cabinet_led"]
MOVIE_ON_LIGHTS = ["light.h6076"]  # Living room ambient light (Govee)


def scripts() -> dict[str, dict]:
    return {
        "panel_all_lights_on": {
            "alias": "All lights on",
            "icon": "mdi:lightbulb-group",
            "mode": "single",
            "sequence": [{"action": "light.turn_on", "target": {"entity_id": LIGHTS}}],
        },
        "panel_all_lights_off": {
            "alias": "All lights off",
            "icon": "mdi:lightbulb-group-off",
            "mode": "single",
            "sequence": [{"action": "light.turn_off", "target": {"entity_id": LIGHTS}}],
        },
        "movie_mode": {
            "alias": "Movie mode",
            "icon": "mdi:movie-open",
            "mode": "single",
            "sequence": [
                {"action": "light.turn_off", "target": {"entity_id": MOVIE_OFF_LIGHTS}},
                {"action": "switch.turn_off", "target": {"entity_id": MOVIE_OFF_SWITCHES}},
                {"action": "light.turn_on", "target": {"entity_id": MOVIE_ON_LIGHTS}},
            ],
        },
    }


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def install(base_url: str, token: str, script_id: str, body: dict) -> None:
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/config/script/config/{script_id}",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        response.read()


def main(argv: list[str] | None = None) -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="without this, nothing is changed")
    ap.add_argument("--base-url", default=os.getenv("HOME_ASSISTANT_BASE_URL",
                                                    "http://127.0.0.1:8123"))
    args = ap.parse_args(argv)

    token = os.getenv("HOME_ASSISTANT_TOKEN")
    if args.apply and not token:
        print("HOME_ASSISTANT_TOKEN is not set (looked in .env)", file=sys.stderr)
        return 1

    for script_id, body in scripts().items():
        print(f"\nscript.{script_id}  ({body['alias']})")
        for step in body["sequence"]:
            print(f"    {step['action']}: {', '.join(step['target']['entity_id'])}")
        if not args.apply:
            continue
        try:
            install(args.base_url, token, script_id, body)
        except urllib.error.HTTPError as exc:
            # 400 is Home Assistant's own validator, and its message says what is wrong.
            print(f"    REFUSED {exc.code}: {exc.read().decode('utf-8', 'replace')[:400]}",
                  file=sys.stderr)
            return 1
        except OSError as exc:
            print(f"    could not reach Home Assistant at {args.base_url}: {exc}", file=sys.stderr)
            return 1
        print("    installed (Home Assistant validated it and reloaded scripts)")

    if not args.apply:
        print("\nNothing was written. Re-run with --apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
