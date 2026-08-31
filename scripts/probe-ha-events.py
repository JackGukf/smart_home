#!/usr/bin/env python3
"""Observe Home Assistant state changes over the WebSocket API.

Phase 0 of the automation design: prove the push event path works, learn what
the sensors actually emit, and measure how long a real motion event takes to
reach this process.  It executes nothing and controls no device.

The dashboard reads Home Assistant over blocking REST (``_home_assistant_get``
in ``src/python/web_app.py``), which only ever answers a question someone
asked.  Automation needs the opposite: to be told.  This script is the seed of
``src/python/automation/ha_events.py``.

Run it on the board, walk past a sensor, and read the log:

    .venv/bin/python scripts/probe-ha-events.py --seconds 300 --jsonl journal.jsonl
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiohttp

# Entities worth watching in Phase 0.  Substring match against entity_id and
# friendly name, so a sensor renamed in Home Assistant keeps being seen.
DEFAULT_INTERESTS = (
    "motion",
    "occupancy",
    "illuminance",
    "door",
    "presence",
    "pir",
)

# Domains that are never interesting no matter what they are called; the phone
# and the backup manager both produce steady traffic that would bury a sensor.
NOISE_PREFIXES = (
    "sensor.iphone_",
    "sensor.backup_",
    "sensor.sun_",
    "update.",
)


def _now() -> float:
    return time.time()


def _parse_ha_time(value: Any) -> float | None:
    """Parse Home Assistant's ISO timestamp into a POSIX float."""
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value).timestamp()
    except ValueError:
        return None


def _is_interesting(entity_id: str, friendly: str, interests: tuple[str, ...]) -> bool:
    if entity_id.startswith(NOISE_PREFIXES):
        return False
    haystack = f"{entity_id} {friendly}".lower()
    return any(term in haystack for term in interests)


