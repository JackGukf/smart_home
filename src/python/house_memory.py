"""The house's long-term memory: every event, kept, and what you said about it.

Phase 0 of the learning plan. Nothing here learns yet; it makes learning
possible. Home Assistant's recorder keeps ten days and then deletes them, and a
routine cannot be learned from ten days - every weekday has to be seen several
times, and heating behaviour needs a season of weather. So this keeps them:

  * **events** - every state change, from the live stream, plus the recorder's
    last ten days on first start and whatever a restart missed on every start
    after (idempotent: an event already here is not stored twice);
  * **entities** - names and kinds, so a model can tell a door from a lamp;
  * **feedback** - your labels ("normal", "false alarm", "unusual"), which are
    what the Phase 1 models learn from, and which cannot be recovered later.

SQLite in WAL mode: the collector writes, the dashboard reads and records
labels, and neither blocks the other.
"""

from __future__ import annotations

import json
import math
import os
import re
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

DEFAULT_DB_PATH = Path(os.getenv("HOUSE_MEMORY_DB", str(Path.home() / "house-memory" / "events.db")))

# Phase 1 needs every weekday seen this many times before a routine means
# anything; a day counts once it has events in most of its hours.
WEEKS_NEEDED = 4
DAY_COVERAGE_HOURS = 20
HEARTBEAT_STALE_S = 180
SUMMARY_CACHE_S = 60
SECURITY_CACHE_S = 20

# Domains whose state changes are not the house doing anything: a camera
# entity "changes" every time its snapshot token rotates, TTS and
# conversation are Assist's plumbing.
SKIP_DOMAINS = frozenset({"camera", "image", "update", "tts", "conversation", "stt", "wake_word"})
# Device health, not house activity. A model fed the voice panel's free PSRAM
# learns about the panel's allocator.
SKIP_ENTITY = re.compile(
    r"_(psram_free|heap_free|free_heap|rssi|linkquality|wifi_signal|uptime|last_seen|"
    r"last_restart|ip_address|firmware|update_state|voltage)$"
)

# Where the state alone misses the point. The thermostat's state is "heat" all
# winter; whether it is heating, and at what temperature, is in the
# attributes - and that is what the energy model will need.
TRACKED_ATTRIBUTES: dict[str, tuple[str, ...]] = {
    # equipment_running names what the thermostat actually switched on
    # ("auxHeat1", "fan", "compCool1"), which is how gas is told from cooling
    # and from the fan alone - the gas model reads it (src/python/gas_model.py).
    "climate": ("hvac_action", "equipment_running", "current_temperature", "temperature",
                "target_temp_low", "target_temp_high", "current_humidity", "preset_mode", "fan_mode"),
    "weather": ("temperature", "humidity", "wind_speed", "cloud_coverage"),
    "alarm_control_panel": (),
    "media_player": ("source", "app_name"),
}

LABELS = ("normal", "false_alarm", "unusual")

# Events worth a person's glance: someone seen, a door, a leak, the alarm.
REVIEW_CLASSES = frozenset({"door", "window", "garage_door", "opening", "smoke", "moisture", "gas",
                            "carbon_monoxide", "vibration"})
REVIEW_LIMIT = 6

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id           INTEGER PRIMARY KEY,
    ts           REAL    NOT NULL,
    entity_id    TEXT    NOT NULL,
    state        TEXT,
    old_state    TEXT,
    value        REAL,
    attrs        TEXT,
    source       TEXT    NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS events_entity_ts ON events (entity_id, ts);
CREATE INDEX IF NOT EXISTS events_ts ON events (ts);

CREATE TABLE IF NOT EXISTS entities (
    entity_id    TEXT PRIMARY KEY,
    name         TEXT,
    domain       TEXT,
    device_class TEXT,
    unit         TEXT,
    first_seen   REAL,
    last_seen    REAL
);

CREATE TABLE IF NOT EXISTS feedback (
    id           INTEGER PRIMARY KEY,
    event_id     INTEGER NOT NULL UNIQUE REFERENCES events (id),
    label        TEXT    NOT NULL,
    note         TEXT,
    created      REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


class FeedbackError(ValueError):
    """A label that is not one of ours, or an event that is not here."""


@dataclass(frozen=True)
class Event:
    ts: float
    entity_id: str
    state: str | None
    old_state: str | None
    value: float | None
    attrs: str | None


def connect(path: Path = DEFAULT_DB_PATH, readonly: bool = False) -> sqlite3.Connection:
    if readonly:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=10, check_same_thread=False)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, timeout=10, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.executescript(SCHEMA)
    conn.row_factory = sqlite3.Row
    return conn


