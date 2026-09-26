#!/usr/bin/env python3
"""Install the house modes in Home Assistant: Away, Home again, Vacation, and
the alarm's night arming and morning disarming (asked for 2026-09-24).

One helper holds the mode, `input_select.house_mode`: Home, Away or Vacation.
Presence decides it, and so can a person, in Home Assistant, by picking one.
What happens is tied to the *change of mode*, not to how it changed, so picking
Vacation by hand before a trip does exactly what 24 hours away would.

    Away        Every tracked phone is out of the home zone (zone.home = 0)
                AND no indoor motion or occupancy sensor has seen anyone for
                15 minutes. The phones alone are not enough: only one phone is
                tracked, and anyone at home without one would have their lights
                turned off. The owner chose this (2026-09-24).
                Since 2026-09-25 the garage camera can stand in for the phones
                (OR): the car leaving the driveway, or someone walking out past
                the garage, counts as "someone just left" for 30 minutes - and
                the house must still be still for 15. The camera cannot tell who
                left, which is why the stillness stays. WATCH-ONLY until
                input_boolean.house_camera_signals is turned on: until then it
                only writes what it would have done to
                input_text.house_camera_would_have (and the logbook).
                -> All lights off (script.panel_all_lights_off, which follows
                   Manage). Between sunset and 23:30 the living room light is
                   then turned back on, and while away it goes on at sunset and
                   off at 23:30 every evening, so the house looks lived in.
    Home again  Away or Vacation, and a phone enters the home zone - or, when
                only Away and for 10 minutes at least, indoor motion (the PIR
                sensors only: the radar ones can hold "occupied" for half an
                hour on nothing; and a fresh Away was likely picked by hand on
                the way out, past the entry sensor).
                Also (same watch-only switch): a car parking in the empty
                driveway, when Away for 10 minutes at least. Never a Vacation:
                ending one disarms the alarm, and any car can pull in.
                -> Ambient lights on, only those that are off and only when the
                   sun is down. Mode back to Home.
    Vacation    Away for 24 hours (checked every 10 minutes against
                input_datetime.house_away_since, which survives a restart where
                a trigger's "for" does not), or picked by hand.
                -> What Away does, plus the alarm armed away and an ecobee
                   vacation (15 C heat, 28 C cool, 60 days; deleted on return).
    Back from   Vacation -> Home, by arrival or by hand: the alarm is disarmed if
    vacation    it is armed away, and the ecobee vacation deleted. Disarming on
                the phone's arrival was the owner's choice (2026-09-24); without
                it, opening the door sets the alarm off.
    Night arm   From 01:30, once no first-floor sensor has seen anyone for 15
                minutes, the alarm is armed home (the panel has no night mode).
                Not on Vacation, which is armed away already. The family room
                radar holds "occupied" ~30 min after the last movement, so on a
                late night this arms at ~02:00 rather than at 01:30.
    Morning     07:00: disarmed, if armed home and not on Vacation.

The owner's rule holds throughout: nothing sends "on" to a light that is on.

Written through Home Assistant's config API, like the other installers: its
validator runs first and automations are reloaded. The Zigbee ids start with a
digit, so they appear only as entity_id values, never as states.binary_sensor.0x...

    python3 scripts/install-house-modes.py            # show it
    python3 scripts/install-house-modes.py --apply    # install (on the board)
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

MODE = "input_select.house_mode"
HOME, AWAY, VACATION = "Home", "Away", "Vacation"
AWAY_SINCE = "input_datetime.house_away_since"

PEOPLE_HOME = "zone.home"              # how many person.* are in the home zone
ALARM = "alarm_control_panel.duo_gong_neng_bao_jing_zhu_ji"
ECOBEE = "climate.my_ecobee_2"         # the cloud integration: it has the vacation service
ALL_LIGHTS_OFF = "script.panel_all_lights_off"
LIVING_ROOM = "light.living_room_living_room_switch_2"

# Indoor PIR sensors (Tuya, "presence" in z2m's naming, but they are PIR).
PIR_FIRST_FLOOR = [
    "binary_sensor.0xa4c1381f2015da50_presence",   # Living room
    "binary_sensor.0xa4c138d00106c90d_presence",   # Kitchen and family room
    "binary_sensor.0xa4c138351a615a3c_presence",   # Entry
    "binary_sensor.0xa4c138257e0d2173_presence",   # Downstairs, by the front door (illumination)
]
PIR_UPSTAIRS = [
    "binary_sensor.0xa4c138ae6a275f0f_presence",   # Upstairs
    "binary_sensor.0xa4c13805646b3a80_presence",   # Bedroom
]
# Radar (mmWave) occupancy: sees someone sitting still, but holds "on" long after.
RADAR_FIRST_FLOOR = ["binary_sensor.8jt7_occupancy"]   # Family room
RADAR_UPSTAIRS = ["binary_sensor.8k2g_occupancy"]      # Master bedroom
# Not used: front door TH, backyard and fence south are outdoors.

FIRST_FLOOR = PIR_FIRST_FLOOR + RADAR_FIRST_FLOOR
INDOOR = FIRST_FLOOR + PIR_UPSTAIRS + RADAR_UPSTAIRS
ARRIVAL_MOTION = PIR_FIRST_FLOOR + PIR_UPSTAIRS

AMBIENT_LIGHTS = [
    "light.h6076",                      # Living room ambient light (Govee)
    "switch.living_room_cabinet_led",
    "light.family_room_led",
    "light.0x286847fffe5eb711",         # IKEA cabinet LED upper
    "light.0x64028ffffe64de32",         # IKEA cabinet LED lower
    "switch.family_room_cabinet_led",
]

# The garage camera (npu-detector: NPU_CLASSES=person,car, NPU_INWARD=garage_camera=y+).
GARAGE_CAR = "binary_sensor.garage_camera_npu_car"                 # a car parked in the driveway
GARAGE_WALKING = "sensor.garage_camera_npu_person_direction"       # inward / outward / still
LEFT_AT = "input_datetime.house_left_seen"        # when the camera last saw someone leave
LEFT_HOW = "input_text.house_left_how"            # how - and "" once it has been acted on
CAMERA_LIVE = "input_boolean.house_camera_signals"  # off: watch-only
WOULD_HAVE = "input_text.house_camera_would_have"   # what watch-only would have done
CAR_PARKED_S = 600      # a car must have been parked this long before its leaving counts
CAR_GONE_S = 300        # and the driveway empty this long before a car's arrival counts
LEFT_RECENTLY_S = 1800  # "someone just left" lasts this long

EMPTY_FOR = {"minutes": 15}
PHONES_GONE_FOR = {"minutes": 5}
VACATION_AFTER_HOURS = 24
MOTION_ENDS_AWAY_AFTER_S = 600
EVENING_OFF = "23:30:00"
NIGHT_ARM_AT = "01:30:00"
NIGHT_ARM_UNTIL = "06:30:00"
MORNING_DISARM_AT = "07:00:00"
VACATION_HEAT_C = 15
VACATION_COOL_C = 28
VACATION_DAYS = 60
VACATION_NAME = "House vacation"
# A sensor that has dropped off Zigbee must not keep the house "occupied" for ever.
QUIET = ["off", "unavailable", "unknown"]


def turn_on_if_off(entity_id: str) -> dict:
    """Turn one light or switch on only when it is off. Never send "on" to a
    light that is already on: some re-apply their level and flash."""
    domain = entity_id.split(".", 1)[0]
    return {
        "alias": f"{entity_id} on, if off",
        "if": [{"condition": "state", "entity_id": entity_id, "state": "off"}],
        "then": [{"action": f"{domain}.turn_on", "target": {"entity_id": entity_id}}],
    }


def set_mode(option: str) -> dict:
    return {"action": "input_select.select_option", "target": {"entity_id": MODE},
            "data": {"option": option}}


def mode_is(*options: str) -> dict:
    return {"condition": "state", "entity_id": MODE, "state": list(options)}


def nobody_home() -> dict:
    return {"condition": "numeric_state", "entity_id": PEOPLE_HOME, "below": 1}


def still(entities: list[str]) -> dict:
    """Every one of them quiet for the whole EMPTY_FOR."""
    return {"condition": "state", "entity_id": entities, "state": QUIET, "for": EMPTY_FOR}


def living_room_evening() -> dict:
    """Sunset to 23:30. "After sunset" alone runs until midnight."""
    return {"condition": "and", "conditions": [
        {"condition": "sun", "after": "sunset"},
        {"condition": "time", "before": EVENING_OFF},
    ]}


def dark() -> dict:
    return {"condition": "or", "conditions": [
        {"condition": "sun", "after": "sunset"},
        {"condition": "sun", "before": "sunrise"},
    ]}


def away_for(seconds: int) -> dict:
    """The house has been left at least this long, by the helper's own timestamp
    attribute: no parsing, none if never set, and it survives a restart where a
    trigger's "for" does not."""
    return {"condition": "template", "value_template": (
        "{% set since = state_attr('" + AWAY_SINCE + "', 'timestamp') %}"
        "{{ since is not none and now().timestamp() - since > " + str(seconds) + " }}")}


