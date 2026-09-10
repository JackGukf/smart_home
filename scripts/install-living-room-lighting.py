#!/usr/bin/env python3
"""Install the living room lighting rules into Home Assistant.

Three automations that work together:

  * **on** when you come *downstairs* into a dark living room
  * **on** when there is motion in the room at all and it is dark - the
    fallback, and in practice the common case, because the downstairs sensor
    only fires on the stairs
  * **off** after 11pm once the room has been quiet for half an hour

Neither "on" rule will override a switch you turned off by hand.

Installed through Home Assistant's own config API rather than by appending to
``automations.yaml``.  That runs the same validator the UI does, writes the file
itself and reloads automations, so a malformed template is refused with a
precise message instead of being written to disk and failing silently at 11pm.
Both of the template bugs below were caught that way.

Idempotent: the ids are fixed, so re-running replaces rather than duplicates.
Nothing is written without ``--apply``.

    python3 scripts/install-living-room-lighting.py           # show the plan
    python3 scripts/install-living-room-lighting.py --apply

## Three things that are not obvious

**Direction, not presence.**  The downstairs sensor fires whether you are going
up or coming down.  What separates them is that the *upstairs* sensor was active
in the seconds before -- so the "on" rule triggers downstairs and checks
upstairs, rather than the other way round.

**The light meter lags the light.**  Measured on this house: the switch went off
at 21:56:48 and the illuminance sensor still reported 183 lx at 21:57:04,
reaching 0 only at 21:58:08.  For 80 seconds the automation would refuse itself
on a reading that its own action had caused.  A reading older than the switch's
last change cannot describe the room as it is now, so in that case the rule
falls back to the sun -- but only then, because "it is night" alone would fire
even with another lamp lighting the room.

**A switch you turned off yourself is left alone.**  A state change Home
Assistant caused carries a context - a ``user_id`` when a person did it in HA, a
``parent_id`` when an automation did.  A change made at the wall carries
neither, which is the only signal there is that *you* turned it off; the switch
does not report how it was pressed.  Both "on" rules respect that for
``MANUAL_OFF_SUPPRESS_S``.

**Two triggers on the off rule.**  Motion going quiet handles the usual case.
The 23:00 trigger catches a night that was *already* quiet before 11pm, which
the first trigger would have fired for at 22:xx and had refused by the time
condition.

## Two Jinja traps this file exists to not repeat

* These Zigbee entity ids **start with a digit**, so ``states.binary_sensor.0xa4c...``
  is a syntax error.  The subscript form is required.
* ``}}`` inside a Python f-string collapses to a single ``}``.  Templates here
  are built by concatenation for that reason -- never an f-string.
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

# --------------------------------------------------------------- the entities
UP_MOTION = "binary_sensor.0xa4c138ae6a275f0f_presence"      # Motion sensor and TH Upstairs
DOWN_MOTION = "binary_sensor.0xa4c138257e0d2173_presence"    # Motion sensor and illumination
LR_MOTION = "binary_sensor.0xa4c1381f2015da50_presence"      # Motion sensor and TH Living room
LR_LUX = "sensor.0xa4c1381f2015da50_illuminance"             # same device as LR_MOTION
SWITCH = "switch.living_room_switch_2"

# Dark reads ~12 lx here; lit or in daylight it is never below 160. 50 sits
# clear of both edges.
DARK_LX = 50
# Long enough for a slow descent plus the sensors' 30s fade, short enough that
# "was upstairs an hour ago" does not count.
CAME_DOWN_WINDOW_S = 120
# How long the room must be still before it counts as empty. 30 minutes, not
# 10: the living room sensor's p90 gap is 10.9 minutes, so sitting quietly
# watching television regularly exceeded 10 and turned the light off on someone
# who was still in the room.
QUIET_FOR = "00:30:00"
# How long a switch you turned off by hand stays off. Measured: a change made
# outside Home Assistant carries no context at all (user_id and parent_id both
# None), where anything HA did carries one - so "you turned it off" is
# detectable, and this is how long that decision is respected.
MANUAL_OFF_SUPPRESS_S = 1800


def _came_down() -> str:
    return (
        "{% set up = states['" + UP_MOTION + "'] %}"
        "{{ up is not none and (up.state == 'on' or "
        "(now() - up.last_changed).total_seconds() < " + str(CAME_DOWN_WINDOW_S) + ") }}"
    )


def _is_dark() -> str:
    return (
        "{% set lux = states['" + LR_LUX + "'] %}"
        "{% set sw = states['" + SWITCH + "'] %}"
        "{% set reading = lux.state | float(9999) %}"
        "{% set stale = lux.last_changed < sw.last_changed %}"
        "{{ reading < " + str(DARK_LX) + " or "
        "(stale and is_state('sun.sun', 'below_horizon')) }}"
    )


def _not_recently_switched_off_by_hand() -> str:
    """True unless you turned the switch off yourself in the last while.

    A state change Home Assistant caused carries a context - a user_id for
    something a person did in HA, a parent_id for something an automation did.
    A change made at the wall, or in the Kasa app, or by a schedule on the
    device itself, carries neither. That is the signal, and it is the only one
    available: the switch does not report *how* it was pressed.
    """
    return (
        "{% set sw = states['" + SWITCH + "'] %}"
        "{% set by_hand = sw.context.user_id is none and sw.context.parent_id is none %}"
        "{{ not (sw.state == 'off' and by_hand and "
        "(now() - sw.last_changed).total_seconds() < " + str(MANUAL_OFF_SUPPRESS_S) + ") }}"
    )


def automations() -> dict[str, dict]:
    return {
        "living_room_on_when_dark": {
            "id": "living_room_on_when_dark",
            "alias": "Living room - on when you come downstairs in the dark",
            "description": (
                "Triggers on the downstairs sensor and checks the upstairs one, because "
                "the downstairs sensor alone cannot tell up from down. Dark is the living "
                "room meter at 50 lx, with a fallback for when that reading predates the "
                "switch changing and so cannot describe the room yet."
            ),
            "triggers": [
                {"trigger": "state", "entity_id": DOWN_MOTION, "from": "off", "to": "on"},
            ],
            "conditions": [
                {"condition": "template", "value_template": _came_down()},
                {"condition": "template", "value_template": _is_dark()},
                {"condition": "template", "value_template": _not_recently_switched_off_by_hand()},
                # Nothing to do if it is already on, and it saves a device round trip.
                {"condition": "state", "entity_id": SWITCH, "state": "off"},
            ],
            "actions": [{"action": "switch.turn_on", "target": {"entity_id": SWITCH}}],
            "mode": "single",
        },
        "living_room_on_when_motion": {
            "id": "living_room_on_when_motion",
            "alias": "Living room - on when there is motion in the room and it is dark",
            "description": (
                "The fallback for arriving without passing the downstairs sensor - which "
                "is most of the time, since that sensor fires only on the stairs. Same "
                "dark test as the descent rule, and the same respect for a switch you "
                "turned off by hand."
            ),
            "triggers": [
                {"trigger": "state", "entity_id": LR_MOTION, "from": "off", "to": "on"},
            ],
            "conditions": [
                {"condition": "template", "value_template": _is_dark()},
                {"condition": "template", "value_template": _not_recently_switched_off_by_hand()},
                {"condition": "state", "entity_id": SWITCH, "state": "off"},
            ],
            "actions": [{"action": "switch.turn_on", "target": {"entity_id": SWITCH}}],
            "mode": "single",
        },
        "living_room_off_late_and_quiet": {
            "id": "living_room_off_late_and_quiet",
            "alias": "Living room - off after 11pm once quiet for 30 minutes",
            "description": (
                "Two triggers: motion going quiet handles the usual case, and the 23:00 "
                "trigger catches a night already quiet before 11pm. Both then check the "
                "same two things."
            ),
            "triggers": [
                {"trigger": "state", "entity_id": LR_MOTION, "to": "off", "for": QUIET_FOR},
                {"trigger": "time", "at": "23:00:00"},
            ],
            "conditions": [
                {"condition": "time", "after": "23:00:00", "before": "06:00:00"},
                {"condition": "state", "entity_id": LR_MOTION, "state": "off", "for": QUIET_FOR},
                {"condition": "state", "entity_id": SWITCH, "state": "on"},
            ],
            "actions": [{"action": "switch.turn_off", "target": {"entity_id": SWITCH}}],
            "mode": "single",
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


def install(base_url: str, token: str, auto_id: str, body: dict) -> None:
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/config/automation/config/{auto_id}",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        response.read()


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="without this, nothing is changed")
    ap.add_argument("--base-url", default=os.getenv("HOME_ASSISTANT_BASE_URL",
                                                    "http://127.0.0.1:8123"))
    args = ap.parse_args()

    token = os.getenv("HOME_ASSISTANT_TOKEN")
    if not token:
        print("HOME_ASSISTANT_TOKEN is not set (looked in .env)", file=sys.stderr)
        return 1

    for auto_id, body in automations().items():
        print(f"\n{auto_id}  ({body['alias']})")
        for condition in body["conditions"]:
            if condition.get("condition") == "template":
                print(f"    template: {condition['value_template']}")
        if not args.apply:
            continue
        try:
            install(args.base_url, token, auto_id, body)
        except urllib.error.HTTPError as exc:
            # 400 here is Home Assistant's own validator, and its message says
            # exactly what is wrong with the automation.
            print(f"    REFUSED {exc.code}: {exc.read().decode('utf-8', 'replace')[:400]}",
                  file=sys.stderr)
            return 1
        except OSError as exc:
            print(f"    could not reach Home Assistant at {args.base_url}: {exc}",
                  file=sys.stderr)
            return 1
        print("    installed (Home Assistant validated it and reloaded automations)")

    if not args.apply:
        print("\nNothing was written. Re-run with --apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
