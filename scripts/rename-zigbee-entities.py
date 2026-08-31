#!/usr/bin/env python3
"""Give Zigbee2MQTT entities entity IDs that match their device names.

Home Assistant assigns an entity_id once, when the entity is first created, and
then keys the entity on its unique_id. Renaming a device in Zigbee2MQTT afterwards
republishes discovery with the same unique_id, so Home Assistant updates the
display name and deliberately leaves the entity_id alone - changing it would break
automations pointing at it.

The practical effect is that a device paired before it was named keeps IDs built
from its IEEE address:

    sensor.0xa4c138829671ddd5_temperature   "Temperature and humidity living room Temperature"

and no amount of renaming in Zigbee2MQTT will fix that. This does, by renaming
through Home Assistant's entity registry - the same thing the "also rename entity
IDs" prompt does when you rename a device in the UI, but for every device at once
and without the clicking.

It also covers the entities that prompt cannot help with: Zigbee2MQTT omits
object_id for diagnostic entities (last_seen, linkquality), so those come back
IEEE-named even after a full delete-and-rediscover.

Targets are derived from Home Assistant's own device and entity registries, so
this needs no MQTT credentials and no access to the broker.

    # See what would change - this is the default, nothing is written
    ./scripts/rename-zigbee-entities.py

    # Do it
    ./scripts/rename-zigbee-entities.py --apply

Renaming orphans the recorder history stored under the old entity_id. That is
usually the right trade right after pairing, and a bad one for a device that has
been collecting data for months.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
import unicodedata

import aiohttp


def slugify(value: str) -> str:
    """Approximate Home Assistant's slugify for ASCII names.

    Non-ASCII characters are transliterated where possible and dropped where not,
    which is fine for Zigbee2MQTT devices - they are named by hand in its UI - but
    would mangle a device named entirely in a non-Latin script. Such a name yields
    an empty slug, and those entities are skipped rather than renamed to nonsense.
    """
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", normalized.lower())).strip("_")


class HomeAssistant:
    """Minimal Home Assistant WebSocket client for the two registries."""

    def __init__(self, session: aiohttp.ClientSession, ws: aiohttp.ClientWebSocketResponse) -> None:
        self._ws = ws
        self._id = 0

    async def call(self, **payload) -> object:
        self._id += 1
        await self._ws.send_json({"id": self._id, **payload})
        while True:
            message = await self._ws.receive_json()
            if message.get("id") != self._id:
                continue  # An event or a reply to something else.
            if not message.get("success"):
                raise RuntimeError(message.get("error", {}).get("message", "call failed"))
            return message.get("result")


async def connect(base_url: str, token: str, session: aiohttp.ClientSession) -> HomeAssistant:
    ws_url = base_url.rstrip("/").replace("http", "ws", 1) + "/api/websocket"
    ws = await session.ws_connect(ws_url, heartbeat=30)
    greeting = await ws.receive_json()
    if greeting.get("type") != "auth_required":
        raise RuntimeError(f"unexpected greeting: {greeting.get('type')}")
    await ws.send_json({"type": "auth", "access_token": token})
    result = await ws.receive_json()
    if result.get("type") != "auth_ok":
        raise RuntimeError("authentication rejected")
    return HomeAssistant(session, ws)


def plan_renames(entities: list[dict], devices: list[dict], platform: str, name_filter: str | None) -> list[tuple[str, str, str]]:
    """Work out the intended entity_id for each entity.

    Returns (current_id, target_id, reason-to-skip-or-empty) for everything
    considered, so the dry run can explain what it is leaving alone.
    """
    device_names = {
        device["id"]: (device.get("name_by_user") or device.get("name") or "")
        for device in devices
    }
    taken = {entity["entity_id"] for entity in entities}

    plan: list[tuple[str, str, str]] = []
    for entity in entities:
        current = entity["entity_id"]
        if entity.get("platform") != platform:
            continue
        device_name = device_names.get(entity.get("device_id") or "", "")
        if not device_name:
            continue
        if name_filter and name_filter.lower() not in device_name.lower():
            continue

        domain = current.split(".", 1)[0]
        device_slug = slugify(device_name)
        # original_name is the per-entity part Zigbee2MQTT published - Temperature,
        # Battery, Linkquality. A main entity can have none, in which case the
        # device name alone is the whole id.
        entity_slug = slugify(entity.get("original_name") or "")
        if not device_slug:
            plan.append((current, "", "device name has no ASCII characters"))
            continue

        target = f"{domain}.{device_slug}" + (f"_{entity_slug}" if entity_slug else "")
        if target == current:
            continue
        if target in taken:
            plan.append((current, target, "target id already in use"))
            continue
        plan.append((current, target, ""))
        # Claim it so two entities cannot both be renamed onto the same id.
        taken.add(target)
    return plan


async def run(args: argparse.Namespace, token: str) -> int:
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
        ha = await connect(args.base_url, token, session)
        entities = await ha.call(type="config/entity_registry/list")
        devices = await ha.call(type="config/device_registry/list")

        plan = plan_renames(entities, devices, args.platform, args.filter)
        renames = [(old, new) for old, new, skip in plan if not skip]
        skips = [(old, new, skip) for old, new, skip in plan if skip]

        for old, new, reason in skips:
            print(f"  skip   {old}\n         -> {new or '(no target)'}  [{reason}]")

        if not renames:
            print("Nothing to rename - every entity id already matches its device name.")
            return 0

        for old, new in renames:
            print(f"  {'rename' if args.apply else 'would'}  {old}\n         -> {new}")

        if not args.apply:
            print(f"\n{len(renames)} entity ids would change. Re-run with --apply to do it.")
            return 0

        failures = 0
        for old, new in renames:
            try:
                await ha.call(type="config/entity_registry/update", entity_id=old, new_entity_id=new)
            except RuntimeError as error:
                failures += 1
                print(f"  FAILED {old}: {error}", file=sys.stderr)
        print(f"\nRenamed {len(renames) - failures} of {len(renames)}.")
        return 1 if failures else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--apply", action="store_true",
                        help="Actually rename. Without this nothing is written.")
    parser.add_argument("--filter", help="Only devices whose name contains this text.")
    parser.add_argument("--platform", default="mqtt",
                        help="Integration to act on (default: mqtt, which is Zigbee2MQTT).")
    parser.add_argument("--base-url", default=os.getenv("HOME_ASSISTANT_URL") or "http://127.0.0.1:8123",
                        help="Home Assistant base URL.")
    parser.add_argument("--token-env", default="HOME_ASSISTANT_TOKEN",
                        help="Environment variable holding the long-lived token.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token = os.getenv(args.token_env)
    if not token:
        print(f"No token in ${args.token_env}. Source the board's .env first:", file=sys.stderr)
        print("  set -a && . ./.env && set +a", file=sys.stderr)
        return 2
    try:
        return asyncio.run(run(args, token))
    except (aiohttp.ClientError, RuntimeError) as error:
        print(f"Failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
