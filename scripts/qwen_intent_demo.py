#!/usr/bin/env python3
"""Send a read-only smart-home intent demo request to a local Ollama server.

This script does not call Home Assistant, Matter, or any device API.  It only
asks Qwen to convert a natural-language request into a JSON proposal.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_DEVICES = ("kitchen_ceiling", "living_room_lamp")

INTENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "intent": {"type": "string"},
        "device_id": {"type": ["string", "null"]},
        "power": {"type": ["string", "null"]},
        "brightness_pct": {"type": ["integer", "null"]},
        "question": {"type": ["string", "null"]},
    },
    "required": ["intent", "device_id", "power", "brightness_pct", "question"],
}


def build_request(model: str, user_message: str, devices: tuple[str, ...]) -> dict[str, Any]:
    device_list = ", ".join(devices)
    system_message = (
        "You are a home-control intent parser. Return an object that matches "
        "the schema. Allowed devices: "
        f"{device_list}. Allowed action: set_light. "
        "If a device or request is ambiguous, set intent to clarify and ask a "
        "question. Never invent a device or action. If brightness was not "
        "requested, set brightness_pct to null."
    )
    return {
        "model": model,
        "think": False,
        "stream": False,
        "format": INTENT_SCHEMA,
        "options": {"temperature": 0, "num_predict": 80},
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ],
    }


def call_ollama(endpoint: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    request = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "message",
        nargs="?",
        default="Turn on the kitchen light",
        help="Natural-language request to parse.",
    )
    parser.add_argument("--model", default="qwen3:4b", help="Installed Ollama model.")
    parser.add_argument(
        "--endpoint",
        default="http://127.0.0.1:11434/api/chat",
        help="Local Ollama chat endpoint.",
    )
    parser.add_argument(
        "--device",
        action="append",
        dest="devices",
        help="Allowed device ID. Repeat to allow more than one device.",
    )
    parser.add_argument("--timeout", type=float, default=90, help="HTTP timeout in seconds.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    devices = tuple(args.devices or DEFAULT_DEVICES)
    payload = build_request(args.model, args.message, devices)

    try:
        response = call_ollama(args.endpoint, payload, args.timeout)
        proposal = json.loads(response["message"]["content"])
    except (HTTPError, URLError, TimeoutError, KeyError, json.JSONDecodeError) as error:
        print(f"Ollama demo failed: {error}", file=sys.stderr)
        return 1

    print(json.dumps(proposal, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
