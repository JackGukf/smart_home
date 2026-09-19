#!/usr/bin/env python3
"""Install the family room's late-night lights-off automation in Home Assistant.

After 11:30 PM (until 6 AM), when the kitchen/family room occupancy sensor has
seen nobody for 10 minutes and any of the family room's accent lights is on,
all of them go off:

    Family room LED                light.family_room_led
    Cabinet LEDs (IKEA, 2)         light.0x286847fffe5eb711, light.0x64028ffffe64de32
    Cabinet LED plug (TP-Link)     switch.family_room_cabinet_led

Motion never turns anything on - the owner's choice (2026-09-18).

The 11:30 PM is not in the automation: it reads input_datetime.family_room_lights_off_after,
a time helper the dashboard sets (Settings -> Night lights), so changing it
needs no reinstall. The helper is created here if it is missing, at 23:30.

Three triggers, because "no motion for 10 minutes" alone misses two evenings:
the room already empty at 11:30 (the sensor went off at 11:00 and does not
change again), and a light switched on remotely with nobody there to move.
The conditions then decide, whichever trigger fired.

Written through Home Assistant's config API, like install-panel-scenes.py: its
validator runs first and automations are reloaded. The Zigbee entity ids start
with a digit, which is fine in triggers and targets; never write them as
states.binary_sensor.0x... in a template.

    python3 scripts/install-family-room-late-off.py            # show it
    python3 scripts/install-family-room-late-off.py --apply    # install (on the board)
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

AUTOMATION_ID = "family_room_lights_off_late"
OCCUPANCY = "binary_sensor.0xa4c138d00106c90d_presence"  # Motion and TH Kitchen and Family Room
LIGHTS = ["light.family_room_led", "light.0x286847fffe5eb711", "light.0x64028ffffe64de32"]
SWITCHES = ["switch.family_room_cabinet_led"]
NO_MOTION = {"minutes": 10}
# When it starts: a time helper, set from the dashboard. Ends at 6 AM.
AFTER = "input_datetime.family_room_lights_off_after"
AFTER_DEFAULT = "23:30:00"
BEFORE = "06:00:00"


def automation() -> dict:
    return {
        "id": AUTOMATION_ID,
        "alias": "Family room lights off late, when nobody is there",
        "description": ("From the time in input_datetime.family_room_lights_off_after (11:30 PM "
                        "unless changed on the dashboard) until 6 AM, when the kitchen and family room occupancy sensor "
                        "has seen nobody for 10 minutes, turn off the family room LED, both IKEA "
                        "cabinet LEDs and the cabinet LED plug. Installed by "
                        "scripts/install-family-room-late-off.py."),
        "mode": "single",
        "triggers": [
            {"trigger": "state", "entity_id": OCCUPANCY, "to": "off", "for": NO_MOTION},
            {"trigger": "time", "at": AFTER},
            {"trigger": "state", "entity_id": LIGHTS + SWITCHES, "to": "on", "for": NO_MOTION},
        ],
        "conditions": [
            # A time condition with after > before spans midnight; "after" may be
            # a time helper, read each time the condition is checked.
            {"condition": "time", "after": AFTER, "before": BEFORE},
            {"condition": "state", "entity_id": OCCUPANCY, "state": "off", "for": NO_MOTION},
            {"condition": "state", "entity_id": LIGHTS + SWITCHES, "match": "any", "state": "on"},
        ],
        "actions": [
            {"action": "light.turn_off", "target": {"entity_id": LIGHTS}},
            {"action": "switch.turn_off", "target": {"entity_id": SWITCHES}},
        ],
    }


def ensure_helper(base_url: str, token: str) -> str:
    """Create the start-time helper if it is missing, at 23:30. Returns its value."""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        with urllib.request.urlopen(urllib.request.Request(f"{base_url}/api/states/{AFTER}", headers=headers),
                                    timeout=15) as response:
            return json.load(response)["state"]
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
    # Helpers are created over the websocket API only; aiohttp is in the board's .venv.
    import asyncio
    import aiohttp

    async def create() -> None:
        ws_url = base_url.replace("http", "ws", 1) + "/api/websocket"
        async with aiohttp.ClientSession() as session, session.ws_connect(ws_url) as ws:
            await ws.receive_json()
            await ws.send_json({"type": "auth", "access_token": token})
            await ws.receive_json()
            await ws.send_json({"id": 1, "type": "input_datetime/create", "name": "Family room lights off after",
                                "has_date": False, "has_time": True, "icon": "mdi:weather-night"})
            await ws.receive_json()
            await ws.send_json({"id": 2, "type": "call_service", "domain": "input_datetime",
                                "service": "set_datetime", "target": {"entity_id": AFTER},
                                "service_data": {"time": AFTER_DEFAULT}})
            await ws.receive_json()

    asyncio.run(create())
    return AFTER_DEFAULT


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
        f"{base_url.rstrip('/')}/api/config/automation/config/{AUTOMATION_ID}",
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

    body = automation()
    print(json.dumps(body, indent=2))
    if not args.apply:
        print("\nNothing was written. Re-run with --apply.")
        return 0
    token = os.getenv("HOME_ASSISTANT_TOKEN")
    if not token:
        print("HOME_ASSISTANT_TOKEN is not set (looked in .env)", file=sys.stderr)
        return 1
    try:
        print(f"start time: {ensure_helper(args.base_url.rstrip('/'), token)} ({AFTER})")
        install(args.base_url, token, body)
    except urllib.error.HTTPError as exc:
        print(f"REFUSED {exc.code}: {exc.read().decode('utf-8', 'replace')[:400]}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"could not reach Home Assistant at {args.base_url}: {exc}", file=sys.stderr)
        return 1
    print(f"\ninstalled automation.{AUTOMATION_ID} (Home Assistant validated it and reloaded automations)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
