"""The house's motion routine, by area, for the Motion view.

For each area the page names (its motion sensors, and the cameras' person
detection), from the house memory:

  * **usual** - for each hour of the day, the share of the last 14 days that
    had any motion in that area in that hour. An area is its sensors together:
    a day counts once however many of them saw it.
  * **day** - the chosen day's motion in 5-minute steps (minutes since
    midnight), so a timeline can draw it without the raw events.
  * **last** - when the area last saw motion.

The page decides which sensors make an area - it knows the dashboard's own
area assignments. The cameras' person detection is not among the page's
devices, so the cameras are found here, in the history itself
(`..._npu_person`), and joined to the area with their name: "Office Camera"
to Office, "Frontyard" to Front Yard. A camera no area matches becomes an
area of its own (the Garage). All of it reads the history only, so it is
testable without Home Assistant. "Unusual" - motion in an hour that is almost
always quiet - is left to the page, which draws it.
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

USUAL_DAYS = 14
STEP_MINUTES = 5
ON_STATES = ("on", "detected", "occupied")


CAMERA_SUFFIX = "_camera_npu_person"


def _plain(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def with_cameras(conn: sqlite3.Connection, areas: dict[str, list[str]]) -> dict[str, list[str]]:
    """The areas with each camera's person detection joined by name."""
    joined = {name: list(entities) for name, entities in areas.items()}
    by_plain = {_plain(name): name for name in areas}
    cameras = [row[0] for row in conn.execute(
        "SELECT DISTINCT entity_id FROM events WHERE entity_id LIKE ?", (f"binary_sensor.%{CAMERA_SUFFIX}",))]
    for entity in sorted(cameras):
        place = entity.split(".", 1)[1][: -len(CAMERA_SUFFIX)]
        name = by_plain.get(_plain(place)) or place.replace("_", " ").title()
        joined.setdefault(name, [])
        if entity not in joined[name]:
            joined[name].append(entity)
    return joined


def _midnight(day: date) -> datetime:
    return datetime.combine(day, datetime.min.time())


def routine(conn: sqlite3.Connection, areas: dict[str, list[str]], day: date,
            now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now()
    first = _midnight(day - timedelta(days=USUAL_DAYS))
    end = min(_midnight(day + timedelta(days=1)), now)
    owner = {entity: name for name, entities in areas.items() for entity in entities}
    result: dict[str, dict[str, Any]] = {
        name: {"hours": [set() for _ in range(24)], "day": set(), "last": None} for name in areas
    }
    if owner:
        marks = ",".join("?" * len(owner))
        rows = conn.execute(
            f"SELECT ts, entity_id FROM events WHERE entity_id IN ({marks}) AND ts >= ? AND ts < ?"
            f" AND lower(state) IN ({','.join('?' * len(ON_STATES))}) ORDER BY ts",
            (*owner, first.timestamp(), end.timestamp(), *ON_STATES))
        today = _midnight(day)
        for ts, entity in rows:
            area = result[owner[entity]]
            at = datetime.fromtimestamp(ts)
            if at < today:
                area["hours"][at.hour].add(at.date())
            else:
                minute = at.hour * 60 + at.minute
                area["day"].add(minute - minute % STEP_MINUTES)
        # Last motion looks further back than the window, for an area that has
        # been quiet a long time.
        for name, entities in areas.items():
            if not entities:
                continue
            found = conn.execute(
                f"SELECT max(ts) FROM events WHERE entity_id IN ({','.join('?' * len(entities))})"
                f" AND ts < ? AND lower(state) IN ({','.join('?' * len(ON_STATES))})",
                (*entities, now.timestamp(), *ON_STATES)).fetchone()[0]
            result[name]["last"] = found
    return {
        "day": day.isoformat(),
        "days": USUAL_DAYS,
        "step_minutes": STEP_MINUTES,
        "now": now.timestamp(),
        "areas": {
            name: {
                "usual": [round(len(h) / USUAL_DAYS, 2) for h in area["hours"]],
                "day": sorted(area["day"]),
                "last": area["last"],
                "entities": areas[name],
            }
            for name, area in result.items()
        },
    }


def routine_from_path(path: Path, areas: dict[str, list[str]], day: date,
                      now: datetime | None = None) -> dict[str, Any]:
    from src.python import house_memory

    conn = house_memory.connect(path, readonly=True)
    try:
        return routine(conn, with_cameras(conn, areas), day, now)
    finally:
        conn.close()
