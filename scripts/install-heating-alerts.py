#!/usr/bin/env python3
"""Install the freeze and furnace-failure alerts (action list A5, 2026-09-26).

  Too cold        the thermostat reads below Settings -> House rules -> "Too cold
                  below" (default 12 C) for 10 minutes.
  Furnace failing heat has been called for "Furnace failing after" (default 60
                  min) and the house is not 0.3 C warmer than when the call began:
                  the furnace is not running, or runs without heating.

Either runs script.heating_alert: input_boolean.heating_alert (the dashboard's
red banner, with the reason from input_text.heating_alert_reason), a
time-sensitive push (through Focus, not the mute switch: urgent over hours, not
seconds) and Telegram, then again every hour while it still holds and nobody
said "I know", six times at most.

The temperature is the cloud ecobee's, falling back to the local (HomeKit) one -
the same preference the dashboard has, so a lost internet does not blind it.
"Heat called" is hvac_action == heating on either. The thresholds are read from
their helpers at run time (install-house-settings.py), so changing them on the
dashboard needs no reinstall.

    python3 scripts/install-heating-alerts.py            # show it
    python3 scripts/install-heating-alerts.py --apply    # install (on the board)
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

from src.python.house_settings import ha_value  # noqa: E402


def _door_alerts():
    spec = importlib.util.spec_from_file_location("door_alerts", PROJECT_ROOT / "scripts" / "install-door-alerts.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_doors = _door_alerts()
PHONE = _doors.PHONE
THERMOSTATS = ("climate.my_ecobee_2", "climate.my_ecobee")      # cloud first, then the local copy
FLAG = "input_boolean.heating_alert"
REASON = "input_text.heating_alert_reason"
START_TEMP = "input_number.heat_call_start_temp"
SCRIPT_ID = "heating_alert"
SCRIPT = f"script.{SCRIPT_ID}"
ACK_ACTION = "HEATING_ACK"
TAG = "heating"
COLD_FOR = {"minutes": 10}
WARMED_BY = 0.3
REMIND_EVERY = {"hours": 1}
REMINDERS = 6

TEMP = ("{% set t = [" + ", ".join(f"state_attr('{e}', 'current_temperature')" for e in THERMOSTATS)
        + "] | select('number') | list %}")
HEATING = " or ".join(f"is_state_attr('{e}', 'hvac_action', 'heating')" for e in THERMOSTATS)
THRESHOLD = ha_value("freeze_below_c")
FAIL_MIN = ha_value("furnace_fail_min")


def too_cold() -> str:
    return TEMP + "{{ t | count > 0 and t[0] < " + THRESHOLD + " }}"


def not_warming() -> str:
    return (TEMP + "{% set start = states('" + START_TEMP + "') | float(none) %}"
            "{{ t | count > 0 and start is not none and t[0] < start + " + str(WARMED_BY) + " }}")


def still_wrong() -> str:
    """For the reminders: too cold, or heat called and still not warming."""
    return (TEMP + "{% set start = states('" + START_TEMP + "') | float(none) %}"
            "{{ t | count > 0 and (t[0] < " + THRESHOLD + " or ((" + HEATING
            + ") and start is not none and t[0] < start + " + str(WARMED_BY) + ")) }}")


def _push(title: str, message: str) -> dict:
    return {"action": PHONE, "continue_on_error": True, "data": {
        "title": title, "message": message,
        "data": {"tag": TAG, "push": {"interruption-level": "time-sensitive"},
                 "actions": [{"action": ACK_ACTION, "title": "I know"}]}}}


def script(telegram: list[str]) -> dict:
    return {
        "alias": "Heating alert",
        "description": ("Too cold, or the furnace not heating: input_boolean.heating_alert with the reason, a "
                        "time-sensitive push and Telegram, then hourly while it holds (6 at most). Installed by "
                        "scripts/install-heating-alerts.py."),
        "mode": "single",
        "max_exceeded": "silent",
        "fields": {"why": {"description": "What is wrong, with the temperatures"}},
        "sequence": [
            {"action": "input_text.set_value", "target": {"entity_id": REASON}, "data": {"value": "{{ why[:250] }}"}},
            {"action": "input_boolean.turn_on", "target": {"entity_id": FLAG}},
            _push("🥶 Heating", "{{ why }}"),
            *_doors._telegram(telegram, "🥶 {{ why }}"),
            {"repeat": {
                "while": [{"condition": "state", "entity_id": FLAG, "state": "on"},
                          {"condition": "template", "value_template": "{{ repeat.index <= " + str(REMINDERS) + " }}"}],
                "sequence": [
                    {"wait_for_trigger": [{"trigger": "state", "entity_id": FLAG, "to": "off"}],
                     "timeout": REMIND_EVERY, "continue_on_timeout": True},
                    {"if": [{"condition": "state", "entity_id": FLAG, "state": "on"},
                            {"condition": "template", "value_template": still_wrong()}],
                     "then": [
                         _push("🥶 Heating - still", TEMP + "Still: the house is at {{ t[0] if t else '?' }} °C. {{ why }}"),
                         *_doors._telegram(telegram, "🥶 Still: " + TEMP + "{{ t[0] if t else '?' }} °C. {{ why }}"),
                     ]},
                ],
            }},
        ],
    }


def automations() -> list[dict]:
    return [
        {
            "id": "heating_call_started",
            "alias": "Heating - remember the temperature when heat is called",
            "description": "For the furnace check: the temperature when the thermostat starts calling for heat. "
                           "Installed by scripts/install-heating-alerts.py.",
            "mode": "single",
            "triggers": [{"trigger": "template", "value_template": "{{ " + HEATING + " }}"}],
            "conditions": [{"condition": "template", "value_template": TEMP + "{{ t | count > 0 }}"}],
            "actions": [{"action": "input_number.set_value", "target": {"entity_id": START_TEMP},
                         "data": {"value": TEMP + "{{ t[0] }}"}}],
        },
        {
            "id": "heating_furnace_not_heating",
            "alias": "Heating - heat called but the house is not warming",
            "description": "Heat called for the House rules time and not 0.3 C warmer: the furnace may have "
                           "failed. Installed by scripts/install-heating-alerts.py.",
            "mode": "single",
            "triggers": [{"trigger": "template", "value_template": "{{ " + HEATING + " }}",
                          "for": {"minutes": "{{ " + FAIL_MIN + " | int }}"}}],
            "conditions": [{"condition": "template", "value_template": not_warming()},
                           {"condition": "state", "entity_id": FLAG, "state": "off"}],
            "actions": [{"action": "script.turn_on", "target": {"entity_id": SCRIPT}, "data": {"variables": {"why": (
                TEMP + "Heat has been on for {{ " + FAIL_MIN + " | int }} minutes and the house went from "
                "{{ states('" + START_TEMP + "') | float(0) | round(1) }} to {{ t[0] }} °C - the furnace may not "
                "be working.")}}}],
        },
        {
            "id": "heating_too_cold",
            "alias": "Heating - the house is too cold",
            "description": "The thermostat below the House rules threshold for 10 minutes. "
                           "Installed by scripts/install-heating-alerts.py.",
            "mode": "single",
            "triggers": [{"trigger": "template", "value_template": too_cold(), "for": COLD_FOR}],
            "conditions": [{"condition": "state", "entity_id": FLAG, "state": "off"}],
            "actions": [{"action": "script.turn_on", "target": {"entity_id": SCRIPT}, "data": {"variables": {"why": (
                TEMP + "The house is at {{ t[0] }} °C, below {{ " + THRESHOLD + " }} °C.")}}}],
        },
        {
            "id": "heating_alert_acknowledged",
            "alias": "Heating - acknowledged on the iPhone",
            "description": "\"I know\" on the push stops the reminders and clears the dashboard. "
                           "Installed by scripts/install-heating-alerts.py.",
            "mode": "single",
            "triggers": [{"trigger": "event", "event_type": "mobile_app_notification_action",
                          "event_data": {"action": ACK_ACTION}}],
            "actions": [{"action": "input_boolean.turn_off", "target": {"entity_id": FLAG}}],
        },
    ]


HELPERS = [
    (FLAG, {"type": "input_boolean/create", "name": "Heating alert", "icon": "mdi:thermometer-alert"}),
    (REASON, {"type": "input_text/create", "name": "Heating alert reason", "max": 255,
              "icon": "mdi:thermometer-alert"}),
    (START_TEMP, {"type": "input_number/create", "name": "Heat call start temp", "min": -20, "max": 50,
                  "step": 0.1, "mode": "box", "unit_of_measurement": "°C", "icon": "mdi:thermometer"}),
]


def ensure_helpers(base_url: str, token: str) -> list[str]:
    created = []
    for entity_id, message in HELPERS:
        try:
            _doors._request(base_url, token, f"/api/states/{entity_id}")
            continue
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
        reply = _doors._ws(base_url, token, [message])[0]
        if not reply.get("success"):
            raise OSError(f"could not create {entity_id}: {reply.get('error')}")
        created.append(entity_id)
    return created


def main(argv: list[str] | None = None) -> int:
    _doors.load_dotenv(PROJECT_ROOT / ".env")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--base-url", default=os.getenv("HOME_ASSISTANT_BASE_URL", "http://127.0.0.1:8123"))
    args = ap.parse_args(argv)
    base_url, token = args.base_url.rstrip("/"), os.getenv("HOME_ASSISTANT_TOKEN")
    telegram = _doors.telegram_targets(base_url, token) if args.apply and token else []
    print(json.dumps({"script": script(telegram), "automations": automations()}, indent=2, ensure_ascii=False))
    if not args.apply:
        print("\nNothing was written. Re-run with --apply.")
        return 0
    if not token:
        print("HOME_ASSISTANT_TOKEN is not set (looked in .env)", file=sys.stderr)
        return 1
    try:
        for entity_id in ensure_helpers(base_url, token):
            print(f"created helper {entity_id}")
        _doors._request(base_url, token, f"/api/config/script/config/{SCRIPT_ID}", script(telegram), "POST")
        print(f"installed script {SCRIPT}")
        for body in automations():
            _doors._request(base_url, token, f"/api/config/automation/config/{body['id']}", body, "POST")
            print(f"installed automation {body['id']}")
        print(f"Telegram: {', '.join(telegram) if telegram else 'not set up'}")
    except urllib.error.HTTPError as exc:
        print(f"REFUSED {exc.code}: {exc.read().decode('utf-8', 'replace')[:400]}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"could not reach Home Assistant at {base_url}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
