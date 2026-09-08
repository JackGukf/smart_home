#!/usr/bin/env python3
"""Show which agent answers a sentence, and how long it takes.

The point of the Ollama wiring on this board is that the local model is a
*fallback*: Home Assistant's own sentence matcher keeps answering the things it
understands in milliseconds, and only what it does not understand waits on a 4B
model generating at ~15 tok/s. That is a claim about routing, and routing is
invisible from the Assist dialog - a right answer looks the same whether it took
30 ms or 14 s.

This runs sentences through a real Assist pipeline and prints, for each one,
which agent handled it, whether it was handled locally, and the wall time. A
regression here looks like every sentence suddenly reporting the Ollama agent.

    ~/smart_home_AI/.venv/bin/python scripts/check-assist-routing.py
    ~/smart_home_AI/.venv/bin/python scripts/check-assist-routing.py \\
        --pipeline "Local Qwen (control)"

The default sentences only ask questions. Anything you pass yourself is really
spoken to the house, so `--say "turn off the kitchen light"` will turn off the
kitchen light.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Read-only on purpose. The first two are sentences Home Assistant's matcher
# can answer from the house; the third is one it cannot possibly know, so it
# has to fall through to the model.
#
# Note the first uses the sensor's full name. "is the front door open" does
# NOT match, because the entity is called "Door sensor front door" - the
# matcher matches names and aliases, not paraphrases. Anything you want
# answered instantly needs an alias that matches how you actually say it.
DEFAULT_SENTENCES = [
    "is the door sensor front door open",
    "how many lights are on",
    "what humidity should a bedroom be at night",
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


def speech_of(intent_output: dict) -> str:
    try:
        return intent_output["response"]["speech"]["plain"]["speech"]
    except (KeyError, TypeError):
        return ""


async def run_one(ws: Any, msg_id: int, pipeline_id: str, text: str,
                  timeout: float) -> tuple[str, bool, str, float]:
    """Run one sentence, returning (agent, processed_locally, speech, seconds)."""
    started = time.monotonic()
    await ws.send_json({
        "id": msg_id,
        "type": "assist_pipeline/run",
        "start_stage": "intent",
        "end_stage": "intent",
        "input": {"text": text},
        "pipeline": pipeline_id,
    })

    agent, locally, speech = "?", False, ""
    while True:
        remaining = timeout - (time.monotonic() - started)
        if remaining <= 0:
            return "timeout", False, "", time.monotonic() - started
        message = await asyncio.wait_for(ws.receive_json(), timeout=remaining)
        if message.get("id") != msg_id:
            continue
        if message.get("type") == "result" and not message.get("success"):
            error = message.get("error", {})
            return "error", False, str(error.get("message", error)), time.monotonic() - started
        if message.get("type") != "event":
            continue
        event = message["event"]
        if event["type"] == "intent-start":
            # The pipeline names its configured agent here. Which one actually
            # answered is only knowable from processed_locally, below.
            agent = event["data"].get("engine") or "?"
        elif event["type"] == "intent-end":
            locally = bool(event["data"].get("processed_locally"))
            speech = speech_of(event["data"]["intent_output"])
        elif event["type"] in ("run-end", "error"):
            if event["type"] == "error":
                return "error", False, str(event["data"].get("message", "")), \
                    time.monotonic() - started
            return agent, locally, speech, time.monotonic() - started


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

    base = args.base_url.rstrip("/")
    ws_url = base.replace("https://", "wss://").replace("http://", "ws://") + "/api/websocket"
    sentences = args.say or DEFAULT_SENTENCES

    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(ws_url, heartbeat=30) as ws:
            await ws.receive_json()
            await ws.send_json({"type": "auth", "access_token": token})
            if (await ws.receive_json()).get("type") != "auth_ok":
                print("Home Assistant rejected the token", file=sys.stderr)
                return 1

            await ws.send_json({"id": 1, "type": "assist_pipeline/pipeline/list"})
            listing = (await ws.receive_json())["result"]
            pipelines = listing["pipelines"] if isinstance(listing, dict) else listing

            chosen = next((p for p in pipelines if p["name"] == args.pipeline), None)
            if chosen is None:
                names = ", ".join(repr(p["name"]) for p in pipelines)
                print(f"no pipeline named {args.pipeline!r} (have: {names})", file=sys.stderr)
                return 1

            print(f"pipeline {chosen['name']!r}: agent={chosen['conversation_engine']} "
                  f"prefer_local_intents={bool(chosen.get('prefer_local_intents'))}\n")

            msg_id = 1
            for text in sentences:
                msg_id += 1
                agent, locally, speech, seconds = await run_one(
                    ws, msg_id, chosen["id"], text, args.timeout)
                who = "local matcher" if locally else agent
                where = "local" if locally else "MODEL"
                print(f"  {seconds:6.2f}s  {where:5}  {who}")
                print(f"          {text!r}")
                print(f"       -> {speech.strip()[:300] or '(no speech)'}\n")
    return 0


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pipeline", default="Home Assistant")
    ap.add_argument("--say", action="append",
                    help="a sentence to try; repeatable. These really are spoken "
                         "to the house, so a command will be carried out.")
    ap.add_argument("--timeout", type=float, default=180.0)
    ap.add_argument("--base-url", default=os.getenv("HOME_ASSISTANT_BASE_URL",
                                                    "http://127.0.0.1:8123"))
    return asyncio.run(run(ap.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