def held_for(seconds: int) -> dict:
    """The sensor had been in its previous state at least this long - a car that
    was parked, not one turning round in the driveway."""
    return {"condition": "template", "value_template": (
        "{{ (trigger.to_state.last_changed - trigger.from_state.last_changed).total_seconds() > "
        + str(seconds) + " }}")}


def left_recently() -> dict:
    """The camera saw someone leave in the last 30 minutes, and that has not been
    acted on yet."""
    return {"condition": "template", "value_template": (
        "{% set at = state_attr('" + LEFT_AT + "', 'timestamp') %}"
        "{{ at is not none and now().timestamp() - at < " + str(LEFT_RECENTLY_S)
        + " and states('" + LEFT_HOW + "') not in ['', 'unknown', 'unavailable'] }}")}


def record_leaving(how: str) -> list[dict]:
    return [
        {"action": "input_datetime.set_datetime", "target": {"entity_id": LEFT_AT},
         "data": {"timestamp": "{{ now().timestamp() }}"}},
        {"action": "input_text.set_value", "target": {"entity_id": LEFT_HOW}, "data": {"value": how}},
    ]


def camera_decides(option: str, why: str) -> dict:
    """Live: change the mode. Watch-only: write down what would have happened."""
    said = "{{ now().strftime('%a %H:%M') }} " + option + " - " + why
    return {"if": [{"condition": "state", "entity_id": CAMERA_LIVE, "state": "on"}],
            "then": [set_mode(option),
                     {"action": "logbook.log", "data": {"name": "House mode", "message": option + ": " + why,
                                                        "entity_id": MODE}}],
            "else": [{"action": "input_text.set_value", "target": {"entity_id": WOULD_HAVE},
                      "data": {"value": said}},
                     {"action": "logbook.log", "data": {"name": "House mode (watch-only)",
                                                        "message": "would have gone " + option + ": " + why,
                                                        "entity_id": MODE}}]}


