#!/usr/bin/env python3
"""Install what the house does while the alarm is armed (asked for 2026-09-24):
the alarm speaker for an unexpected person on the first floor, and the bedroom
smart button - once to stop the speaker, twice for Night arm.

The intruder rule
-----------------
While the alarm is armed (any armed state), a first-floor PIR or an indoor
camera's NPU person detection sets off the Zigbee alarm speaker for
SIREN_SECONDS, unless the person is *expected*. What set it off goes into
input_text.security_alarm_reason, which the dashboard shows beside a Stop
button (Security view and a banner).

"Expected" exists because the alarm is armed at night with people asleep
upstairs - and not only by our Night arm: the alarm itself is armed away at
01:30 and disarmed at 07:00 every day by a schedule outside Home Assistant
(seen in the house memory 2026-09-22 to 09-24, most likely the Smart Life
app). So the arm type says nothing about whether anyone is home; the house
mode does:

  * Away or Vacation: nobody is home, so anyone on the first floor is unexpected.
  * Home: someone who comes down the stairs (the upstairs sensor saw them in
    the last 3 minutes), or who was already downstairs when the alarm armed, is
    expected - and stays expected for 30 minutes after their last movement on
    the first floor (input_datetime.security_expected_until). Someone up late
    or fetching water at 3 AM does not set it off; the cost is that an
    intruder within 30 minutes of the household's last movement downstairs
    does not either.

Not for the first ARM_GRACE_S after arming - the exit, and the Tuya panel's own
arming delay. The radar (mmWave) sensors are not used: they hold "occupied"
for half an hour on nothing, and a false siren at 3 AM is the worst outcome
this rule can have.

The bedroom button
------------------
event.smart_button_bedroom_action: single press stops the alarm speaker if it
is sounding; double press runs Night arm (the house_mode_night_arm rule from
install-house-modes.py, conditions skipped). The two automations that used the
button for the master bedroom light (npu_bedroom_button_single_on /
npu_bedroom_button_double_off) are deleted by --apply; their bodies are
printed first so nothing is lost.

    python3 scripts/install-security-response.py            # show it
    python3 scripts/install-security-response.py --apply    # install (on the board)
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

ALARM = "alarm_control_panel.duo_gong_neng_bao_jing_zhu_ji"
ARMED = ["armed_home", "armed_away", "armed_night", "armed_vacation", "armed_custom_bypass"]
SPEAKER = "switch.0xa4c1382b1f1bd155_alarm"            # Zigbee alarm speaker, living room
SPEAKER_DURATION = "number.0xa4c1382b1f1bd155_duration"
SIREN_SECONDS = 300                                     # the device takes up to 1800
REASON = "input_text.security_alarm_reason"
EXPECTED_UNTIL = "input_datetime.security_expected_until"
MODE = "input_select.house_mode"                        # install-house-modes.py
NIGHT_ARM_RULE_ID = "house_mode_night_arm"
BUTTON = "event.smart_button_bedroom_action"
OLD_BUTTON_RULES = ["npu_bedroom_button_single_on", "npu_bedroom_button_double_off"]

UPSTAIRS = "binary_sensor.0xa4c138ae6a275f0f_presence"  # Motion sensor and TH Upstairs (the stairs)
FIRST_FLOOR_PIR = [
    "binary_sensor.0xa4c1381f2015da50_presence",   # Living room
    "binary_sensor.0xa4c138d00106c90d_presence",   # Kitchen and family room
    "binary_sensor.0xa4c138351a615a3c_presence",   # Entry
    "binary_sensor.0xa4c138257e0d2173_presence",   # Downstairs, by the front door
]
INDOOR_CAMERAS = [
    "binary_sensor.family_room_camera_npu_person",
    "binary_sensor.office_camera_npu_person",
]
FIRST_FLOOR = FIRST_FLOOR_PIR + INDOOR_CAMERAS

CAME_DOWN_S = 180
EXPECTED_FOR_MIN = 30
ARM_GRACE_S = 120
# At arming, the first floor counts as occupied if anything there moved this recently.
OCCUPIED_AT_ARMING_S = 900


def _came_down() -> str:
    """The upstairs sensor saw someone in the last CAME_DOWN_S. Subscript form:
    these ids start with a digit, and states.binary_sensor.0x... is a syntax error."""
    return ("{% set up = states['" + UPSTAIRS + "'] %}"
            "{{ up is not none and (up.state == 'on' or "
            "(now() - up.last_changed).total_seconds() < " + str(CAME_DOWN_S) + ") }}")


def _still_expected() -> str:
    return ("{% set until = state_attr('" + EXPECTED_UNTIL + "', 'timestamp') %}"
            "{{ until is not none and now().timestamp() < until }}")


def _armed_long_enough() -> str:
    return ("{% set alarm = states['" + ALARM + "'] %}"
            "{{ alarm is not none and (now() - alarm.last_changed).total_seconds() > "
            + str(ARM_GRACE_S) + " }}")


def _first_floor_recently_active() -> str:
    ids = ", ".join(f"'{e}'" for e in FIRST_FLOOR)
    return ("{% set ns = namespace(active=false) %}"
            "{% for id in [" + ids + "] %}{% set s = states[id] %}"
            "{% if s is not none and (s.state == 'on' or (now() - s.last_changed).total_seconds() < "
            + str(OCCUPIED_AT_ARMING_S) + ") %}{% set ns.active = true %}{% endif %}{% endfor %}"
            "{{ ns.active }}")


def expect_for_a_while() -> dict:
    return {"action": "input_datetime.set_datetime", "target": {"entity_id": EXPECTED_UNTIL},
            "data": {"timestamp": "{{ now().timestamp() + " + str(EXPECTED_FOR_MIN * 60) + " }}"}}


def home_mode() -> dict:
    return {"condition": "state", "entity_id": MODE, "state": "Home"}


def _desc(text: str) -> str:
    return f"{text} Installed by scripts/install-security-response.py."


def _button(gesture: str) -> list[dict]:
    """Trigger on the event entity's state (a timestamp, new on every press) and
    check the gesture as a condition: filtering on the attribute would miss a
    repeated identical press, because the attribute would not change."""
    return [{"trigger": "state", "entity_id": BUTTON, "not_to": ["unavailable", "unknown"]}], \
        [{"condition": "state", "entity_id": BUTTON, "attribute": "event_type", "state": gesture}]


def automations() -> list[dict]:
    single_triggers, single_conditions = _button("single")
    double_triggers, double_conditions = _button("double")
    return [
        {
            "id": "security_intruder_siren",
            "alias": "Security - alarm speaker for an unexpected person downstairs",
            "description": _desc(
                "While armed: a first-floor PIR or indoor camera person sets off the alarm speaker "
                f"for {SIREN_SECONDS} s, unless expected - on Home, someone who came down the stairs or "
                f"was downstairs at arming, for {EXPECTED_FOR_MIN} min after their last movement there. "
                "On Away or Vacation anyone is unexpected."),
            "mode": "single",
            "triggers": [{"trigger": "state", "entity_id": FIRST_FLOOR, "from": "off", "to": "on"}],
            "conditions": [
                {"condition": "state", "entity_id": ALARM, "state": ARMED},
                {"condition": "template", "value_template": _armed_long_enough()},
            ],
            "actions": [{"choose": [
                {
                    "alias": "Expected: the household, downstairs. Keep them expected.",
                    "conditions": [home_mode(), {"condition": "or", "conditions": [
                        {"condition": "template", "value_template": _came_down()},
                        {"condition": "template", "value_template": _still_expected()},
                    ]}],
                    "sequence": [expect_for_a_while()],
                },
            ], "default": [
                {"action": "input_text.set_value", "target": {"entity_id": REASON},
                 "data": {"value": "{{ trigger.to_state.name }} · {{ now().strftime('%H:%M') }}"}},
                {"action": "number.set_value", "target": {"entity_id": SPEAKER_DURATION},
                 "data": {"value": SIREN_SECONDS}, "continue_on_error": True},
                {"if": [{"condition": "state", "entity_id": SPEAKER, "state": "off"}],
                 "then": [{"action": "switch.turn_on", "target": {"entity_id": SPEAKER}}]},
            ]}],
        },
        {
            "id": "security_expected_at_arming",
            "alias": "Security - whoever is downstairs at arming is expected",
            "description": _desc(
                "When the alarm arms with the house mode Home and anything on the first floor moved in "
                f"the last {OCCUPIED_AT_ARMING_S // 60} minutes, that person is expected for "
                f"{EXPECTED_FOR_MIN} minutes - the alarm's own 01:30 schedule arms it on people up late."),
            "mode": "single",
            "triggers": [{"trigger": "state", "entity_id": ALARM, "to": ARMED}],
            "conditions": [home_mode(), {"condition": "template", "value_template": _first_floor_recently_active()}],
            "actions": [expect_for_a_while()],
        },
        {
            "id": "security_bedroom_button_stops_speaker",
            "alias": "Bedroom button single - stop the alarm speaker",
            "description": _desc("One press on the bedroom smart button stops the alarm speaker."),
            "mode": "single",
            "triggers": single_triggers,
            "conditions": single_conditions + [{"condition": "state", "entity_id": SPEAKER, "state": "on"}],
            "actions": [{"action": "switch.turn_off", "target": {"entity_id": SPEAKER}}],
        },
        {
            "id": "security_bedroom_button_night_arm",
            "alias": "Bedroom button double - Night arm",
            "description": _desc("Two presses on the bedroom smart button run Night arm now "
                                 "(house_mode_night_arm, its conditions skipped)."),
            "mode": "single",
            "triggers": double_triggers,
            "conditions": double_conditions,
            "actions": [{"action": "automation.trigger", "data": {"skip_condition": True},
                         "target": {"entity_id": "{{ states.automation | selectattr('attributes.id', "
                                                  "'defined') | selectattr('attributes.id', 'eq', '"
                                                  + NIGHT_ARM_RULE_ID + "') | map(attribute='entity_id') "
                                                  "| first }}"}}],
        },
    ]


HELPERS = [
    (REASON, {"type": "input_text/create", "name": "Security alarm reason", "max": 255,
              "icon": "mdi:alarm-light"}),
    (EXPECTED_UNTIL, {"type": "input_datetime/create", "name": "Security expected until",
                      "has_date": True, "has_time": True, "icon": "mdi:account-clock"}),
]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _exists(base_url: str, token: str, path: str) -> dict | None:
    try:
        with urllib.request.urlopen(urllib.request.Request(f"{base_url}{path}", headers=_headers(token)),
                                    timeout=15) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code in (400, 404):
            return None
        raise


def ensure_helpers(base_url: str, token: str) -> list[str]:
    missing = [(e, m) for e, m in HELPERS if _exists(base_url, token, f"/api/states/{e}") is None]
    if not missing:
        return []
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
    return [e for e, _ in missing]


def remove_old_button_rules(base_url: str, token: str) -> list[tuple[str, dict]]:
    """Delete the light automations that used the bedroom button. Returns what was deleted."""
    removed = []
    for rule_id in OLD_BUTTON_RULES:
        body = _exists(base_url, token, f"/api/config/automation/config/{rule_id}")
        if body is None:
            continue
        request = urllib.request.Request(f"{base_url}/api/config/automation/config/{rule_id}",
                                         headers=_headers(token), method="DELETE")
        with urllib.request.urlopen(request, timeout=30) as response:
            response.read()
        removed.append((rule_id, body))
    return removed


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
        f"{base_url}/api/config/automation/config/{body['id']}",
        data=json.dumps(body).encode("utf-8"), headers=_headers(token), method="POST")
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
        print(f"\nNothing was written. Re-run with --apply (it also deletes {', '.join(OLD_BUTTON_RULES)}).")
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
            print(f"installed automation {body['id']}")
        for rule_id, body in remove_old_button_rules(base_url, token):
            print(f"deleted automation {rule_id}; it was:\n{json.dumps(body)}")
    except urllib.error.HTTPError as exc:
        print(f"REFUSED {exc.code}: {exc.read().decode('utf-8', 'replace')[:400]}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"could not reach Home Assistant at {base_url}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
