"""Keep every Home Assistant event in the house memory.

    python -m src.python.house_memory_collector            # the service
    python -m src.python.house_memory_collector --backfill-only

On start it copies what the recorder still holds and the store does not: the
full ten days the first time, the gap since the last event after a restart or
a deploy. Then it follows the live ``state_changed`` stream. Both paths write
the same rows and the store ignores a row it already has, so an overlap costs
nothing and a gap is filled on the next start.

A dropped connection is the normal case over months, not an error: reconnect
with backoff, and fill the gap from history when back.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

import aiohttp

from src.python import house_memory as hm
from src.python.automation_author import ha_get, load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RECORDER_DAYS = 10
BACKFILL_CHUNK_S = 6 * 3600
BACKFILL_ENTITIES_PER_CALL = 40
HEARTBEAT_S = 60
FLUSH_S = 5.0


def log(message: str) -> None:
    print(message, flush=True)


def backfill(memory: hm.HouseMemory, base_url: str, token: str, now: float | None = None) -> int:
    """Copy what the recorder has and the store does not. Returns rows added."""
    now = time.time() if now is None else now
    states = ha_get(base_url, token, "/api/states", timeout=30)
    memory.upsert_entities(states, now)
    entity_ids = sorted(s["entity_id"] for s in states if hm.wanted(str(s.get("entity_id") or "")))

    last = memory.last_event_ts()
    # A few minutes of overlap: the last rows before a restart may not all
    # have been flushed, and a duplicate is ignored anyway.
    start = max(now - RECORDER_DAYS * 86400, (last - 300) if last else 0)
    if last is None:
        memory.set_meta("backfill_from", start)

    added = 0
    cursor = start
    while cursor < now:
        end = min(cursor + BACKFILL_CHUNK_S, now)
        for i in range(0, len(entity_ids), BACKFILL_ENTITIES_PER_CALL):
            batch = ",".join(entity_ids[i:i + BACKFILL_ENTITIES_PER_CALL])
            path = (f"/api/history/period/{quote(hm.utc_iso(cursor))}?end_time={quote(hm.utc_iso(end))}"
                    f"&filter_entity_id={batch}")
            try:
                history = ha_get(base_url, token, path, timeout=60)
            except OSError as error:
                log(f"  ! history {hm.utc_iso(cursor)} failed: {error}")
                continue
            events = [e for series in history for e in hm.events_from_history(series)
                      if cursor - 1 <= e.ts <= end]
            added += memory.add_events(events, "backfill")
        cursor = end
    return added


class Collector:
    def __init__(self, memory: hm.HouseMemory, base_url: str, token: str):
        self.memory = memory
        self.base_url = base_url
        self.token = token
        self.url = base_url.rstrip("/").replace("http", "ws", 1) + "/api/websocket"
        self.pending: list[hm.Event] = []
        self.seen = 0

    def handle(self, message: dict[str, Any]) -> None:
        if message.get("type") != "event":
            return
        data = (message.get("event") or {}).get("data") or {}
        entity_id = str(data.get("entity_id") or "")
        event = hm.event_from_states(entity_id, data.get("new_state"), data.get("old_state"))
        if event is not None:
            self.pending.append(event)
        new = data.get("new_state") or {}
        old = data.get("old_state")
        if old is None and new and hm.wanted(entity_id):
            # A new entity: remember its name and kind.
            self.memory.upsert_entities([{**new, "entity_id": entity_id}])

    def flush(self) -> None:
        if self.pending:
            batch, self.pending = self.pending, []
            self.seen += self.memory.add_events(batch, "live")

    async def session(self) -> None:
        timeout = aiohttp.ClientTimeout(total=None, sock_connect=10)
        async with aiohttp.ClientSession(timeout=timeout) as http:
            async with http.ws_connect(self.url, heartbeat=30, max_msg_size=0) as ws:
                greeting = await ws.receive_json()
                if greeting.get("type") != "auth_required":
                    raise ConnectionError(f"unexpected greeting: {greeting.get('type')}")
                await ws.send_json({"type": "auth", "access_token": self.token})
                result = await ws.receive_json()
                if result.get("type") != "auth_ok":
                    raise ConnectionError("authentication rejected")
                await ws.send_json({"id": 1, "type": "subscribe_events", "event_type": "state_changed"})
                log("  subscribed to state_changed")

                # Subscribed first, then the gap: anything that happens while
                # the history is being read arrives on the stream.
                added = await asyncio.to_thread(backfill, self.memory, self.base_url, self.token)
                log(f"  backfilled {added} events")

                last_flush = last_beat = 0.0
                while True:
                    try:
                        msg = await asyncio.wait_for(ws.receive(), timeout=FLUSH_S)
                    except asyncio.TimeoutError:
                        msg = None
                    if msg is not None:
                        if msg.type is aiohttp.WSMsgType.TEXT:
                            self.handle(json.loads(msg.data))
                        elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSING,
                                          aiohttp.WSMsgType.ERROR):
                            raise ConnectionError("websocket closed")
                    now = time.monotonic()
                    if now - last_flush >= FLUSH_S:
                        await asyncio.to_thread(self.flush)
                        last_flush = now
                    if now - last_beat >= HEARTBEAT_S:
                        self.memory.set_meta("collector_heartbeat", time.time())
                        last_beat = now

    async def run(self) -> None:
        backoff = 1.0
        while True:
            try:
                await self.session()
            except (aiohttp.ClientError, asyncio.TimeoutError, ConnectionError, OSError) as error:
                self.flush()
                log(f"  ! connection lost ({error}); retrying in {backoff:.0f}s")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60.0)
            else:
                backoff = 1.0


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default=os.getenv("HOME_ASSISTANT_BASE_URL", "http://127.0.0.1:8123"))
    parser.add_argument("--db", type=Path, default=hm.DEFAULT_DB_PATH)
    parser.add_argument("--backfill-only", action="store_true")
    args = parser.parse_args()

    token = os.getenv("HOME_ASSISTANT_TOKEN")
    if not token:
        log("HOME_ASSISTANT_TOKEN is not set (looked in .env)")
        return 1

    memory = hm.HouseMemory(args.db)
    log(f"house memory at {args.db}")
    if args.backfill_only:
        log(f"backfilled {backfill(memory, args.base_url, token)} events")
        return 0
    try:
        asyncio.run(Collector(memory, args.base_url, token).run())
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
