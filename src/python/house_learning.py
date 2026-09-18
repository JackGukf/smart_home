"""Phase 1: learn the house's routine from the house memory, every night.

    python -m src.python.house_learning             # the nightly run
    python -m src.python.house_learning --print     # and show what it found

What it learns, per sensor that says someone is about (room motion, cameras,
doors) and for the house as a whole: how likely each hour of each weekday is
to see activity, and how many events that hour usually brings.

The model is deliberately small - smoothed, recency-weighted rates - because
one house makes little data: a few thousand sensor-hours a week. Each
estimate borrows from a broader one when it has seen too little (this
Tuesday-at-3am from any-day-at-3am, that from the sensor's overall rate), so
it gives sensible answers from the first week and sharper ones as the weeks
add up. Recent days count more (a half-life), so a changed routine is picked
up rather than averaged away.

"Smarter every day" is measured, not assumed. Each night:

  1. every candidate configuration is trained on all but the last few
     complete days and scored on those days (Brier score: how far the
     predicted chance of activity was from what happened);
  2. the best replaces the current one only if it beats it on the same days -
     a worse model is never deployed;
  3. the winner is retrained on everything and saved, and the scores go into
     model_runs, so the trend is visible on the Status view.

Then, silently, it looks at the recent hours for what the routine did not
expect - activity at an hour that is almost always quiet, an hour far busier
than usual, a room that has gone silent - and records them in shadow_alerts.
Nothing is sent. Your labels on those moments are how its precision is
measured before it is ever allowed to alert.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from src.python import house_memory as hm

HOURS = 24
HOUSE = "house"
MIN_TRAIN_DAYS = 3
READY_DAYS = hm.WEEKS_NEEDED * 7

# Candidates the nightly run chooses between. Small on purpose: every one is
# scored on held-out days, and a large grid on little data picks noise.
CONFIGS: tuple[dict[str, Any], ...] = tuple(
    {"half_life_days": half_life, "weekday_strength": strength, "profile": profile}
    for half_life in (14, 28, 56)
    for strength in (1.0, 3.0)
    for profile in ("weekday", "workweek")
)
DEFAULT_CONFIG = {"half_life_days": 28, "weekday_strength": 3.0, "profile": "weekday"}
# Replace the champion only for a real improvement, not for rounding.
PROMOTE_MARGIN = 0.005
HOUR_STRENGTH = 2.0

# Shadow alerts. Support is how many days of that hour the estimate stands on.
UNUSUAL_P = 0.05
MIN_SUPPORT_DAYS = 5
QUIET_P = 0.9
QUIET_HOURS = 3
BUSY_SIGMAS = 4.0
ALERT_LOOKBACK_H = 48

SIGNAL_CLASSES = frozenset({"motion", "occupancy", "presence"})
DOOR_CLASSES = frozenset({"door", "window", "garage_door", "opening", "vibration"})
OUTDOOR = re.compile(r"front ?door|front ?yard|back ?yard|garage|porch|drive ?way|garden|patio", re.I)
ON, OFF, MISSING = "on", "off", "missing"

LEARNING_SCHEMA = """
CREATE TABLE IF NOT EXISTS model_runs (
    id        INTEGER PRIMARY KEY,
    ts        REAL NOT NULL,
    through   TEXT NOT NULL,
    days      INTEGER NOT NULL,
    config    TEXT NOT NULL,
    metrics   TEXT NOT NULL,
    promoted  INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS shadow_alerts (
    id          INTEGER PRIMARY KEY,
    hour_ts     REAL NOT NULL,
    entity_id   TEXT NOT NULL,
    kind        TEXT NOT NULL,
    score       REAL NOT NULL,
    detail      TEXT NOT NULL,
    event_id    INTEGER,
    suppressed  INTEGER NOT NULL DEFAULT 0,
    run_id      INTEGER,
    UNIQUE (entity_id, hour_ts, kind)
);
"""


# ── which sensors, and what they are ─────────────────────────────────────────

@dataclass(frozen=True)
class Signal:
    entity_id: str
    name: str
    kind: str        # room | outdoor | camera | door
    indoor: bool


def signals_from_entities(rows: Iterable[sqlite3.Row | dict]) -> list[Signal]:
    out = []
    for row in rows:
        entity_id, name, device_class = row["entity_id"], row["name"] or row["entity_id"], row["device_class"]
        if not entity_id.startswith("binary_sensor."):
            continue
        outdoor = bool(OUTDOOR.search(name))
        if entity_id.endswith("_npu_person"):
            out.append(Signal(entity_id, name, "camera", not outdoor))
        elif device_class in SIGNAL_CLASSES:
            out.append(Signal(entity_id, name, "outdoor" if outdoor else "room", not outdoor))
        elif device_class in DOOR_CLASSES:
            out.append(Signal(entity_id, name, "door", False))
    return sorted(out, key=lambda s: s.entity_id)


# ── the hourly picture ────────────────────────────────────────────────────────

@dataclass
class Cell:
    active: int
    rises: int
    first_event: int | None = None


def _category(state: str | None) -> str:
    if state == "on":
        return ON
    if state == "off":
        return OFF
    return MISSING


def hourly_cells(rows: Iterable[tuple[int, float, str | None, str | None]], start_h: int,
                 end_h: int) -> dict[int, Cell]:
    """One entity's events as UTC-hour cells in [start_h, end_h).

    An hour is active if something *happened* in it - the sensor went from
    off to on - not merely if it was on. A camera holding "person" for hours
    over a static shape, an occupancy sensor stuck on, a window left open
    overnight: all "on", none of them someone moving. Counted as activity,
    they made the house look busy at 3am every night.

    An hour with no event is inactive if the state was known through it (on
    or off), and absent - no data - if it was not: before the first event,
    or while the device was unavailable.
    """
    spans: list[tuple[float, float, str]] = []
    rises: dict[int, list[int]] = {}
    current: str | None = None
    since = 0.0
    for event_id, ts, state, old_state in rows:
        if current is None:
            current, since = _category(old_state), ts
            # Before the first event nothing is known; from it, the old state
            # is known only for that instant.
        spans.append((since, ts, current))
        new = _category(state)
        if new == ON and old_state == "off":
            rises.setdefault(int(ts // 3600), []).append(event_id)
        current, since = new, ts
    if current is not None:
        spans.append((since, end_h * 3600.0, current))

    cells: dict[int, Cell] = {}
    known: set[int] = set()
    for begin, finish, category in spans:
        if finish <= begin or category == MISSING:
            continue
        first = max(int(begin // 3600), start_h)
        last = min(int((finish - 1e-6) // 3600), end_h - 1)
        known.update(range(first, last + 1))
    for hour in known:
        cells.setdefault(hour, Cell(0, 0))
    for hour, ids in rises.items():
        if start_h <= hour < end_h:
            cell = cells.setdefault(hour, Cell(1, 0))
            cell.active = 1
            cell.rises += len(ids)
            cell.first_event = ids[0]
    return cells


def house_cells(per_signal: dict[str, dict[int, Cell]], signals: list[Signal]) -> dict[int, Cell]:
    """The house as one signal: active when any indoor sensor or camera is."""
    indoor = [s.entity_id for s in signals if s.indoor and s.kind in ("room", "camera")]
    out: dict[int, Cell] = {}
    for entity_id in indoor:
        for hour, cell in per_signal.get(entity_id, {}).items():
            merged = out.setdefault(hour, Cell(0, 0))
            merged.active = max(merged.active, cell.active)
            merged.rises += cell.rises
    return out


@dataclass
class Frame:
    """Every signal's cells, with each UTC hour's local date, weekday and hour."""
    tz: ZoneInfo
    cells: dict[str, dict[int, Cell]]
    signals: list[Signal]
    local: dict[int, tuple[date, int, int]] = field(default_factory=dict)

    def at(self, hour: int) -> tuple[date, int, int]:
        hit = self.local.get(hour)
        if hit is None:
            moment = datetime.fromtimestamp(hour * 3600, self.tz)
            hit = self.local[hour] = (moment.date(), moment.weekday(), moment.hour)
        return hit


def load_frame(conn: sqlite3.Connection, tz: ZoneInfo, end_ts: float) -> Frame:
    conn.row_factory = sqlite3.Row
    signals = signals_from_entities(conn.execute(
        "SELECT entity_id, name, device_class FROM entities WHERE domain = 'binary_sensor'").fetchall())
    first = conn.execute("SELECT MIN(ts) FROM events").fetchone()[0]
    start_h = int(first // 3600) if first else int(end_ts // 3600)
    end_h = int(end_ts // 3600)
    cells: dict[str, dict[int, Cell]] = {}
    for signal in signals:
        rows = conn.execute(
            "SELECT id, ts, state, old_state FROM events WHERE entity_id = ? AND ts < ? ORDER BY ts",
            (signal.entity_id, end_ts)).fetchall()
        cells[signal.entity_id] = hourly_cells([tuple(r) for r in rows], start_h, end_h)
    cells[HOUSE] = house_cells(cells, signals)
    return Frame(tz, cells, signals)


def complete_days(frame: Frame, today: date) -> list[date]:
    """Local days before today with the house signal known for most hours."""
    hours: dict[date, int] = {}
    for hour in frame.cells.get(HOUSE, {}):
        day = frame.at(hour)[0]
        hours[day] = hours.get(day, 0) + 1
    return sorted(d for d, n in hours.items() if d < today and n >= hm.DAY_COVERAGE_HOURS)


# ── the model ─────────────────────────────────────────────────────────────────

def _group(weekday: int, profile: str) -> int:
    return weekday if profile == "weekday" else (0 if weekday < 5 else 1)


@dataclass
class SignalModel:
    p: list[list[float]]          # [weekday][hour] chance of activity
    rate: list[list[float]]       # [weekday][hour] expected events
    support: list[int]            # [hour] days that hour was seen, any weekday
    overall: float


def fit(frame: Frame, days: list[date], config: dict[str, Any]) -> dict[str, SignalModel]:
    """Train on `days`. Recent days weigh more; thin estimates borrow."""
    if not days:
        return {}
    keep = set(days)
    reference = max(days)
    half_life = float(config["half_life_days"])
    strength = float(config["weekday_strength"])
    profile = config["profile"]
    groups = 7 if profile == "weekday" else 2
    models: dict[str, SignalModel] = {}
    for entity_id, cells in frame.cells.items():
        hour_w = [0.0] * HOURS
        hour_a = [0.0] * HOURS
        hour_r = [0.0] * HOURS
        support = [0] * HOURS
        grp_w = [[0.0] * HOURS for _ in range(groups)]
        grp_a = [[0.0] * HOURS for _ in range(groups)]
        grp_r = [[0.0] * HOURS for _ in range(groups)]
        for utc_hour, cell in cells.items():
            day, weekday, hour = frame.at(utc_hour)
            if day not in keep:
                continue
            weight = 0.5 ** ((reference - day).days / half_life)
            g = _group(weekday, profile)
            hour_w[hour] += weight
            hour_a[hour] += weight * cell.active
            hour_r[hour] += weight * cell.rises
            support[hour] += 1
            grp_w[g][hour] += weight
            grp_a[g][hour] += weight * cell.active
            grp_r[g][hour] += weight * cell.rises
        total_w = sum(hour_w)
        if total_w == 0:
            continue
        overall = (sum(hour_a) + 0.5) / (total_w + 1.0)
        overall_rate = sum(hour_r) / total_w
        by_hour = [(hour_a[h] + HOUR_STRENGTH * overall) / (hour_w[h] + HOUR_STRENGTH) for h in range(HOURS)]
        rate_by_hour = [(hour_r[h] + HOUR_STRENGTH * overall_rate) / (hour_w[h] + HOUR_STRENGTH) for h in range(HOURS)]
        p = []
        rate = []
        for weekday in range(7):
            g = _group(weekday, profile)
            p.append([(grp_a[g][h] + strength * by_hour[h]) / (grp_w[g][h] + strength) for h in range(HOURS)])
            rate.append([(grp_r[g][h] + strength * rate_by_hour[h]) / (grp_w[g][h] + strength) for h in range(HOURS)])
        models[entity_id] = SignalModel(p, rate, support, overall)
    return models


def score(frame: Frame, models: dict[str, SignalModel], days: list[date]) -> dict[str, Any]:
    """How well the models predicted `days`, against a guess that ignores the clock.

    Brier: the mean squared gap between the predicted chance and what
    happened (0 is perfect, 0.25 is a coin toss). The baseline predicts each
    sensor's overall rate for every hour - what you would say knowing how
    busy a sensor is but not when.
    """
    keep = set(days)
    brier = base = 0.0
    n = 0
    house = {"n": 0, "right": 0, "base_right": 0, "brier": 0.0}
    for entity_id, cells in frame.cells.items():
        model = models.get(entity_id)
        if model is None:
            continue
        majority = 1 if model.overall >= 0.5 else 0
        for utc_hour, cell in cells.items():
            day, weekday, hour = frame.at(utc_hour)
            if day not in keep:
                continue
            p = model.p[weekday][hour]
            brier += (p - cell.active) ** 2
            base += (model.overall - cell.active) ** 2
            n += 1
            if entity_id == HOUSE:
                house["n"] += 1
                house["brier"] += (p - cell.active) ** 2
                house["right"] += int((p >= 0.5) == bool(cell.active))
                house["base_right"] += int(majority == cell.active)
    if not n:
        return {"cells": 0}
    return {
        "cells": n,
        "brier": round(brier / n, 5),
        "brier_baseline": round(base / n, 5),
        "skill": round(1 - (brier / base), 4) if base else 0.0,
        "house_accuracy": round(house["right"] / house["n"], 4) if house["n"] else None,
        "house_baseline_accuracy": round(house["base_right"] / house["n"], 4) if house["n"] else None,
        "house_brier": round(house["brier"] / house["n"], 5) if house["n"] else None,
    }


def split(days: list[date]) -> tuple[list[date], list[date]]:
    """Hold out the most recent days: a week once there are three, fewer before."""
    test = 7 if len(days) >= 21 else max(1, len(days) // 3)
    return days[:-test], days[-test:]


def choose(frame: Frame, days: list[date], champion: dict[str, Any] | None) -> dict[str, Any]:
    """Score every candidate on the same held-out days; keep the champion
    unless one beats it by a margin."""
    train, test = split(days)
    scored = []
    for config in CONFIGS:
        metrics = score(frame, fit(frame, train, config), test)
        if metrics.get("cells"):
            scored.append((metrics["brier"], config, metrics))
    if not scored:
        return {"config": champion or DEFAULT_CONFIG, "metrics": {"cells": 0}, "promoted": False,
                "train_days": len(train), "test_days": len(test), "candidates": 0}
    scored.sort(key=lambda item: item[0])
    best_brier, best, best_metrics = scored[0]
    current = next(((b, c, m) for b, c, m in scored if c == champion), None)
    promoted = current is None or best_brier < current[0] * (1 - PROMOTE_MARGIN)
    chosen, chosen_metrics = (best, best_metrics) if promoted else (current[1], current[2])
    return {
        "config": chosen,
        "metrics": chosen_metrics,
        "promoted": promoted and chosen != champion,
        "train_days": len(train),
        "test_days": len(test),
        "candidates": len(scored),
    }


# ── what the routine did not expect ───────────────────────────────────────────

@dataclass(frozen=True)
class Alert:
    hour_ts: float
    entity_id: str
    kind: str          # unusual_time | unusually_busy | unusually_quiet
    score: float
    detail: str
    event_id: int | None


def find_alerts(frame: Frame, models: dict[str, SignalModel], start_h: int, end_h: int) -> list[Alert]:
    alerts: list[Alert] = []
    for signal in frame.signals:
        model = models.get(signal.entity_id)
        cells = frame.cells.get(signal.entity_id, {})
        if model is None:
            continue
        quiet_run: list[int] = []
        for utc_hour in range(start_h, end_h):
            cell = cells.get(utc_hour)
            _, weekday, hour = frame.at(utc_hour)
            p = model.p[weekday][hour]
            supported = model.support[hour] >= MIN_SUPPORT_DAYS
            if cell is None or not supported:
                quiet_run = []
                continue
            if cell.active and p < UNUSUAL_P:
                alerts.append(Alert(utc_hour * 3600.0, signal.entity_id, "unusual_time",
                                    round(-math.log10(max(p, 1e-6)), 2),
                                    f"active at {hour:02d}:00, which it is on {p:.0%} of the time",
                                    cell.first_event))
            expected = model.rate[weekday][hour]
            if cell.rises > expected + BUSY_SIGMAS * math.sqrt(max(expected, 0.25)) + 3:
                alerts.append(Alert(utc_hour * 3600.0, signal.entity_id, "unusually_busy",
                                    round((cell.rises - expected) / math.sqrt(max(expected, 0.25)), 2),
                                    f"{cell.rises} events at {hour:02d}:00, about {expected:.0f} is usual",
                                    cell.first_event))
            if signal.kind == "room" and not cell.active and p >= QUIET_P:
                quiet_run.append(utc_hour)
                if len(quiet_run) == QUIET_HOURS:
                    alerts.append(Alert(quiet_run[0] * 3600.0, signal.entity_id, "unusually_quiet",
                                        float(QUIET_HOURS),
                                        f"quiet for {QUIET_HOURS} hours from "
                                        f"{frame.at(quiet_run[0])[2]:02d}:00, usually busy then",
                                        None))
            else:
                quiet_run = []
    return alerts


def known_normal(conn: sqlite3.Connection, tz: ZoneInfo) -> set[tuple[str, int]]:
    """(entity, local hour) pairs you have said are fine, for suppression."""
    rows = conn.execute(
        "SELECT e.entity_id, e.ts FROM feedback f JOIN events e ON e.id = f.event_id "
        "WHERE f.label IN ('normal', 'false_alarm')").fetchall()
    out = set()
    for entity_id, ts in rows:
        hour = datetime.fromtimestamp(ts, tz).hour
        for near in (hour - 1, hour, hour + 1):
            out.add((entity_id, near % 24))
    return out


# ── the nightly run ───────────────────────────────────────────────────────────

def _model_json(frame: Frame, models: dict[str, SignalModel], config: dict[str, Any]) -> dict[str, Any]:
    names = {s.entity_id: s for s in frame.signals}
    return {
        "config": config,
        "signals": {
            entity_id: {
                "name": names[entity_id].name if entity_id in names else "The house",
                "kind": names[entity_id].kind if entity_id in names else HOUSE,
                "p": [[round(v, 4) for v in row] for row in m.p],
                "rate": [[round(v, 3) for v in row] for row in m.rate],
                "support": m.support,
                "overall": round(m.overall, 4),
            }
            for entity_id, m in models.items()
        },
    }


def run(db_path: Path, tz_name: str, now: float | None = None, models_dir: Path | None = None) -> dict[str, Any]:
    now = time.time() if now is None else now
    tz = ZoneInfo(tz_name)
    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(hm.SCHEMA + LEARNING_SCHEMA)
    conn.row_factory = sqlite3.Row
    try:
        frame = load_frame(conn, tz, now)
        today = datetime.fromtimestamp(now, tz).date()
        days = complete_days(frame, today)
        status = "collecting" if len(days) < MIN_TRAIN_DAYS else "warming_up" if len(days) < READY_DAYS else "learning"
        if status == "collecting":
            return {"status": status, "days": len(days)}

        row = conn.execute("SELECT value FROM meta WHERE key = 'learning_champion'").fetchone()
        champion = json.loads(row[0]) if row else None
        choice = choose(frame, days, champion)
        models = fit(frame, days, choice["config"])

        metrics = {**choice["metrics"], "train_days": choice["train_days"], "test_days": choice["test_days"],
                   "candidates": choice["candidates"], "status": status, "tz": tz_name}
        with conn:
            cursor = conn.execute(
                "INSERT INTO model_runs (ts, through, days, config, metrics, promoted) VALUES (?, ?, ?, ?, ?, ?)",
                (now, days[-1].isoformat(), len(days), json.dumps(choice["config"]), json.dumps(metrics),
                 int(choice["promoted"])))
            run_id = cursor.lastrowid
            for key, value in (("learning_champion", choice["config"]),
                               ("learning_tz", tz_name),
                               ("learning_house_routine", _model_json(frame, {HOUSE: models[HOUSE]},
                                                                      choice["config"])["signals"][HOUSE]["p"]
                                if HOUSE in models else None)):
                conn.execute("INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET "
                             "value=excluded.value", (key, json.dumps(value)))

            # Judged by a model that has not seen the hours it judges: trained
            # on them, a 3am visit is already part of "what Sundays are like"
            # and nothing is ever unexpected.
            end_h = int(now // 3600)
            start_h = end_h - ALERT_LOOKBACK_H
            before = [d for d in days if d < frame.at(start_h)[0]]
            alerts = find_alerts(frame, fit(frame, before, choice["config"]), start_h, end_h) if before else []
            fine = known_normal(conn, tz)
            for alert in alerts:
                suppressed = int((alert.entity_id, datetime.fromtimestamp(alert.hour_ts, tz).hour) in fine)
                conn.execute(
                    "INSERT OR IGNORE INTO shadow_alerts (hour_ts, entity_id, kind, score, detail, event_id, "
                    "suppressed, run_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (alert.hour_ts, alert.entity_id, alert.kind, alert.score, alert.detail, alert.event_id,
                     suppressed, run_id))

        if models_dir is not None:
            models_dir.mkdir(parents=True, exist_ok=True)
            payload = json.dumps({"through": days[-1].isoformat(), "tz": tz_name, "metrics": metrics,
                                  **_model_json(frame, models, choice["config"])})
            (models_dir / f"routine-{days[-1].isoformat()}.json").write_text(payload, encoding="utf-8")
            (models_dir / "routine.json").write_text(payload, encoding="utf-8")
        return {"status": status, "days": len(days), "run_id": run_id, "config": choice["config"],
                "promoted": choice["promoted"], "metrics": metrics, "alerts": len(alerts)}
    finally:
        conn.close()


# ── what the Status view shows ────────────────────────────────────────────────

def learning_summary(conn: sqlite3.Connection, now: float | None = None) -> dict[str, Any]:
    now = time.time() if now is None else now
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    if "model_runs" not in tables:
        return {"runs": 0}
    runs = conn.execute(
        "SELECT ts, through, days, config, metrics, promoted FROM model_runs ORDER BY id DESC LIMIT 30").fetchall()
    if not runs:
        return {"runs": 0}
    last = runs[0]
    metrics = json.loads(last[4])
    routine = conn.execute("SELECT value FROM meta WHERE key = 'learning_house_routine'").fetchone()
    alerts = conn.execute(
        """SELECT a.id, a.hour_ts, a.entity_id, a.kind, a.detail, a.event_id, n.name, f.label
           FROM shadow_alerts a
           LEFT JOIN entities n ON n.entity_id = a.entity_id
           LEFT JOIN feedback f ON f.event_id = a.event_id
           WHERE a.hour_ts > ? AND a.suppressed = 0
           ORDER BY a.hour_ts DESC LIMIT 8""", (now - ALERT_LOOKBACK_H * 3600,)).fetchall()
    labelled = conn.execute(
        """SELECT f.label, COUNT(*) FROM shadow_alerts a JOIN feedback f ON f.event_id = a.event_id
           GROUP BY f.label""").fetchall()
    return {
        "runs": conn.execute("SELECT COUNT(*) FROM model_runs").fetchone()[0],
        "last_run": last[0],
        "through": last[1],
        "days": last[2],
        "config": json.loads(last[3]),
        "promoted": bool(last[5]),
        "status": metrics.get("status"),
        "metrics": metrics,
        "history": [{"ts": r[0], "skill": json.loads(r[4]).get("skill"),
                     "house_accuracy": json.loads(r[4]).get("house_accuracy")} for r in reversed(runs)],
        "routine": json.loads(routine[0]) if routine else None,
        "alerts": [{"id": r[0], "ts": r[1], "entity_id": r[2], "kind": r[3], "detail": r[4],
                    "event_id": r[5], "name": r[6] or r[2], "label": r[7]} for r in alerts],
        "alert_labels": dict(labelled),
        "ready_days": READY_DAYS,
    }


def digest_note(db_path: Path) -> str | None:
    """One line for the digest: what the last run learned."""
    if not db_path.exists():
        return None
    # The digest must survive anything here: a busy or damaged store costs
    # this one line, never the digest.
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=10)
        try:
            summary = learning_summary(conn)
        finally:
            conn.close()
    except (sqlite3.Error, ValueError):
        return None
    if not summary.get("runs"):
        return None
    m = summary["metrics"]
    accuracy = m.get("house_accuracy")
    if accuracy is None:
        return None
    stage = "still warming up" if summary.get("status") != "learning" else "learning"
    alerts = len([a for a in summary["alerts"] if not a["label"]])
    line = (f"house learning, {summary['days']} days in ({stage}): predicts whether the house is active "
            f"{accuracy:.0%} of hours, against {m.get('house_baseline_accuracy', 0):.0%} for a guess")
    if alerts:
        line += f"; {alerts} unusual moment{'s' if alerts != 1 else ''} noted silently"
    return line


def house_time_zone(base_url: str, token: str | None) -> str | None:
    if not token:
        return None
    from src.python.automation_author import ha_get
    try:
        return str(ha_get(base_url, token, "/api/config").get("time_zone") or "") or None
    except (OSError, ValueError):
        return None


def main() -> int:
    from src.python.automation_author import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", type=Path, default=hm.DEFAULT_DB_PATH)
    parser.add_argument("--models", type=Path, default=hm.DEFAULT_DB_PATH.parent / "models")
    parser.add_argument("--tz", default=os.getenv("HOUSE_TZ"))
    parser.add_argument("--base-url", default=os.getenv("HOME_ASSISTANT_BASE_URL", "http://127.0.0.1:8123"))
    parser.add_argument("--print", dest="show", action="store_true")
    args = parser.parse_args()

    tz_name = args.tz or house_time_zone(args.base_url, os.getenv("HOME_ASSISTANT_TOKEN"))
    if not tz_name:
        conn = sqlite3.connect(args.db)
        try:
            row = conn.execute("SELECT value FROM meta WHERE key = 'learning_tz'").fetchone()
        except sqlite3.Error:
            row = None
        conn.close()
        tz_name = json.loads(row[0]) if row else None
    if not tz_name:
        # A routine learned in the wrong zone is shifted by hours - "busy at
        # 3am, quiet at 10" - and looks plausible. Better no run than that.
        print("could not determine the house's time zone: set HOUSE_TZ or make Home Assistant "
              "reachable", file=sys.stderr, flush=True)
        return 1
    started = time.time()
    result = run(args.db, tz_name, models_dir=args.models)
    result["seconds"] = round(time.time() - started, 1)
    print(json.dumps(result, indent=2 if args.show else None, default=str), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