def _desc(text: str) -> str:
    return f"{text} Installed by scripts/install-house-modes.py."


def automations() -> list[dict]:
    return [
        {
            "id": "house_mode_goes_away",
            "alias": "House mode - Away when the phones are gone and the house is still",
            "description": _desc("Every tracked phone out of the home zone and no indoor sensor "
                                 "seeing anyone for 15 minutes: the mode becomes Away."),
            "mode": "single",
            "triggers": [
                {"trigger": "numeric_state", "entity_id": PEOPLE_HOME, "below": 1, "for": PHONES_GONE_FOR},
                {"trigger": "state", "entity_id": INDOOR, "to": "off", "for": EMPTY_FOR},
            ],
            "conditions": [mode_is(HOME), nobody_home(), still(INDOOR)],
            "actions": [set_mode(AWAY)],
        },
        {
            "id": "house_mode_left_by_car",
            "alias": "House mode - the car left the driveway",
            "description": _desc("The garage camera's car sensor goes from parked (10 minutes at "
                                 "least) to an empty driveway: someone just left."),
            "mode": "single",
            "triggers": [{"trigger": "state", "entity_id": GARAGE_CAR, "from": "on", "to": "off"}],
            "conditions": [mode_is(HOME), held_for(CAR_PARKED_S)],
            "actions": record_leaving("the car left the driveway"),
        },
        {
            "id": "house_mode_left_on_foot",
            "alias": "House mode - someone walked out past the garage",
            "description": _desc("The garage camera sees a person walking away from the house, "
                                 "towards the street: someone just left."),
            "mode": "single",
            "triggers": [{"trigger": "state", "entity_id": GARAGE_WALKING, "to": "outward"}],
            "conditions": [mode_is(HOME)],
            "actions": record_leaving("someone walked out past the garage"),
        },
        {
            "id": "house_mode_away_by_camera",
            "alias": "House mode - Away when the camera saw us leave and the house is still",
            "description": _desc("OR with the phones: the garage camera saw someone leave in the "
                                 "last 30 minutes AND no indoor sensor has seen anyone for 15. "
                                 "Watch-only until input_boolean.house_camera_signals is on."),
            "mode": "single",
            "triggers": [
                {"trigger": "state", "entity_id": LEFT_AT},
                {"trigger": "state", "entity_id": INDOOR, "to": "off", "for": EMPTY_FOR},
                # "for" does not survive a restart; this does.
                {"trigger": "time_pattern", "minutes": "/5"},
            ],
            "conditions": [mode_is(HOME), left_recently(), still(INDOOR)],
            "actions": [
                {"variables": {"why": "{{ states('" + LEFT_HOW + "') }}"}},
                # Acted on: the same leaving must not decide again in 5 minutes.
                {"action": "input_text.set_value", "target": {"entity_id": LEFT_HOW}, "data": {"value": ""}},
                camera_decides(AWAY, "{{ why }}"),
            ],
        },
        {
            "id": "house_mode_leaving",
            "alias": "House mode - leaving: lights off, living room on in the evening",
            "description": _desc("Home -> Away or Vacation: all lights off, then the living room "
                                 "light back on if it is between sunset and 23:30. Records when the "
                                 "house was left, for the 24-hour Vacation rule."),
            "mode": "single",
            "triggers": [{"trigger": "state", "entity_id": MODE, "from": HOME, "to": [AWAY, VACATION]}],
            "actions": [
                {"action": "input_datetime.set_datetime", "target": {"entity_id": AWAY_SINCE},
                 "data": {"timestamp": "{{ now().timestamp() }}"}},
                {"action": ALL_LIGHTS_OFF},
                {"if": [living_room_evening()], "then": [turn_on_if_off(LIVING_ROOM)]},
            ],
        },
        {
            "id": "house_mode_away_evening_light",
            "alias": "House mode - away: living room light from sunset to 23:30",
            "description": _desc("While Away or on Vacation, the living room light goes on at "
                                 "sunset and off at 23:30, so the house looks lived in."),
            "mode": "single",
            "triggers": [
                {"trigger": "sun", "event": "sunset", "id": "on"},
                {"trigger": "time", "at": EVENING_OFF, "id": "off"},
            ],
            "conditions": [mode_is(AWAY, VACATION)],
            "actions": [{"choose": [
                {"conditions": [{"condition": "trigger", "id": "on"}],
                 "sequence": [turn_on_if_off(LIVING_ROOM)]},
                {"conditions": [{"condition": "trigger", "id": "off"},
                                {"condition": "state", "entity_id": LIVING_ROOM, "state": "on"}],
                 "sequence": [{"action": "light.turn_off", "target": {"entity_id": LIVING_ROOM}}]},
            ]}],
        },
        {
            "id": "house_mode_becomes_vacation",
            "alias": "House mode - Vacation after 24 hours away",
            "description": _desc("Away for 24 hours becomes Vacation. Checked every 10 minutes "
                                 "against input_datetime.house_away_since, which survives a restart."),
            "mode": "single",
            "triggers": [{"trigger": "time_pattern", "minutes": "/10"}],
            "conditions": [
                mode_is(AWAY),
                away_for(VACATION_AFTER_HOURS * 3600),
            ],
            "actions": [set_mode(VACATION)],
        },
        {
            "id": "house_mode_vacation_starts",
            "alias": "House mode - Vacation: arm the alarm, ecobee on vacation",
            "description": _desc(f"On Vacation: the alarm armed away, and an ecobee vacation "
                                 f"({VACATION_HEAT_C} C heat, {VACATION_COOL_C} C cool, "
                                 f"{VACATION_DAYS} days; deleted on return)."),
            "mode": "single",
            "triggers": [{"trigger": "state", "entity_id": MODE, "to": VACATION}],
            "actions": [
                {"if": [{"condition": "state", "entity_id": ALARM, "state": ["disarmed", "armed_home"]}],
                 "then": [{"action": "alarm_control_panel.alarm_arm_away", "target": {"entity_id": ALARM},
                           "continue_on_error": True}]},
                {"action": "ecobee.create_vacation", "continue_on_error": True, "data": {
                    "entity_id": ECOBEE, "vacation_name": VACATION_NAME,
                    "heat_temp": VACATION_HEAT_C, "cool_temp": VACATION_COOL_C,
                    "start_date": "{{ now().strftime('%Y-%m-%d') }}",
                    "start_time": "{{ now().strftime('%H:%M:%S') }}",
                    "end_date": "{{ (now() + timedelta(days=" + str(VACATION_DAYS) + ")).strftime('%Y-%m-%d') }}",
                    "end_time": "23:59:00",
                }},
            ],
        },
        {
            "id": "house_mode_vacation_ends",
            "alias": "House mode - back from Vacation: disarm, ecobee vacation off",
            "description": _desc("Vacation -> Home, by arrival or by hand: disarm if armed away "
                                 "(the owner's choice - otherwise the door sets it off), and delete "
                                 "the ecobee vacation."),
            "mode": "single",
            "triggers": [{"trigger": "state", "entity_id": MODE, "from": VACATION, "to": HOME}],
            "actions": [
                {"if": [{"condition": "state", "entity_id": ALARM, "state": "armed_away"}],
                 "then": [{"action": "alarm_control_panel.alarm_disarm", "target": {"entity_id": ALARM},
                           "continue_on_error": True}]},
                {"action": "ecobee.delete_vacation", "continue_on_error": True,
                 "data": {"entity_id": ECOBEE, "vacation_name": VACATION_NAME}},
            ],
        },
        {
            "id": "house_mode_arrival",
            "alias": "House mode - first person home",
            "description": _desc("Away or Vacation, and a phone enters the home zone (or, when "
                                 "only Away and for 10 minutes at least, a PIR sensor sees "
                                 "someone): the mode becomes Home. What Home does is "
                                 "house_mode_coming_home, so picking Home by hand does the same."),
            "mode": "single",
            "triggers": [
                {"trigger": "numeric_state", "entity_id": PEOPLE_HOME, "above": 0, "id": "phone"},
                {"trigger": "state", "entity_id": ARRIVAL_MOTION, "from": "off", "to": "on", "id": "motion"},
            ],
            "conditions": [
                mode_is(AWAY, VACATION),
                # Motion alone never ends a Vacation: on an armed house that is the
                # alarm's business. Nor a fresh Away: picked by hand on the way out,
                # the entry sensor would see you reach the door and undo it.
                {"condition": "or", "conditions": [
                    {"condition": "trigger", "id": "phone"},
                    {"condition": "and", "conditions": [mode_is(AWAY), away_for(MOTION_ENDS_AWAY_AFTER_S)]},
                ]},
            ],
            "actions": [set_mode(HOME)],
        },
        {
            "id": "house_mode_home_by_car",
            "alias": "House mode - a car parked in the empty driveway",
            "description": _desc("Away for 10 minutes at least, and a car parks in a driveway that "
                                 "was empty for 5: the mode becomes Home. Never ends a Vacation - "
                                 "that disarms the alarm, and any car can pull in. Watch-only until "
                                 "input_boolean.house_camera_signals is on."),
            "mode": "single",
            "triggers": [{"trigger": "state", "entity_id": GARAGE_CAR, "from": "off", "to": "on"}],
            "conditions": [mode_is(AWAY), away_for(MOTION_ENDS_AWAY_AFTER_S), held_for(CAR_GONE_S)],
            "actions": [camera_decides(HOME, "a car parked in the driveway")],
        },
        {
            "id": "house_mode_coming_home",
            "alias": "House mode - home again: ambient lights on in the dark",
            "description": _desc("Away or Vacation -> Home, by arrival or by hand: the ambient "
                                 "lights that are off go on if the sun is down."),
            "mode": "single",
            "triggers": [{"trigger": "state", "entity_id": MODE, "from": [AWAY, VACATION], "to": HOME}],
            "conditions": [dark()],
            "actions": [turn_on_if_off(e) for e in AMBIENT_LIGHTS],
        },
        {
            "id": "house_mode_night_arm",
            "alias": "Security - arm at night once the first floor is empty",
            "description": _desc("From 01:30 until 06:30, once no first-floor sensor has seen anyone "
                                 "for 15 minutes, arm the alarm home. Not on Vacation."),
            "mode": "single",
            "triggers": [
                {"trigger": "time", "at": NIGHT_ARM_AT},
                {"trigger": "state", "entity_id": FIRST_FLOOR, "to": "off", "for": EMPTY_FOR},
            ],
            "conditions": [
                {"condition": "time", "after": NIGHT_ARM_AT, "before": NIGHT_ARM_UNTIL},
                {"condition": "not", "conditions": [mode_is(VACATION)]},
                {"condition": "state", "entity_id": ALARM, "state": "disarmed"},
                still(FIRST_FLOOR),
            ],
            "actions": [{"action": "alarm_control_panel.alarm_arm_home", "target": {"entity_id": ALARM}}],
        },
        {
            "id": "house_mode_morning_disarm",
            "alias": "Security - disarm at 07:00",
            "description": _desc("At 07:00, disarm the alarm if it is armed home. Never on Vacation."),
            "mode": "single",
            "triggers": [{"trigger": "time", "at": MORNING_DISARM_AT}],
            "conditions": [
                {"condition": "state", "entity_id": ALARM, "state": "armed_home"},
                {"condition": "not", "conditions": [mode_is(VACATION)]},
            ],
            "actions": [{"action": "alarm_control_panel.alarm_disarm", "target": {"entity_id": ALARM}}],
        },
    ]