def _domain(entity_id: str) -> str:
    return entity_id.split(".", 1)[0]


def wanted(entity_id: str) -> bool:
    return bool(entity_id) and "." in entity_id and _domain(entity_id) not in SKIP_DOMAINS \
        and not SKIP_ENTITY.search(entity_id)


def _parse_ts(raw: Any) -> float | None:
    if isinstance(raw, (int, float)):
        return float(raw)
    if not isinstance(raw, str):
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _number(state: Any) -> float | None:
    try:
        value = float(state)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _tracked(entity_id: str, attributes: dict[str, Any]) -> dict[str, Any] | None:
    keys = TRACKED_ATTRIBUTES.get(_domain(entity_id))
    if not keys:
        return None
    picked = {key: attributes[key] for key in keys if attributes.get(key) is not None}
    return picked or None


def event_from_states(entity_id: str, new: dict[str, Any] | None, old: dict[str, Any] | None) -> Event | None:
    """One stored event from a state change, or None when nothing happened.

    An attribute-only update is kept only where the attributes are the point
    (the thermostat starting to heat); everywhere else it is noise.
    """
    if not new or not wanted(entity_id):
        return None
    state = new.get("state")
    old_state = (old or {}).get("state")
    attrs = _tracked(entity_id, new.get("attributes") or {})
    old_attrs = _tracked(entity_id, (old or {}).get("attributes") or {})
    if old is not None and state == old_state and attrs == old_attrs:
        return None
    ts = _parse_ts(new.get("last_updated") or new.get("last_changed"))
    if ts is None:
        return None
    return Event(
        ts=ts, entity_id=entity_id,
        state=None if state is None else str(state)[:255],
        old_state=None if old_state is None else str(old_state)[:255],
        value=_number(state),
        attrs=json.dumps(attrs, sort_keys=True, separators=(",", ":")) if attrs else None,
    )


def events_from_history(series: Iterable[dict[str, Any]]) -> list[Event]:
    """The recorder's history for one entity, as the changes between its points.

    The first point is the state the window opened in, stamped with the
    window's start - not a change. It is only what the next point is compared
    with; storing it would add a fake event per entity per request.
    """
    out: list[Event] = []
    previous: dict[str, Any] | None = None
    entity_id = ""
    for point in series:
        entity_id = str(point.get("entity_id") or entity_id)
        if previous is not None:
            event = event_from_states(entity_id, point, previous)
            if event is not None:
                out.append(event)
        previous = point
    return out