class EventProbe:
    """Subscribe to ``state_changed`` and report matching transitions."""

    def __init__(
        self,
        base_url: str,
        token: str,
        interests: tuple[str, ...],
        jsonl: Path | None,
        show_all: bool,
    ) -> None:
        self._url = base_url.rstrip("/").replace("http", "ws", 1) + "/api/websocket"
        self._token = token
        self._interests = interests
        self._jsonl = jsonl
        self._show_all = show_all
        self._msg_id = 0
        self._seen = 0
        self._matched = 0
        self._latencies: list[float] = []

    def _next_id(self) -> int:
        self._msg_id += 1
        return self._msg_id

    async def run(self, seconds: float) -> int:
        deadline = _now() + seconds
        # A dropped connection is the normal case over days, not an error, so
        # reconnect with backoff rather than exiting.
        backoff = 1.0
        while _now() < deadline:
            try:
                await self._session(deadline)
                backoff = 1.0
            except (aiohttp.ClientError, asyncio.TimeoutError, ConnectionError) as error:
                remaining = deadline - _now()
                if remaining <= 0:
                    break
                print(f"  ! connection lost ({error}); retrying in {backoff:.0f}s", flush=True)
                await asyncio.sleep(min(backoff, remaining))
                backoff = min(backoff * 2, 30.0)
        self._summary()
        return 0

    async def _session(self, deadline: float) -> None:
        timeout = aiohttp.ClientTimeout(total=None, sock_connect=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.ws_connect(self._url, heartbeat=30) as ws:
                await self._authenticate(ws)
                await ws.send_json({"id": self._next_id(), "type": "subscribe_events",
                                    "event_type": "state_changed"})
                print(f"  subscribed to state_changed at {datetime.now():%H:%M:%S}", flush=True)
                print("  watching:", ", ".join(self._interests), flush=True)
                print("-" * 96, flush=True)

                while _now() < deadline:
                    remaining = deadline - _now()
                    try:
                        msg = await asyncio.wait_for(ws.receive(), timeout=remaining)
                    except asyncio.TimeoutError:
                        return
                    if msg.type is aiohttp.WSMsgType.TEXT:
                        self._handle(json.loads(msg.data))
                    elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                        raise ConnectionError("websocket closed")

    async def _authenticate(self, ws: aiohttp.ClientWebSocketResponse) -> None:
        greeting = await ws.receive_json()
        if greeting.get("type") != "auth_required":
            raise ConnectionError(f"unexpected greeting: {greeting.get('type')}")
        await ws.send_json({"type": "auth", "access_token": self._token})
        result = await ws.receive_json()
        if result.get("type") != "auth_ok":
            raise ConnectionError(f"authentication rejected: {result}")
        print(f"  authenticated to Home Assistant {result.get('ha_version', '?')}", flush=True)

    def _handle(self, message: dict[str, Any]) -> None:
        if message.get("type") != "event":
            return
        data = message.get("event", {}).get("data", {})
        new_state = data.get("new_state") or {}
        old_state = data.get("old_state") or {}
        entity_id = str(data.get("entity_id") or "")
        if not entity_id or not new_state:
            return

        self._seen += 1
        attributes = new_state.get("attributes") or {}
        friendly = str(attributes.get("friendly_name") or "")

        if not self._show_all and not _is_interesting(entity_id, friendly, self._interests):
            return

        before = str(old_state.get("state", "?"))
        after = str(new_state.get("state", "?"))
        if before == after:
            # An attribute-only update.  Not a transition, so not an event a
            # rule would ever fire on.
            return

        self._matched += 1
        received = _now()
        changed_at = _parse_ha_time(new_state.get("last_changed"))
        lag = received - changed_at if changed_at else None
        if lag is not None and 0 <= lag < 60:
            self._latencies.append(lag)

        lag_text = f"{lag * 1000:7.0f} ms" if lag is not None else "        -"
        print(
            f"{datetime.now():%H:%M:%S}  {entity_id:<46} "
            f"{before:>12} -> {after:<12} lag {lag_text}   {friendly[:28]}",
            flush=True,
        )

        if self._jsonl is not None:
            record = {
                "at": datetime.now(timezone.utc).isoformat(),
                "entity_id": entity_id,
                "friendly_name": friendly,
                "device_class": attributes.get("device_class"),
                "from": before,
                "to": after,
                "lag_seconds": round(lag, 3) if lag is not None else None,
            }
            with self._jsonl.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record) + "\n")

    def _summary(self) -> None:
        print("-" * 96, flush=True)
        print(f"  state_changed messages seen: {self._seen}")
        print(f"  transitions reported:        {self._matched}")
        if self._latencies:
            ordered = sorted(self._latencies)
            median = ordered[len(ordered) // 2]
            print(
                f"  delivery lag: min {min(ordered) * 1000:.0f} ms  "
                f"median {median * 1000:.0f} ms  max {max(ordered) * 1000:.0f} ms"
            )
            print("  (lag = Home Assistant's last_changed to arrival here; it excludes")
            print("   whatever the sensor and the Tuya cloud spent before that.)")
        else:
            print("  no transitions captured - walk past a sensor while this runs.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seconds", type=float, default=180.0,
                        help="How long to observe before summarising (default: 180).")
    parser.add_argument("--base-url", default=os.getenv("HOME_ASSISTANT_URL") or "http://127.0.0.1:8123",
                        help="Home Assistant base URL.")
    parser.add_argument("--token-env", default="HOME_ASSISTANT_TOKEN",
                        help="Environment variable holding the long-lived token.")
    parser.add_argument("--watch", action="append", dest="watch",
                        help="Substring to treat as interesting. Repeatable. Replaces the defaults.")
    parser.add_argument("--all", action="store_true",
                        help="Report every entity transition, not just the interesting ones.")
    parser.add_argument("--jsonl", type=Path,
                        help="Append observed transitions to this JSONL file.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token = os.getenv(args.token_env)
    if not token:
        print(f"No token in ${args.token_env}. Source the board's .env first:", file=sys.stderr)
        print("  set -a && . ./.env && set +a", file=sys.stderr)
        return 2

    interests = tuple(args.watch) if args.watch else DEFAULT_INTERESTS
    probe = EventProbe(args.base_url, token, interests, args.jsonl, args.all)

    print(f"  connecting to {args.base_url} for {args.seconds:.0f}s", flush=True)
    try:
        return asyncio.run(probe.run(args.seconds))
    except KeyboardInterrupt:
        probe._summary()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
