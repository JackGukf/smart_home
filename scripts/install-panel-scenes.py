#!/usr/bin/env python3
"""Install the Voice Panel's scenes as Home Assistant scripts.

Scenes live in Home Assistant, not on the panel, so the same Movie mode runs
from a tap on the panel, from "Okay Nabu, movie mode" and from the dashboard,
and is changed in one place (docs/design/voice-panel-screens.html, Decisions).

    All lights on / off   the six lights on the panel's Home page
    Movie mode            projector, Fire TV and Z906 on (family room IR remote);
                          the family room and kitchen lights, the family room LED,
                          both IKEA cabinet LEDs and the cabinet LED plug off

This file is the source of Movie mode: --apply replaces what is in Home
Assistant with what is here, so a change made only in Home Assistant's UI is
lost on the next run. (Until 2026-09-18 this held an older Movie mode than the
live one, and running it would have rolled the live one back.)

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

# The family room IR remote's learned switches (a Zigbee IR blaster).
IR_REMOTE = "switch.0xa4c1380c14c64266"
MOVIE_ON_IR = [
    (f"{IR_REMOTE}_switch1", "Projector"),
    (f"{IR_REMOTE}_switch2", "Fire TV Stick"),
    (f"{IR_REMOTE}_switch3", "Logitech Z906"),
]
# Switched off only if on: a TP-Link switch's "off" to an off switch is a wasted
# round trip that can time out. The TP-Link entities, not the Matter bridge's
# "_2" copies.
MOVIE_OFF_IF_ON = [
    ("light.family_room_switch", "Family room switch"),
    ("light.kitchen_light_switch", "Kitchen light switch"),
]
# The two IKEA TRADFRI LED drivers in the family room cabinet (Zigbee, added
# 2026-09-18). Zigbee entity ids that start with a digit: fine in a target,
# never write them as states.light.0x... in a template.
CABINET_LEDS = ["light.0x286847fffe5eb711", "light.0x64028ffffe64de32"]
# The cabinet's LED strip, on a TP-Link HS103 plug (192.168.0.142, added
# 2026-09-18). It replaced the IR "Smart IR Cabinet" light, whose off button
# was never learned.
CABINET_PLUG = "switch.family_room_cabinet_led"


IR_PAUSE_S = 1


def ir_on_with_pauses() -> list[dict]:
    steps: list[dict] = []
    for entity, name in MOVIE_ON_IR:
        if steps:
            steps.append({"delay": {"seconds": IR_PAUSE_S}})
        steps.append({"alias": f"{name} on (IR remote family room)", "action": "switch.turn_on",
                      "target": {"entity_id": entity}})
    return steps


def scripts() -> dict[str, dict]:
    return {
        "panel_all_lights_on": {
            "alias": "All lights on",
            "icon": "mdi:lightbulb-group",
            "mode": "single",
            # Each only if it is off: "on" to a light already on makes some
            # re-apply their level and flash - the owner's rule for anything
            # that turns lights on (2026-09-18).
            "sequence": [{"alias": f"{entity} on, if off",
                          "if": [{"condition": "state", "entity_id": entity, "state": "off"}],
                          "then": [{"action": "light.turn_on", "target": {"entity_id": entity}}]}
                         for entity in LIGHTS],
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
            "description": ("Projector, Fire TV and the Z906 on through the family room IR remote; "
                            "then the family room and kitchen lights, the family room LED, both "
                            "IKEA cabinet LEDs and the cabinet LED plug off."),
            "sequence": [
                # One IR blaster sends all three: a pause between them, or a code
                # sent while the last is still going out can be lost.
                *ir_on_with_pauses(),
                {"delay": {"seconds": 2}},
                *({"alias": f"{name} off, if on",
                   "if": [{"condition": "state", "entity_id": entity, "state": "on"}],
                   "then": [{"action": "light.turn_off", "target": {"entity_id": entity}}]}
                  for entity, name in MOVIE_OFF_IF_ON),
                {"alias": "Family room LED off", "action": "light.turn_off",
                 "target": {"entity_id": "light.family_room_led"}},
                {"alias": "Cabinet LEDs off (IKEA upper and lower)", "action": "light.turn_off",
                 "target": {"entity_id": CABINET_LEDS}},
                {"alias": "Cabinet LED plug off (Family room cabinet LED)", "action": "switch.turn_off",
                 "target": {"entity_id": CABINET_PLUG}},
            ],
        },
    }


def describe_step(step: dict) -> str:
    if "delay" in step:
        return f"wait {step['delay'].get('seconds', 0)} s"
    if "if" in step:
        inner = step["then"][0]
        condition = step["if"][0]
        return f"if {condition['entity_id']} is {condition['state']}: {describe_step(inner)}"
    targets = step["target"]["entity_id"]
    targets = targets if isinstance(targets, list) else [targets]
    return f"{step['action']}: {', '.join(targets)}"


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
            print(f"    {describe_step(step)}")
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
