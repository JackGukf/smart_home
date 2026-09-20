#!/usr/bin/env python3
"""Hide the HomeKit ecobee's entities, so Home Assistant shows one thermostat.

The same thermostat is in Home Assistant twice: over HomeKit on the LAN, and
through the ecobee cloud integration, which is the one that carries the room
sensors, the presets and what the equipment is doing. Two of everything is
confusing, but removing the local one would leave the house unable to touch the
thermostat when the internet is out.

So: **hidden, not disabled.** A hidden entity still updates and can still be
driven - it simply does not clutter Home Assistant - and the dashboard ranks an
answering thermostat above a richer one (web_app._thermostat_richness), so the
card falls back to the HomeKit entity by itself the moment the cloud one goes
unavailable, and back again when it returns.

    .venv/bin/python scripts/hide-duplicate-ecobee.py           # hide them
    .venv/bin/python scripts/hide-duplicate-ecobee.py --undo    # show them again
"""
import asyncio, json, os, sys
import aiohttp

TOKEN = os.environ["HOME_ASSISTANT_TOKEN"]
UNDO = "--undo" in sys.argv


async def main():
    async with aiohttp.ClientSession() as session, session.ws_connect("ws://127.0.0.1:8123/api/websocket") as ws:
        await ws.receive_json()
        await ws.send_json({"type": "auth", "access_token": TOKEN})
        assert (await ws.receive_json())["type"] == "auth_ok"

        await ws.send_json({"id": 1, "type": "config/entity_registry/list"})
        entities = (await ws.receive_json())["result"]
        homekit = [e for e in entities
                   if e.get("platform") == "homekit_controller" and "ecobee" in e["entity_id"]]
        print(f"HomeKit ecobee entities: {len(homekit)}")

        for i, entity in enumerate(homekit, start=2):
            await ws.send_json({"id": i, "type": "config/entity_registry/update",
                                "entity_id": entity["entity_id"],
                                "hidden_by": None if UNDO else "user"})
            reply = await ws.receive_json()
            state = "shown" if UNDO else "hidden"
            print(f"  {entity['entity_id']:46} {state if reply.get('success') else reply.get('error')}")

asyncio.run(main())