class HouseMemory:
    """The store. One instance per process; methods are thread-safe."""

    def __init__(self, path: Path = DEFAULT_DB_PATH):
        self.path = path
        self._conn = connect(path)
        self._lock = threading.Lock()

    def close(self) -> None:
        self._conn.close()

    # ── writing ──────────────────────────────────────────────────────────────
    def add_events(self, events: Iterable[Event], source: str) -> int:
        rows = [(e.ts, e.entity_id, e.state, e.old_state, e.value, e.attrs, source) for e in events]
        if not rows:
            return 0
        with self._lock, self._conn:
            before = self._conn.total_changes
            self._conn.executemany(
                "INSERT OR IGNORE INTO events (ts, entity_id, state, old_state, value, attrs, source) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
            return self._conn.total_changes - before

    def upsert_entities(self, states: Iterable[dict[str, Any]], now: float | None = None) -> None:
        now = time.time() if now is None else now
        rows = []
        for state in states:
            entity_id = str(state.get("entity_id") or "")
            if not wanted(entity_id):
                continue
            attributes = state.get("attributes") or {}
            rows.append((entity_id, str(attributes.get("friendly_name") or entity_id), _domain(entity_id),
                         attributes.get("device_class"), attributes.get("unit_of_measurement"), now, now))
        with self._lock, self._conn:
            self._conn.executemany(
                "INSERT INTO entities (entity_id, name, domain, device_class, unit, first_seen, last_seen) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(entity_id) DO UPDATE SET "
                "name=excluded.name, device_class=excluded.device_class, unit=excluded.unit, "
                "last_seen=excluded.last_seen", rows)

    def set_meta(self, key: str, value: Any) -> None:
        with self._lock, self._conn:
            self._conn.execute("INSERT INTO meta (key, value) VALUES (?, ?) "
                               "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, json.dumps(value)))

    def get_meta(self, key: str, default: Any = None) -> Any:
        with self._lock:
            row = self._conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return default if row is None else json.loads(row[0])

    def last_event_ts(self) -> float | None:
        with self._lock:
            row = self._conn.execute("SELECT MAX(ts) FROM events").fetchone()
        return row[0]

    def label(self, event_id: int, label: str, note: str | None = None, now: float | None = None) -> dict[str, Any]:
        """Record what you said about an event; saying something else replaces it."""
        if label not in LABELS:
            raise FeedbackError(f"label must be one of {', '.join(LABELS)}")
        with self._lock, self._conn:
            if not self._conn.execute("SELECT 1 FROM events WHERE id = ?", (event_id,)).fetchone():
                raise FeedbackError("no such event")
            self._conn.execute(
                "INSERT INTO feedback (event_id, label, note, created) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(event_id) DO UPDATE SET label=excluded.label, note=excluded.note, "
                "created=excluded.created",
                (event_id, label, (note or "")[:500] or None, time.time() if now is None else now))
        return {"event_id": event_id, "label": label}

    # ── reading ──────────────────────────────────────────────────────────────
    def summary(self, tz_name: str = "UTC", now: float | None = None) -> dict[str, Any]:
        """What the Status tile shows: how much is kept, how far to Phase 1."""
        now = time.time() if now is None else now
        try:
            tz = ZoneInfo(tz_name)
        except (KeyError, ValueError):
            tz = ZoneInfo("UTC")
        with self._lock:
            c = self._conn
            total, first, last = c.execute("SELECT COUNT(*), MIN(ts), MAX(ts) FROM events").fetchone()
            entities = c.execute("SELECT COUNT(DISTINCT entity_id) FROM events").fetchone()[0]
            hourly = c.execute(
                "SELECT CAST(ts / 3600 AS INTEGER) AS h, COUNT(*) FROM events GROUP BY h").fetchall()
            labels = dict(c.execute("SELECT label, COUNT(*) FROM feedback GROUP BY label").fetchall())
            live = c.execute("SELECT COUNT(*) FROM events WHERE source = 'live'").fetchone()[0]
            review = self._review(c, now)

        per_day: dict[str, dict[str, Any]] = {}
        for hour, count in hourly:
            local = datetime.fromtimestamp(hour * 3600, tz)
            day = per_day.setdefault(local.date().isoformat(),
                                     {"events": 0, "hours": set(), "weekday": local.weekday()})
            day["events"] += count
            day["hours"].add(local.hour)
        today = datetime.fromtimestamp(now, tz).date().isoformat()
        complete = {d: v for d, v in per_day.items() if d != today and len(v["hours"]) >= DAY_COVERAGE_HOURS}
        weekdays = [0] * 7
        for info in complete.values():
            weekdays[info["weekday"]] += 1

        days = sorted(per_day)[-14:]
        heartbeat = self.get_meta("collector_heartbeat")
        size = sum(p.stat().st_size for p in self.path.parent.glob(self.path.name + "*") if p.is_file())
        return {
            "events": total,
            "entities": entities,
            "live_events": live,
            "first_ts": first,
            "last_ts": last,
            "events_today": per_day.get(today, {}).get("events", 0),
            "days_complete": len(complete),
            "weekday_coverage": weekdays,
            "weeks_needed": WEEKS_NEEDED,
            "ready": min(weekdays) >= WEEKS_NEEDED,
            "daily": [{"date": d, "events": per_day[d]["events"], "complete": d in complete} for d in days],
            "labels": {label: labels.get(label, 0) for label in LABELS},
            "db_bytes": size,
            "collector": {
                "heartbeat": heartbeat,
                "running": bool(heartbeat) and now - float(heartbeat) < HEARTBEAT_STALE_S,
                "backfilled_to": self.get_meta("backfill_from"),
            },
            "review": review,
            "time_zone": str(tz),
        }

    @staticmethod
    def _review(c: sqlite3.Connection, now: float) -> list[dict[str, Any]]:
        """Recent moments worth a label: someone seen by a camera, a door, a
        leak - the ones not yet labelled, newest first."""
        rows = c.execute(
            """SELECT e.id, e.ts, e.entity_id, e.state, n.name, n.device_class, f.label
               FROM events e
               LEFT JOIN entities n ON n.entity_id = e.entity_id
               LEFT JOIN feedback f ON f.event_id = e.id
               WHERE e.ts > ? AND e.state = 'on' AND e.old_state = 'off'
                 AND (e.entity_id LIKE 'binary_sensor.%npu_person' OR n.device_class IN ({}))
               ORDER BY e.ts DESC LIMIT 60""".format(",".join("?" * len(REVIEW_CLASSES))),
            (now - 86400, *sorted(REVIEW_CLASSES))).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            if row["label"]:
                continue
            kind = "camera" if row["entity_id"].endswith("_npu_person") else (row["device_class"] or "sensor")
            out.append({"id": row["id"], "ts": row["ts"], "entity_id": row["entity_id"],
                        "name": row["name"] or row["entity_id"], "kind": kind})
            if len(out) >= REVIEW_LIMIT:
                break
        return out


# ── Security activity: what happened, for the Security and Status views ──────

SECURITY_DOOR = frozenset({"door", "window", "garage_door", "opening"})
SECURITY_MOTION = frozenset({"motion", "occupancy", "presence"})
SECURITY_SAFETY = frozenset({"moisture", "smoke", "gas", "carbon_monoxide"})
# One sensor firing again within this long is the same moment, told once.
BURST_S = 10 * 60
RECENT_LIMIT = 12


def security_kind(entity_id: str, device_class: str | None) -> str | None:
    if entity_id.endswith("_npu_person"):
        return "camera"
    if device_class in SECURITY_DOOR:
        return "door"
    if device_class == "vibration":
        return "vibration"
    if device_class in SECURITY_SAFETY:
        return "safety"
    if device_class in SECURITY_MOTION:
        return "motion"
    return None


def fold_bursts(events: list[dict[str, Any]], window: float = BURST_S) -> list[dict[str, Any]]:
    """Newest first. A sensor that fires again within `window` of its previous
    firing joins that line: "Office camera, person, 4 times since 09:19"."""
    lines: list[dict[str, Any]] = []
    open_line: dict[str, dict[str, Any]] = {}
    for event in events:  # newest first
        line = open_line.get(event["entity_id"])
        if line is not None and line["first_ts"] - event["ts"] <= window:
            line["count"] += 1
            line["first_ts"] = event["ts"]
            continue
        line = {**event, "count": 1, "first_ts": event["ts"]}
        lines.append(line)
        open_line[event["entity_id"]] = line
    return lines


def security_activity(conn: sqlite3.Connection, tz_name: str, now: float,
                      limit: int = RECENT_LIMIT) -> dict[str, Any]:
    """The recent security events, folded, and today's counts since local midnight."""
    try:
        tz = ZoneInfo(tz_name)
    except (KeyError, ValueError):
        tz = ZoneInfo("UTC")
    midnight = datetime.fromtimestamp(now, tz).replace(hour=0, minute=0, second=0, microsecond=0)
    since = min(midnight.timestamp(), now - 86400)
    rows = conn.execute(
        """SELECT e.id, e.ts, e.entity_id, n.name, n.device_class
           FROM events e LEFT JOIN entities n ON n.entity_id = e.entity_id
           WHERE e.ts >= ? AND e.entity_id LIKE 'binary_sensor.%'
             AND e.state = 'on' AND e.old_state = 'off'
           ORDER BY e.ts DESC""", (since,)).fetchall()
    events = []
    for event_id, ts, entity_id, name, device_class in rows:
        kind = security_kind(entity_id, device_class)
        if kind:
            events.append({"id": event_id, "ts": ts, "entity_id": entity_id,
                           "name": name or entity_id, "kind": kind})

    today = midnight.timestamp()
    hours = [0] * 24
    counts = {"doors": 0, "people": 0, "motion": 0, "other": 0}
    for event in events:
        if event["ts"] < today:
            continue
        hours[datetime.fromtimestamp(event["ts"], tz).hour] += 1
        key = {"door": "doors", "camera": "people", "motion": "motion"}.get(event["kind"], "other")
        counts[key] += 1
    return {
        "recent": fold_bursts(events)[:limit],
        "today": {**counts, "hours": hours, "hour_now": datetime.fromtimestamp(now, tz).hour,
                  "since": today},
        "time_zone": str(tz),
    }


# While the alarm is armed, people outdoors are worth a log of their own
# (asked for 2026-09-24): the outdoor cameras' NPU person detection - the
# garage camera counts its driveway only (NPU_ZONES) - and the outdoor motion
# sensors, which see a person or an animal and cannot tell which.
OUTDOOR_PEOPLE = {
    "binary_sensor.front_door_camera_npu_person": "camera",
    "binary_sensor.frontyard_camera_npu_person": "camera",
    "binary_sensor.garage_camera_npu_person": "camera",
    "binary_sensor.0xa4c138f3061bad8d_presence": "motion",   # front door TH
    "binary_sensor.0xa4c1382ad5555219_presence": "motion",   # backyard
    "binary_sensor.0xa4c138b9f255ff1b_presence": "motion",   # fence south
}
ALARM_SPEAKER = "switch.0xa4c1382b1f1bd155_alarm"
ARMED_LOG_DAYS = 7
ARMED_LOG_LIMIT = 10


def _armed(state: str | None) -> bool:
    # Triggered and pending happen only on an armed panel.
    return bool(state) and (state.startswith("armed_") or state in ("triggered", "pending"))


def armed_spans(conn: sqlite3.Connection, since: float, now: float) -> list[tuple[float, float]]:
    """When the alarm was armed between `since` and `now`, from its own state changes."""
    before = conn.execute(
        """SELECT state FROM events WHERE entity_id LIKE 'alarm_control_panel.%' AND ts < ?
           ORDER BY ts DESC LIMIT 1""", (since,)).fetchone()
    start = since if before and _armed(before[0]) else None
    spans: list[tuple[float, float]] = []
    for ts, state in conn.execute(
            """SELECT ts, state FROM events WHERE entity_id LIKE 'alarm_control_panel.%' AND ts >= ?
               ORDER BY ts""", (since,)):
        if _armed(state) and start is None:
            start = ts
        elif not _armed(state) and start is not None:
            spans.append((start, ts))
            start = None
    if start is not None:
        spans.append((start, now))
    return spans


def armed_log(conn: sqlite3.Connection, now: float, days: int = ARMED_LOG_DAYS,
              limit: int = ARMED_LOG_LIMIT) -> dict[str, Any]:
    """People outdoors while the alarm was armed, and every time the alarm
    speaker sounded, newest first and folded like the activity list."""
    since = now - days * 86400
    spans = armed_spans(conn, since, now)
    watched = list(OUTDOOR_PEOPLE) + [ALARM_SPEAKER]
    marks = ",".join("?" * len(watched))
    rows = conn.execute(
        f"""SELECT e.id, e.ts, e.entity_id, n.name FROM events e
            LEFT JOIN entities n ON n.entity_id = e.entity_id
            WHERE e.ts >= ? AND e.entity_id IN ({marks}) AND e.state = 'on' AND e.old_state = 'off'
            ORDER BY e.ts DESC""", (since, *watched)).fetchall()
    events = []
    for event_id, ts, entity_id, name in rows:
        speaker = entity_id == ALARM_SPEAKER
        if not speaker and not any(start <= ts <= end for start, end in spans):
            continue
        events.append({"id": event_id, "ts": ts, "entity_id": entity_id,
                       "name": "Alarm speaker" if speaker else (name or entity_id),
                       "kind": "speaker" if speaker else OUTDOOR_PEOPLE[entity_id]})
    return {
        "recent": fold_bursts(events)[:limit],
        "armed_now": bool(spans) and spans[-1][1] == now,
        "days": days,
    }


class SummaryCache:
    """The dashboard's view of the store: read-only, cached briefly.

    Opened lazily, because the store is created by the collector and may not
    exist yet the first time the tile asks.
    """

    def __init__(self, path: Path = DEFAULT_DB_PATH, clock=time.time):
        self.path = path
        self._clock = clock
        self._memory: HouseMemory | None = None
        self._cache: tuple[float, str, dict[str, Any]] | None = None
        self._security_cache: tuple[float, str, dict[str, Any]] | None = None
        self._lock = threading.Lock()

    def _store(self) -> HouseMemory | None:
        if self._memory is None and self.path.exists():
            self._memory = HouseMemory(self.path)
        return self._memory

    def summary(self, tz_name: str) -> dict[str, Any]:
        now = self._clock()
        with self._lock:
            hit = self._cache
            if hit and hit[1] == tz_name and now - hit[0] < SUMMARY_CACHE_S:
                return hit[2]
            store = self._store()
            if store is None:
                return {"available": False}
            from src.python import house_learning  # imports this module; import here, not at the top
            result = {"available": True, **store.summary(tz_name, now)}
            with store._lock:
                result["learning"] = house_learning.learning_summary(store._conn, now)
            self._cache = (now, tz_name, result)
            return result

    def security(self, tz_name: str) -> dict[str, Any]:
        """Recent security events and today's counts, cached briefly: every open
        Security and Status view polls this."""
        now = self._clock()
        with self._lock:
            hit = self._security_cache
            if hit and hit[1] == tz_name and now - hit[0] < SECURITY_CACHE_S:
                return hit[2]
            store = self._store()
            if store is None:
                return {"available": False}
            with store._lock:
                result = {"available": True, **security_activity(store._conn, tz_name, now),
                          "armed": armed_log(store._conn, now)}
            self._security_cache = (now, tz_name, result)
            return result

    def label(self, event_id: int, label: str, note: str | None = None) -> dict[str, Any]:
        with self._lock:
            store = self._store()
            if store is None:
                raise FeedbackError("the house memory has not started yet")
            result = store.label(event_id, label, note)
            self._cache = None
            return result


def utc_iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
