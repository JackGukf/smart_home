#!/usr/bin/env python3
"""Install the water-leak and smoke alerts, and the sensor-health warning
(asked for 2026-09-25): the dashboard, a critical iPhone push, and Telegram.

The sensors are listed once, in src/python/safety_sensors.py.

Leak and smoke
--------------
A sensor turning "on" runs script.water_leak_alert / script.smoke_alert, which
turns input_boolean.water_leak_alert / smoke_alert on (the dashboard's red
banner, on every screen) and sends a *critical* push - it sounds through the
mute switch and every Focus - naming where, plus Telegram. Then it reminds while
the alert stands and nobody has said "I know": leak every 10 minutes, smoke
every 3, a few times each.

Two things the house's own history (house memory, 2026-09-20) decided:

  * The Tuya WATER SENSOR stayed wet ~8 hours while flapping between "on" and
    "unavailable" about twenty times - the Tuya cloud dropping it. Each flap back
    is an unavailable -> on change, so an "unavailable -> on" does not alert again
    within 3 hours of this rule's last alert. off -> on always alerts.
  * The Zigbee detectors sit at "unknown" for days - sleepy devices report only
    on a change - so their first real report of smoke is unknown -> on. That
    always alerts: "unknown" is not "unavailable".

When every sensor of the kind reads dry/clear again, one "Dry again at 14:32" /
"Smoke cleared at 14:32" follows (replacing the alarm on the lock screen by its
tag). The banner stays until someone presses "I know" - on the push, or on any
dashboard screen - because a leak that has dried may still want looking at.

No siren and no lights: the detectors sound themselves, and a siren the house
sets off by itself at 3 AM is its own hazard. Say if you want either.

Sensor health
-------------
A leak or smoke sensor that dies says nothing, so the rule
safety_sensors_need_attention sends an ordinary push and Telegram listing each
sensor whose battery is under 20% (or says it is low), or that has been
unavailable for 6 hours - when one crosses the line, and again every morning at
10:00 until fixed (those three numbers, and the reminders above, are defaults:
Settings -> House rules changes them, src/python/house_settings.py). "unknown" does not count: that is how the Zigbee ones rest.

    python3 scripts/install-safety-alerts.py            # show it
    python3 scripts/install-safety-alerts.py --apply    # install (on the board)
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import urllib.error
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.python import safety_sensors  # noqa: E402
from src.python.house_settings import BY_KEY as SETTINGS, ha_value  # noqa: E402


def _door_alerts():
    """The Home Assistant plumbing (REST, websocket, Telegram targets, .env) lives
    in the door alerts installer: one copy, not two."""
    spec = importlib.util.spec_from_file_location("door_alerts", PROJECT_ROOT / "scripts" / "install-door-alerts.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_doors = _door_alerts()
PHONE = _doors.PHONE

# How far back an alert makes an "unavailable -> on" a flap rather than news.
FLAP_WINDOW_S = 3 * 3600
# Settings -> House rules (src/python/house_settings.py): read by the rules at run time.
LOW_BATTERY = ha_value("low_battery_pct")
UNAVAILABLE_H = ha_value("sensor_silent_h")
HEALTH_AT = SETTINGS["health_check_at"].entity            # a time trigger can take the helper itself
LOW_BATTERY_ENTITY = SETTINGS["low_battery_pct"].entity   # and so can a numeric_state threshold
HEALTH_TAG = "safety-sensors"

HAZARDS = {
    "water_leak": {
        "sensors": safety_sensors.LEAK,
        "flag": "input_boolean.water_leak_alert",
        "flag_name": "Water leak alert",
        "flag_icon": "mdi:water-alert",
        "alias": "Water leak",
        "title": "Water leak",
        "found": "Water at ",
        "still": "Still wet at ",
        "clear_title": "Dry again",
        "clear": "The leak sensors read dry at ",
        "emoji": "💧",
        "tag": "water-leak",
        "ack": "WATER_LEAK_ACK",
        "remind_min": "leak_remind_min",
        "reminders": "leak_reminders",
    },
    "smoke": {
        "sensors": safety_sensors.SMOKE,
        "flag": "input_boolean.smoke_alert",
        "flag_name": "Smoke alert",
        "flag_icon": "mdi:smoke-detector-alert",
        "alias": "Smoke",
        "title": "Smoke detected",
        "found": "Smoke in ",
        "still": "Still smoke in ",
        "clear_title": "Smoke cleared",
        "clear": "The smoke detectors are clear at ",
        "emoji": "🔥",
        "tag": "smoke",
        "ack": "SMOKE_ACK",
        "remind_min": "smoke_remind_min",
        "reminders": "smoke_reminders",
    },
}


def _places_map(sensors: dict[str, str]) -> str:
    """A Jinja dict literal. json.dumps keeps quotes and escapes right."""
    return json.dumps(sensors, ensure_ascii=False)


def places_now(sensors: dict[str, str], fallback: str) -> str:
    """Where it is wet (or smoky) right now, read at send time - so a second
    sensor joining in is named too. `fallback` covers a flap to unavailable in
    the moment between the trigger and the send."""
    return ("{% set places = " + _places_map(sensors) + " %}"
            "{% set ns = namespace(on=[]) %}"
            "{% for id in places %}{% if is_state(id, 'on') %}{% set ns.on = ns.on + [places[id]] %}"
            "{% endif %}{% endfor %}"
            "{{ ns.on | join(' and ') if ns.on else " + fallback + " }}")


def any_on(sensors: dict[str, str]) -> str:
    ids = ", ".join(f"'{e}'" for e in sensors)
    return "{{ [" + ids + "] | select('is_state', 'on') | list | count > 0 }}"


def none_on(sensors: dict[str, str]) -> str:
    ids = ", ".join(f"'{e}'" for e in sensors)
    return "{{ [" + ids + "] | select('is_state', 'on') | list | count == 0 }}"


def not_a_flap() -> str:
    """off -> on and unknown -> on always alert; unavailable -> on only when this
    rule has not alerted in FLAP_WINDOW_S (last_triggered survives restarts)."""
    return ("{{ trigger.from_state is none or trigger.from_state.state != 'unavailable' "
            "or this.attributes.last_triggered is none "
            "or (now() - this.attributes.last_triggered).total_seconds() > " + str(FLAP_WINDOW_S) + " }}")


def _critical_push(hazard: dict, title: str, message: str) -> dict:
    return {"action": PHONE, "continue_on_error": True, "data": {
        "title": title, "message": message,
        "data": {
            "tag": hazard["tag"],
            # Critical: sounds through the mute switch and Focus, at full volume.
            "push": {"sound": {"name": "default", "critical": 1, "volume": 1.0}},
            "actions": [{"action": hazard["ack"], "title": "I know"}],
        },
    }}


def _quiet_push(tag: str, title: str, message: str) -> dict:
    return {"action": PHONE, "continue_on_error": True,
            "data": {"title": title, "message": message, "data": {"tag": tag}}}


def _telegram(telegram: list[str], text: str) -> list[dict]:
    return _doors._telegram(telegram, text)


def script(key: str, telegram: list[str]) -> dict:
    hazard = HAZARDS[key]
    sensors = hazard["sensors"]
    first = hazard["found"] + places_now(sensors, "where") + "."
    minutes = "(" + ha_value(hazard["remind_min"]) + " | int)"
    count = "(" + ha_value(hazard["reminders"]) + " | int)"
    reminder = (hazard["still"] + places_now(sensors, "where")
                + " - {{ repeat.index * " + minutes + " }} minutes since the first message.")
    return {
        "alias": f"{hazard['alias']} alert",
        "description": (f"{hazard['title']}: {hazard['flag']} for the dashboard, a critical iPhone push and "
                        "Telegram, then reminders while it stands - how often and how many are on "
                        "Settings -> House rules. Installed by scripts/install-safety-alerts.py."),
        # A second sensor setting it off starts it again, so the message names both.
        "mode": "restart",
        "fields": {"where": {"description": "The sensor that set it off", "example": "the boiler"}},
        "sequence": [
            {"action": "input_boolean.turn_on", "target": {"entity_id": hazard["flag"]}},
            _critical_push(hazard, hazard["title"], first),
            *_telegram(telegram, hazard["emoji"] + " " + first),
            {"repeat": {
                "while": [
                    {"condition": "state", "entity_id": hazard["flag"], "state": "on"},
                    {"condition": "template",
                     "value_template": "{{ repeat.index <= " + count + " }}"},
                ],
                "sequence": [
                    {"wait_for_trigger": [{"trigger": "state", "entity_id": hazard["flag"], "to": "off"}],
                     "timeout": {"minutes": "{{ " + minutes + " }}"}, "continue_on_timeout": True},
                    {"if": [
                        {"condition": "state", "entity_id": hazard["flag"], "state": "on"},
                        {"condition": "template", "value_template": any_on(sensors)},
                    ], "then": [
                        _critical_push(hazard, hazard["title"], reminder),
                        *_telegram(telegram, hazard["emoji"] + " " + reminder),
                    ]},
                ],
            }},
        ],
    }


def automations(key: str, telegram: list[str]) -> list[dict]:
    hazard = HAZARDS[key]
    sensors = hazard["sensors"]
    script_id = f"script.{key}_alert"
    at = "{{ now().strftime('%H:%M') }}"
    return [
        {
            "id": f"{key}_detected",
            "alias": f"{hazard['alias']} - detected",
            "description": (f"Any {key.replace('_', ' ')} sensor turns on. An unavailable -> on within "
                            f"{FLAP_WINDOW_S // 3600} h of the last alert is a flap, not news. "
                            "Installed by scripts/install-safety-alerts.py."),
            "mode": "queued",
            "triggers": [{"trigger": "state", "entity_id": list(sensors), "to": "on"}],
            "conditions": [{"condition": "template", "value_template": not_a_flap()}],
            "actions": [{"action": "script.turn_on", "target": {"entity_id": script_id},
                         "data": {"variables": {
                             "where": "{{ " + _places_map(sensors) + "[trigger.entity_id] }}"}}}],
        },
        {
            "id": f"{key}_cleared",
            "alias": f"{hazard['alias']} - clear again",
            "description": ("Every sensor reads clear again while the alert stands: say so once. The banner "
                            "stays until \"I know\". Installed by scripts/install-safety-alerts.py."),
            "mode": "single",
            "triggers": [{"trigger": "state", "entity_id": list(sensors), "to": "off"}],
            "conditions": [
                {"condition": "state", "entity_id": hazard["flag"], "state": "on"},
                {"condition": "template", "value_template": none_on(sensors)},
                # Once per alert: not again for a sensor flapping off -> unavailable -> off.
                {"condition": "template", "value_template": (
                    "{{ this.attributes.last_triggered is none or this.attributes.last_triggered < "
                    "states['" + hazard["flag"] + "'].last_changed }}")},
            ],
            "actions": [
                _quiet_push(hazard["tag"], hazard["clear_title"], hazard["clear"] + at + "."),
                *_telegram(telegram, "✅ " + hazard["clear"] + at + "."),
            ],
        },
        {
            "id": f"{key}_acknowledged",
            "alias": f"{hazard['alias']} - acknowledged on the iPhone",
            "description": "\"I know\" on the push stops the reminders and clears the dashboard. "
                           "Installed by scripts/install-safety-alerts.py.",
            "mode": "single",
            "triggers": [{"trigger": "event", "event_type": "mobile_app_notification_action",
                          "event_data": {"action": hazard["ack"]}}],
            "actions": [{"action": "input_boolean.turn_off", "target": {"entity_id": hazard["flag"]}}],
        },
    ]


def health_problems() -> str:
    """One line per sensor that needs a person: a low battery, or unavailable 6 h."""
    batteries = _places_map(safety_sensors.BATTERIES)
    lows = _places_map(safety_sensors.BATTERY_LOW)
    watched = _places_map({**{e: "Leak sensor at " + p for e, p in safety_sensors.LEAK.items()},
                           **{e: "Smoke detector in " + p for e, p in safety_sensors.SMOKE.items()}})
    return ("{% set ns = namespace(out=[]) %}"
            "{% set batteries = " + batteries + " %}"
            "{% for id in batteries %}{% set level = states(id) | float(101) %}"
            "{% if level < " + LOW_BATTERY + " %}"
            "{% set ns.out = ns.out + [batteries[id] ~ ': battery ' ~ (level | round(0) | int) ~ '%'] %}"
            "{% endif %}{% endfor %}"
            "{% set lows = " + lows + " %}"
            "{% for id in lows %}{% if is_state(id, 'on') %}"
            "{% set ns.out = ns.out + [lows[id] ~ ': battery low'] %}{% endif %}{% endfor %}"
            "{% set watched = " + watched + " %}"
            "{% for id in watched %}{% set s = states[id] %}"
            "{% if s is not none and s.state == 'unavailable' and "
            "(now() - s.last_changed).total_seconds() > " + UNAVAILABLE_H + " * 3600 %}"
            "{% set ns.out = ns.out + [watched[id] ~ ': not reporting for ' ~ "
            "(((now() - s.last_changed).total_seconds() / 3600) | round(0) | int) ~ ' h'] %}"
            "{% endif %}{% endfor %}"
            "{{ ns.out | join('\\n') }}")


def health_automation(telegram: list[str]) -> dict:
    watched = list(safety_sensors.LEAK) + list(safety_sensors.SMOKE)
    return {
        "id": "safety_sensors_need_attention",
        "alias": "Safety sensors - need attention",
        "description": ("A leak or smoke sensor with a low battery (or saying low), or unavailable too long: "
                        "when it happens and every day at the check time until fixed - the three numbers are "
                        "on Settings -> House rules. Installed by scripts/install-safety-alerts.py."),
        "mode": "single",
        "triggers": [
            {"trigger": "numeric_state", "entity_id": list(safety_sensors.BATTERIES), "below": LOW_BATTERY_ENTITY},
            {"trigger": "state", "entity_id": list(safety_sensors.BATTERY_LOW), "to": "on"},
            {"trigger": "state", "entity_id": watched, "to": "unavailable",
             "for": {"hours": "{{ " + UNAVAILABLE_H + " | int }}"}},
            {"trigger": "time", "at": HEALTH_AT},
        ],
        "actions": [
            {"variables": {"problems": health_problems()}},
            {"condition": "template", "value_template": "{{ problems | trim != '' }}"},
            _quiet_push(HEALTH_TAG, "Safety sensor needs attention", "{{ problems }}"),
            *_telegram(telegram, "🔋 Safety sensor needs attention:\n{{ problems }}"),
        ],
    }


def ensure_helper(base_url: str, token: str, entity_id: str, name: str, icon: str) -> bool:
    try:
        _doors._request(base_url, token, f"/api/states/{entity_id}")
        return False
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
    reply = _doors._ws(base_url, token, [{"type": "input_boolean/create", "name": name, "icon": icon}])[0]
    if not reply.get("success"):
        raise OSError(f"could not create {entity_id}: {reply.get('error')}")
    created = (reply.get("result") or {}).get("id")
    if created and f"input_boolean.{created}" != entity_id:
        raise OSError(f"Home Assistant named the helper input_boolean.{created}, not {entity_id}")
    return True


def everything(telegram: list[str]) -> dict:
    return {
        "scripts": {f"{key}_alert": script(key, telegram) for key in HAZARDS},
        "automations": [a for key in HAZARDS for a in automations(key, telegram)] + [health_automation(telegram)],
    }


def main(argv: list[str] | None = None) -> int:
    _doors.load_dotenv(PROJECT_ROOT / ".env")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="without this, nothing is changed")
    ap.add_argument("--base-url", default=os.getenv("HOME_ASSISTANT_BASE_URL", "http://127.0.0.1:8123"))
    args = ap.parse_args(argv)
    base_url = args.base_url.rstrip("/")
    token = os.getenv("HOME_ASSISTANT_TOKEN")

    telegram: list[str] = []
    if args.apply:
        if not token:
            print("HOME_ASSISTANT_TOKEN is not set (looked in .env)", file=sys.stderr)
            return 1
        telegram = _doors.telegram_targets(base_url, token)
    plan = everything(telegram)
    print(json.dumps(plan, indent=2, ensure_ascii=False))
    if not args.apply:
        print("\nNothing was written. Re-run with --apply.")
        return 0
    try:
        for hazard in HAZARDS.values():
            if ensure_helper(base_url, token, hazard["flag"], hazard["flag_name"], hazard["flag_icon"]):
                print(f"created helper {hazard['flag']}")
        for script_id, body in plan["scripts"].items():
            _doors._request(base_url, token, f"/api/config/script/config/{script_id}", body, "POST")
            print(f"installed script script.{script_id}")
        for body in plan["automations"]:
            _doors._request(base_url, token, f"/api/config/automation/config/{body['id']}", body, "POST")
            print(f"installed automation {body['id']}")
        print(f"Telegram: {', '.join(telegram) if telegram else 'not set up - see docs/door-alerts.md, then re-run'}")
    except urllib.error.HTTPError as exc:
        print(f"REFUSED {exc.code}: {exc.read().decode('utf-8', 'replace')[:400]}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"could not reach Home Assistant at {base_url}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