HELPERS = [
    (MODE, {"type": "input_select/create", "name": "House mode", "options": [HOME, AWAY, VACATION],
            "initial": HOME, "icon": "mdi:home-account"}),
    (AWAY_SINCE, {"type": "input_datetime/create", "name": "House away since",
                  "has_date": True, "has_time": True, "icon": "mdi:home-export-outline"}),
    (LEFT_AT, {"type": "input_datetime/create", "name": "House left seen",
               "has_date": True, "has_time": True, "icon": "mdi:exit-run"}),
    (LEFT_HOW, {"type": "input_text/create", "name": "House left how", "max": 100, "icon": "mdi:exit-run"}),
    (WOULD_HAVE, {"type": "input_text/create", "name": "House camera would have", "max": 200,
                  "icon": "mdi:eye-outline"}),
    # Created off: the camera signals start watch-only (the owner's choice, 2026-09-25).
    (CAMERA_LIVE, {"type": "input_boolean/create", "name": "House camera signals", "icon": "mdi:cctv"}),
]


def ensure_helpers(base_url: str, token: str) -> list[str]:
    """Create the helpers that are missing. Returns what was created."""
    headers = {"Authorization": f"Bearer {token}"}
    missing = []
    for entity_id, message in HELPERS:
        try:
            with urllib.request.urlopen(urllib.request.Request(f"{base_url}/api/states/{entity_id}",
                                                               headers=headers), timeout=15):
                pass
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
            missing.append((entity_id, message))
    if not missing:
        return []
    # Helpers are created over the websocket API only; aiohttp is in the board's .venv.
    import asyncio
    import aiohttp

    async def create() -> None:
        ws_url = base_url.replace("http", "ws", 1) + "/api/websocket"
        async with aiohttp.ClientSession() as session, session.ws_connect(ws_url) as ws:
            await ws.receive_json()
            await ws.send_json({"type": "auth", "access_token": token})
            await ws.receive_json()
            for n, (entity_id, message) in enumerate(missing, start=1):
                await ws.send_json({"id": n, **message})
                reply = await ws.receive_json()
                if not reply.get("success"):
                    raise OSError(f"could not create {entity_id}: {reply.get('error')}")

    asyncio.run(create())
    return [entity_id for entity_id, _ in missing]


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def install(base_url: str, token: str, body: dict) -> None:
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/config/automation/config/{body['id']}",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        response.read()


def main(argv: list[str] | None = None) -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="without this, nothing is changed")
    ap.add_argument("--base-url", default=os.getenv("HOME_ASSISTANT_BASE_URL", "http://127.0.0.1:8123"))
    args = ap.parse_args(argv)

    bodies = automations()
    print(json.dumps(bodies, indent=2))
    if not args.apply:
        print("\nNothing was written. Re-run with --apply.")
        return 0
    token = os.getenv("HOME_ASSISTANT_TOKEN")
    if not token:
        print("HOME_ASSISTANT_TOKEN is not set (looked in .env)", file=sys.stderr)
        return 1
    base_url = args.base_url.rstrip("/")
    try:
        for entity_id in ensure_helpers(base_url, token):
            print(f"created helper {entity_id}")
        for body in bodies:
            install(base_url, token, body)
            print(f"installed automation {body['id']} (Home Assistant validated it and reloaded automations)")
    except urllib.error.HTTPError as exc:
        print(f"REFUSED {exc.code}: {exc.read().decode('utf-8', 'replace')[:400]}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"could not reach Home Assistant at {base_url}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
