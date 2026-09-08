#!/usr/bin/env python3
"""Find and disable Home Assistant devices that no longer report anything.

Moving a device from one radio to another leaves the old integration's entry
behind. The device is re-paired and working, but Home Assistant still lists the
original as a device whose entities sit at `unavailable` forever, and every view
built on `/api/states` renders it as a dead tile. Five of these accumulated on
this board when sensors moved from the Tuya gateway to the Zigbee dongle.

**Disables rather than deletes.** Home Assistant 2026.6 has no
`remove_config_entry_from_device` WebSocket command, and disabling is the
supported equivalent -- a disabled device's entities leave the state machine
entirely, so they vanish from `/api/states` and everything downstream. It also
survives a restore, because `.storage/core.device_registry` is in the backup,
and unlike deletion it can be undone from the Home Assistant UI.

**Refuses to touch anything still reporting.** A device with even one live
entity is not an orphan, whatever its name suggests, and the check is on state
rather than on the name.

    # what would happen
    python3 scripts/disable-orphan-ha-devices.py --list
    python3 scripts/disable-orphan-ha-devices.py "Motion Sensor&TH"
    # do it
    python3 scripts/disable-orphan-ha-devices.py "Motion Sensor&TH" --apply

Run it on the board: Home Assistant is loopback-only.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEAD_STATES = {None, "unavailable", "unknown"}


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


async def run(args: argparse.Namespace) -> int:
    try:
        import aiohttp
    except ImportError:
        print("aiohttp is required (use the project venv)", file=sys.stderr)
        return 1

    token = os.getenv("HOME_ASSISTANT_TOKEN")
    if not token:
        print("HOME_ASSISTANT_TOKEN is not set (looked in .env)", file=sys.stderr)
        return 1

    base = args.base_url.rstrip("/")
    ws_url = base.replace("https://", "wss://").replace("http://", "ws://") + "/api/websocket"

    async with aiohttp.ClientSession() as session:
        async with session.get(base + "/api/states",
                               headers={"Authorization": f"Bearer {token}"}) as response:
            states = {x["entity_id"]: x["state"] for x in await response.json()}

        async with session.ws_connect(ws_url, heartbeat=30) as ws:
            await ws.receive_json()
            await ws.send_json({"type": "auth", "access_token": token})
            if (await ws.receive_json()).get("type") != "auth_ok":
                print("Home Assistant rejected the token", file=sys.stderr)
                return 1

            counter = 0

            async def call(payload: dict) -> dict:
                nonlocal counter
                counter += 1
                payload["id"] = counter
                await ws.send_json(payload)
                while True:
                    message = await ws.receive_json()
                    if message.get("id") == counter:
                        return message

            entities = (await call({"type": "config/entity_registry/list"}))["result"]
            devices = (await call({"type": "config/device_registry/list"}))["result"]

            by_device: dict[str, list[dict]] = {}
            for entity in entities:
                if entity.get("device_id"):
                    by_device.setdefault(entity["device_id"], []).append(entity)

            def summarise(device: dict) -> tuple[str, list[dict], list[str]]:
                name = device.get("name_by_user") or device.get("name") or "?"
                mine = by_device.get(device["id"], [])
                live = [e["entity_id"] for e in mine if states.get(e["entity_id"]) not in DEAD_STATES]
                return name, mine, live

            if args.list:
                print("Devices with no live entity (candidates):\n")
                found = 0
                for device in sorted(devices, key=lambda d: (d.get("name_by_user") or d.get("name") or "")):
                    if device.get("disabled_by"):
                        continue
                    name, mine, live = summarise(device)
                    if not mine or live:
                        continue
                    platforms = sorted({e.get("platform") or "?" for e in mine})
                    print(f"  {name!r:<42} {len(mine)} entities  platform={','.join(platforms)}")
                    for entity in mine:
                        print(f"      {entity['entity_id']}")
                    found += 1
                print(f"\n{found} candidate device(s). Nothing changed.")
                return 0

            failures = 0
            for wanted in args.names:
                matches = [d for d in devices
                           if (d.get("name_by_user") or d.get("name") or "") == wanted]
                if not matches:
                    print(f"!! no device named {wanted!r}")
                    failures += 1
                    continue
                for device in matches:
                    name, mine, live = summarise(device)
                    print(f"\n{name!r}  id={device['id'][:8]}  entities={len(mine)}")
                    for entity in mine:
                        print(f"   - {entity['entity_id']} = {states.get(entity['entity_id'], '<absent>')}")
                    if live:
                        print(f"   REFUSING: still reporting: {live}")
                        failures += 1
                        continue
                    if not args.apply:
                        print("   would disable (re-run with --apply)")
                        continue
                    result = await call({"type": "config/device_registry/update",
                                         "device_id": device["id"], "disabled_by": "user"})
                    if result.get("success"):
                        print("   disabled")
                    else:
                        print(f"   FAILED: {result.get('error')}")
                        failures += 1
    return 1 if failures else 0


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("names", nargs="*", help="exact device names, as shown in Home Assistant")
    ap.add_argument("--list", action="store_true", help="show every device with no live entity")
    ap.add_argument("--apply", action="store_true", help="without this, nothing is changed")
    ap.add_argument("--base-url", default=os.getenv("HOME_ASSISTANT_BASE_URL", "http://127.0.0.1:8123"))
    args = ap.parse_args()
    if not args.names and not args.list:
        ap.error("give device names, or --list to see the candidates")
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
