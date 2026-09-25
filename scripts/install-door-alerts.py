#!/usr/bin/env python3
"""Install the front-door-left-open alert (asked for 2026-09-25): the dashboard,
an iPhone push, and Telegram when it is set up.

When it fires (the owner chose A + B):

  A  The last person leaves (zone.home falls to 0 for a minute) with the front
     door open - or the door opens and stays open 2 minutes within 7 minutes of
     everyone leaving. Needs the phone to report its location in the background.
  B  The door has been open 10 minutes and no indoor sensor has seen anyone for
     10 minutes. Needs no phone: it covers a phone that does not report, and
     anyone who lives here without a tracked one.

Either runs script.front_door_left_open, which turns input_boolean.front_door_alert
on and sends the message - then again every 15 minutes while the door stays
open, three reminders at most. It runs once at a time (mode single), so A and B
firing together send one message, not two.

It stops when the door closes (a "closed at 14:32" follows, replacing the push
on the lock screen by its tag), or when someone acknowledges it: "I know" on the
push, or closing the banner on any dashboard screen. The banner is Home
Assistant's state, not the browser's, so closing it on one screen closes it on
all of them.

Telegram is sent to every notify entity of the telegram_bot integration, found
when this runs; with none, the rules are installed without it. Set Telegram up
(docs/door-alerts.md), then run this again.

    python3 scripts/install-door-alerts.py            # show it
    python3 scripts/install-door-alerts.py --apply    # install (on the board)
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _house_modes():
    """The indoor sensor list lives in the house modes installer: one list, not two."""
    spec = importlib.util.spec_from_file_location("house_modes", PROJECT_ROOT / "scripts" / "install-house-modes.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


INDOOR = _house_modes().INDOOR
DOOR = "binary_sensor.0xa4c138813abdffff_contact"      # Door sensor front door; on = open
PEOPLE_HOME = "zone.home"
ALERT = "input_boolean.front_door_alert"
SCRIPT_ID = "front_door_left_open"
SCRIPT = f"script.{SCRIPT_ID}"
PHONE = "notify.mobile_app_iphone_15"
CAMERA = "camera.zhi_neng_men_ling"                     # the doorbell, at the front door
TAG = "front-door-open"                                 # one notification on the lock screen, replaced
ACK_ACTION = "FRONT_DOOR_ACK"

LEFT_FOR = {"minutes": 1}
OPENED_AFTER_LEAVING_FOR = {"minutes": 2}
JUST_LEFT_S = 7 * 60
STILL_FOR = {"minutes": 10}
REMIND_EVERY = {"minutes": 15}
REMINDERS = 3
QUIET = ["off", "unavailable", "unknown"]

WHY_LEFT = "Everyone has left and the front door is open."
WHY_STILL = "The front door has been open 10 minutes and nobody has moved inside."


def _door_open_for(duration: dict) -> dict:
    return {"condition": "state", "entity_id": DOOR, "state": "on", "for": duration}


def _nobody_home() -> dict:
    return {"condition": "numeric_state", "entity_id": PEOPLE_HOME, "below": 1}


def _alert(why: str) -> dict:
    return {"action": "script.turn_on", "target": {"entity_id": SCRIPT}, "data": {"variables": {"why": why}}}


def _push(title: str, message: str, urgent: bool) -> dict:
    data: dict = {"tag": TAG}
    if urgent:
        data["push"] = {"interruption-level": "time-sensitive"}
        data["actions"] = [
            {"action": "URI", "title": "Show camera", "uri": f"entityId:{CAMERA}"},
            {"action": ACK_ACTION, "title": "I know"},
        ]
    return {"action": "notify.mobile_app_iphone_15", "continue_on_error": True,
            "data": {"title": title, "message": message, "data": data}}


def _telegram(telegram: list[str], text: str) -> list[dict]:
    if not telegram:
        return []
    return [{"action": "notify.send_message", "target": {"entity_id": telegram}, "continue_on_error": True,
             "data": {"message": text}}]


def script(telegram: list[str]) -> dict:
    reminder = ("{{ why if repeat.index == 1 else 'Still open - ' ~ ((repeat.index - 1) * "
                + str(REMIND_EVERY["minutes"]) + ") ~ ' minutes since the first message.' }}")
    return {
        "alias": "Front door left open",
        "description": ("Alerts that the front door is open with nobody home: input_boolean.front_door_alert "
                        "for the dashboard, the iPhone and Telegram, then every 15 minutes while it stays open "
                        "(3 reminders). Installed by scripts/install-door-alerts.py."),
        "mode": "single",
        "max_exceeded": "silent",
        "fields": {"why": {"description": "What made it fire", "example": WHY_LEFT}},
        "sequence": [
            {"action": "input_boolean.turn_on", "target": {"entity_id": ALERT}},
            {"repeat": {
                "while": [
                    {"condition": "state", "entity_id": DOOR, "state": "on"},
                    {"condition": "state", "entity_id": ALERT, "state": "on"},
                    {"condition": "template", "value_template": "{{ repeat.index <= " + str(1 + REMINDERS) + " }}"},
                ],
                "sequence": [
                    _push("Front door is open", reminder, urgent=True),
                    *_telegram(telegram, "🚪 Front door is open. " + reminder),
                    {"wait_for_trigger": [
                        {"trigger": "state", "entity_id": DOOR, "to": "off"},
                        {"trigger": "state", "entity_id": ALERT, "to": "off"},
                    ], "timeout": REMIND_EVERY, "continue_on_timeout": True},
                ],
            }},
        ],
    }


def automations(telegram: list[str]) -> list[dict]:
    return [
        {
            "id": "front_door_open_when_everyone_left",
            "alias": "Front door - open when the last person leaves",
            "description": "A: the last phone leaves the home zone with the front door open. "
                           "Installed by scripts/install-door-alerts.py.",
            "mode": "single",
            "triggers": [{"trigger": "numeric_state", "entity_id": PEOPLE_HOME, "below": 1, "for": LEFT_FOR}],
            "conditions": [{"condition": "state", "entity_id": DOOR, "state": "on"}],
            "actions": [_alert(WHY_LEFT)],
        },
        {
            "id": "front_door_opened_just_after_leaving",
            "alias": "Front door - opened just after everyone left",
            "description": "A: the front door opens and stays open 2 minutes, within 7 minutes of the last "
                           "phone leaving. Installed by scripts/install-door-alerts.py.",
            "mode": "single",
            "triggers": [{"trigger": "state", "entity_id": DOOR, "to": "on", "for": OPENED_AFTER_LEAVING_FOR}],
            "conditions": [
                _nobody_home(),
                {"condition": "template", "value_template": (
                    "{{ (now() - states['" + PEOPLE_HOME + "'].last_changed).total_seconds() < "
                    + str(JUST_LEFT_S) + " }}")},
            ],
            "actions": [_alert(WHY_LEFT)],
        },
        {
            "id": "front_door_open_house_still",
            "alias": "Front door - open 10 minutes and the house is still",
            "description": "B: open 10 minutes and no indoor sensor has seen anyone for 10 minutes - no phone "
                           "needed. Installed by scripts/install-door-alerts.py.",
            "mode": "single",
            "triggers": [
                {"trigger": "state", "entity_id": DOOR, "to": "on", "for": STILL_FOR},
                {"trigger": "state", "entity_id": INDOOR, "to": "off", "for": STILL_FOR},
            ],
            "conditions": [
                _door_open_for(STILL_FOR),
                {"condition": "state", "entity_id": INDOOR, "state": QUIET, "for": STILL_FOR},
                {"condition": "state", "entity_id": ALERT, "state": "off"},
            ],
            "actions": [_alert(WHY_STILL)],
        },
        {
            "id": "front_door_closed_after_alert",
            "alias": "Front door - closed after an alert",
            "description": "The door closed while an alert was on: say so on the iPhone (replacing the alert "
                           "by its tag) and Telegram, and clear the dashboard. "
                           "Installed by scripts/install-door-alerts.py.",
            "mode": "single",
            "triggers": [{"trigger": "state", "entity_id": DOOR, "to": "off"}],
            "conditions": [{"condition": "state", "entity_id": ALERT, "state": "on"}],
            "actions": [
                {"action": "input_boolean.turn_off", "target": {"entity_id": ALERT}},
                _push("Front door closed", "Closed at {{ now().strftime('%H:%M') }}.", urgent=False),
                *_telegram(telegram, "✅ Front door closed at {{ now().strftime('%H:%M') }}."),
            ],
        },
        {
            "id": "front_door_alert_acknowledged",
            "alias": "Front door - alert acknowledged on the iPhone",
            "description": "\"I know\" on the push stops the reminders and clears the dashboard. "
                           "Installed by scripts/install-door-alerts.py.",
            "mode": "single",
            "triggers": [{"trigger": "event", "event_type": "mobile_app_notification_action",
                          "event_data": {"action": ACK_ACTION}}],
            "actions": [{"action": "input_boolean.turn_off", "target": {"entity_id": ALERT}}],
        },
    ]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _request(base_url: str, token: str, path: str, body: dict | None = None, method: str = "GET"):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(f"{base_url}{path}", data=data, headers=_headers(token), method=method)
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read()
    return json.loads(raw) if raw else None


def _ws(base_url: str, token: str, messages: list[dict]) -> list[dict]:
    """Send websocket commands in order; returns the replies. aiohttp is in the board's .venv."""
    import asyncio
    import aiohttp

    async def run() -> list[dict]:
        replies = []
        async with aiohttp.ClientSession() as session, \
                session.ws_connect(base_url.replace("http", "ws", 1) + "/api/websocket") as ws:
            await ws.receive_json()
            await ws.send_json({"type": "auth", "access_token": token})
            await ws.receive_json()
            for n, message in enumerate(messages, start=1):
                await ws.send_json({"id": n, **message})
                replies.append(await ws.receive_json())
        return replies

    return asyncio.run(run())


