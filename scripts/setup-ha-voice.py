#!/usr/bin/env python3
"""Give Home Assistant a voice: local speech-to-text and text-to-speech.

Before this, Assist here had no speech at all. The only TTS engine was
`tts.google_translate_en_com`, which is a cloud round trip in an otherwise local
house and dies with the WAN, and there was no STT engine of any kind - so a
voice satellite could wake, listen, and then have nothing to transcribe with.

`docker-compose.voice.yml` runs the two Wyoming services on loopback. This wires
them into Home Assistant and points the default Assist pipeline at them:

  * a `wyoming` config entry for Whisper  (127.0.0.1:10300) -> stt.*
  * a `wyoming` config entry for Piper    (127.0.0.1:10200) -> tts.*
  * the default pipeline's stt_engine and tts_engine set to those

## Why the add-ons are not an option here

Every Home Assistant voice guide starts "install the Whisper add-on". This
install is the plain Docker container, not Home Assistant OS and not Supervised,
so there is no Supervisor and no add-on store. The add-ons are wrappers around
exactly these Wyoming services, so running them directly is the same thing
without the wrapper.

## What this does not touch

The conversation agent. `prefer_local_intents` and the two Qwen agents are
scripts/setup-ha-ollama.py's business, and the reasoning there still holds: the
matcher answers in ~0.02 s and the model takes ~22 s, so voice rides the
default pipeline and the model stays a fallback. Speech in and speech out is
all this adds.

Idempotent. Re-running reports what is already there and changes nothing.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import socket
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

SERVICES = [
    ("Whisper (speech to text)", "127.0.0.1", 10300),
    ("Piper (text to speech)", "127.0.0.1", 10200),
]


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def port_open(host: str, port: int, timeout: float = 3.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout):
            return True
    except OSError:
        return False


async def existing_wyoming_entries(session, headers, base) -> dict[str, str]:
    """Map "host:port" -> entry_id for wyoming entries already configured."""
    async with session.get(f"{base}/api/config/config_entries/entry",
                           headers=headers) as response:
        entries = await response.json()

    found = {}
    for entry in entries:
        if entry.get("domain") != "wyoming":
            continue
        # The entry title is the service name, so the address lives in the
        # unique_id, which wyoming sets to "host:port".
        key = entry.get("unique_id") or entry.get("title")
        found[str(key)] = entry["entry_id"]
    return found


async def ensure_entry(session, headers, base, host: str, port: int, apply: bool):
    async with session.post(f"{base}/api/config/config_entries/flow", headers=headers,
                            json={"handler": "wyoming", "show_advanced_options": True}) as response:
        flow = await response.json()
    if "flow_id" not in flow:
        raise RuntimeError(f"could not start the wyoming config flow: {flow}")

    async with session.post(f"{base}/api/config/config_entries/flow/{flow['flow_id']}",
                            headers=headers,
                            json={"host": host, "port": port}) as response:
        result = await response.json()

    if result.get("type") != "create_entry":
        raise RuntimeError(f"wyoming flow for {host}:{port} did not create an entry: {result}")
    return result["result"]["entry_id"]


async def engines(session, headers, base) -> tuple[list[str], list[str]]:
    async with session.get(f"{base}/api/states", headers=headers) as response:
        states = await response.json()
    stt = sorted(s["entity_id"] for s in states if s["entity_id"].startswith("stt."))
    tts = sorted(s["entity_id"] for s in states if s["entity_id"].startswith("tts."))
    return stt, tts


class HomeAssistantWS:
    """Minimal Home Assistant WebSocket client, matching the other scripts here."""

    def __init__(self, ws) -> None:
        self._ws = ws
        self._id = 0

    async def call(self, **payload):
        self._id += 1
        await self._ws.send_json({"id": self._id, **payload})
        while True:
            message = await self._ws.receive_json()
            if message.get("id") != self._id:
                continue
            if not message.get("success"):
                error = message.get("error", {})
                raise RuntimeError(f"{payload.get('type')}: {error.get('message', message)}")
            return message.get("result")


async def point_pipeline_at(ha: HomeAssistantWS, stt_entity: str, tts_entity: str,
                            apply: bool) -> list[str]:
    listing = await ha.call(type="assist_pipeline/pipeline/list")
    pipelines = listing["pipelines"] if isinstance(listing, dict) else listing
    default = next((p for p in pipelines if p["name"] == "Home Assistant"), None)
    if default is None and pipelines:
        default = pipelines[0]
    if default is None:
        return ["no Assist pipeline to update"]

    changes = []
    if default.get("stt_engine") != stt_entity:
        changes.append(f"stt_engine={stt_entity}")
    if default.get("tts_engine") != tts_entity:
        changes.append(f"tts_engine={tts_entity}")
    if not changes:
        return []

    if apply:
        fields = {k: v for k, v in default.items() if k != "id"}
        fields["stt_engine"] = stt_entity
        fields["stt_language"] = fields.get("stt_language") or "en"
        fields["tts_engine"] = tts_entity
        fields["tts_language"] = fields.get("tts_language") or "en"
        fields["tts_voice"] = None
        await ha.call(type="assist_pipeline/pipeline/update",
                      pipeline_id=default["id"], **fields)
    return [f"pipeline {default['name']!r}: {', '.join(changes)}"]


async def run(args: argparse.Namespace) -> int:
    try:
        import aiohttp
    except ImportError:
        print("aiohttp is required (use ~/smart_home_AI/.venv/bin/python)", file=sys.stderr)
        return 1

    token = os.getenv("HOME_ASSISTANT_TOKEN")
    if not token:
        print("HOME_ASSISTANT_TOKEN is not set (looked in .env)", file=sys.stderr)
        return 1

    # Fail here rather than half way through a config flow.
    missing = [f"{name} on {host}:{port}" for name, host, port in SERVICES
               if not port_open(host, port)]
    if missing:
        print("not answering: " + "; ".join(missing), file=sys.stderr)
        print("start them with:  docker compose -f docker-compose.voice.yml up -d",
              file=sys.stderr)
        return 1
    for name, host, port in SERVICES:
        print(f"{name} is answering on {host}:{port}")

    base = args.base_url.rstrip("/")
    headers = {"Authorization": f"Bearer {token}"}
    ws_url = base.replace("https://", "wss://").replace("http://", "ws://") + "/api/websocket"
    apply = args.apply

    async with aiohttp.ClientSession() as session:
        have = await existing_wyoming_entries(session, headers, base)
        for name, host, port in SERVICES:
            key = f"{host}:{port}"
            if key in have:
                print(f"wyoming entry for {key} already exists ({have[key]})")
                continue
            if not apply:
                print(f"would create a wyoming entry for {key}")
                continue
            entry_id = await ensure_entry(session, headers, base, host, port, apply)
            print(f"created the wyoming entry for {key} ({entry_id})")

        if apply:
            await asyncio.sleep(4)  # let the entities register

        stt, tts = await engines(session, headers, base)
        print(f"speech to text engines: {', '.join(stt) or 'none'}")
        print(f"text to speech engines: {', '.join(tts) or 'none'}")

        local_stt = next((e for e in stt if "whisper" in e or "faster" in e), None) or (stt[0] if stt else None)
        local_tts = next((e for e in tts if "piper" in e), None)
        if not local_stt or not local_tts:
            print("could not identify the local engines; pipeline left alone",
                  file=sys.stderr)
            return 0 if not apply else 1

        async with session.ws_connect(ws_url) as ws:
            await ws.receive_json()
            await ws.send_json({"type": "auth", "access_token": token})
            if (await ws.receive_json()).get("type") != "auth_ok":
                print("websocket auth failed", file=sys.stderr)
                return 1
            ha = HomeAssistantWS(ws)
            for line in await point_pipeline_at(ha, local_stt, local_tts, apply):
                print(("" if apply else "would ") + line)

    if not apply:
        print("\ndry run - nothing changed. Re-run with --apply.")
    return 0


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", default=os.getenv("HOME_ASSISTANT_URL", "http://127.0.0.1:8123"))
    ap.add_argument("--apply", action="store_true",
                    help="make the changes (default is a dry run)")
    return asyncio.run(run(ap.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