def telegram_targets(base_url: str, token: str) -> list[str]:
    """Every notify entity the telegram_bot integration made, one per allowed chat."""
    registry = _ws(base_url, token, [{"type": "config/entity_registry/list"}])[0].get("result") or []
    return sorted(e["entity_id"] for e in registry
                  if e.get("platform") == "telegram_bot" and e["entity_id"].startswith("notify.")
                  and not e.get("disabled_by"))


def ensure_alert_helper(base_url: str, token: str) -> bool:
    try:
        _request(base_url, token, f"/api/states/{ALERT}")
        return False
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
    reply = _ws(base_url, token, [{"type": "input_boolean/create", "name": "Front door alert",
                                   "icon": "mdi:door-open"}])[0]
    if not reply.get("success"):
        raise OSError(f"could not create {ALERT}: {reply.get('error')}")
    return True


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main(argv: list[str] | None = None) -> int:
    load_dotenv(PROJECT_ROOT / ".env")
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
        telegram = telegram_targets(base_url, token)
    print(json.dumps({"script": script(telegram), "automations": automations(telegram)}, indent=2))
    if not args.apply:
        print("\nNothing was written. Re-run with --apply.")
        return 0
    try:
        if ensure_alert_helper(base_url, token):
            print(f"created helper {ALERT}")
        _request(base_url, token, f"/api/config/script/config/{SCRIPT_ID}", script(telegram), "POST")
        print(f"installed script {SCRIPT}")
        for body in automations(telegram):
            _request(base_url, token, f"/api/config/automation/config/{body['id']}", body, "POST")
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
