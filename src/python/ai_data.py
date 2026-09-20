"""What the house's models learn from: bills, meter readings, exports, runtime.

The dashboard's **AI -> AI data** page writes here. Everything lands in one
small SQLite database on the board with the original files beside it, and
nothing ever leaves the house.

Four kinds of thing go in:

  * **meter readings** - a number off the gas meter and the moment it was read.
    Two consecutive readings measure exactly what was burned between them, which
    is the only ground truth this house has for gas, so they are what the model
    is fitted against.
  * **bills** - a FortisBC statement (PDF): a billing period, the gigajoules on
    it, and what it cost. Two years of these pin down the summer baseline and
    the winter slope before a single day of furnace runtime is recorded.
  * **usage exports** - a CSV of periods and amounts, if the account offers one.
  * **furnace runtime** - hours the furnace ran on a day, from the Ecobee
    (src/python/ecobee_runtime.py) or, failing that, from the house memory.

A file is never imported on sight. It is parsed, what was found is shown, and
it becomes rows only when the person says so - a bill whose numbers were read
wrongly is worse than a bill that was not read at all.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

# FortisBC bills in gigajoules; the meter counts cubic feet. The factor varies
# a little with the gas itself, and the bills give the real one - so this is a
# starting point, replaced by `derived_gj_per_cubic_foot()` once a bill and the
# readings that cover it are both in.
DEFAULT_GJ_PER_CUBIC_FOOT = 0.001093   # ~1037 Btu/ft3
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_SUFFIXES = {".pdf", ".csv", ".txt"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,              -- bill | usage | readings | unknown
    sha256 TEXT NOT NULL UNIQUE,
    bytes INTEGER NOT NULL,
    stored_path TEXT NOT NULL,
    added_at TEXT NOT NULL,
    status TEXT NOT NULL,            -- parsed | imported | needs_review
    found TEXT NOT NULL              -- JSON: what the parser made of it
);
CREATE TABLE IF NOT EXISTS readings (
    id INTEGER PRIMARY KEY,
    at TEXT NOT NULL,
    cubic_feet REAL,
    gj REAL,
    source TEXT NOT NULL,            -- manual | file
    file_id INTEGER,
    note TEXT,
    UNIQUE (at, source)
);
CREATE TABLE IF NOT EXISTS bills (
    id INTEGER PRIMARY KEY,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    gj REAL NOT NULL,
    cost REAL,
    file_id INTEGER,
    UNIQUE (period_start, period_end)
);
CREATE TABLE IF NOT EXISTS runtime (
    day TEXT PRIMARY KEY,
    furnace_hours REAL NOT NULL,
    outdoor_mean_c REAL,
    source TEXT NOT NULL             -- ecobee | house-memory
);
"""


def connect(path: Path | str) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    return db


# ── parsing ──

@dataclass
class Parsed:
    kind: str
    status: str
    found: dict[str, Any]


DATE_PATTERNS = (
    (re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"), ("y", "m", "d")),
    (re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b"), ("m", "d", "y")),
    (re.compile(r"\b([A-Z][a-z]{2,8})\.?\s+(\d{1,2}),?\s+(\d{4})\b"), ("mon", "d", "y")),
)
MONTHS = {m.lower(): i for i, m in enumerate(
    ("January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"), start=1)}


def _as_date(groups: tuple[str, ...], order: tuple[str, ...]) -> date | None:
    parts = dict(zip(order, groups))
    if "mon" in parts:
        prefix = parts["mon"][:3].lower()
        month = next((i for name, i in MONTHS.items() if name.startswith(prefix)), None)
    else:
        month = parts.get("m")
    try:
        return date(int(parts["y"]), int(month), int(parts["d"]))
    except (KeyError, ValueError, TypeError):
        return None


def find_dates(text: str) -> list[date]:
    found: list[date] = []
    for pattern, order in DATE_PATTERNS:
        for match in pattern.finditer(text):
            when = _as_date(match.groups(), order)
            if when and date(2000, 1, 1) <= when <= date(2100, 1, 1):
                found.append(when)
    return found


GJ_PATTERN = re.compile(r"([\d,]+\.?\d*)\s*(?:GJ|gigajoule)", re.I)
COST_PATTERN = re.compile(r"(?:total|amount due|balance)[^\n$]{0,40}\$\s*([\d,]+\.\d{2})", re.I)


def parse_bill_text(text: str) -> Parsed:
    """A FortisBC statement, as text. Anything unsure is left for a person.

    Bills differ by year and by how a PDF renders, so this looks for the few
    things every one of them has rather than pretending to know the layout."""
    gj = [float(g.replace(",", "")) for g in GJ_PATTERN.findall(text)]
    costs = [float(c.replace(",", "")) for c in COST_PATTERN.findall(text)]
    dates = sorted(set(find_dates(text)))
    found: dict[str, Any] = {
        "gj": max(gj) if gj else None,           # the period total is the largest GJ on the page
        "cost": max(costs) if costs else None,
        "period_start": dates[0].isoformat() if len(dates) >= 2 else None,
        "period_end": dates[-1].isoformat() if len(dates) >= 2 else None,
        "excerpt": " ".join(text.split())[:400],
    }
    if found["gj"] and found["period_start"] and found["period_end"]:
        span = (date.fromisoformat(found["period_end"]) - date.fromisoformat(found["period_start"])).days
        found["days"] = span
        status = "parsed" if 20 <= span <= 70 else "needs_review"
    else:
        status = "needs_review"
    return Parsed("bill", status, found)


def pdf_text(data: bytes) -> str:
    """Text out of a PDF, or "" when there is no reader on this machine."""
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""
    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception:  # noqa: BLE001 - a scan, an encrypted file, a truncated upload
        return ""


CSV_DATE_HINTS = ("date", "day", "period", "start", "read", "time", "month")
CSV_VALUE_HINTS = ("gj", "usage", "consumption", "amount", "energy", "volume", "reading", "ft3", "cubic")


def parse_csv_text(text: str) -> Parsed:
    """Any CSV of dates and amounts: the columns are detected, not configured."""
    sample = text[:64_000]
    try:
        dialect = csv.Sniffer().sniff(sample.split("\n")[0] + "\n" + (sample.split("\n")[1] if "\n" in sample else ""))
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(io.StringIO(text), dialect))
    rows = [r for r in rows if any(str(c).strip() for c in r)]
    if len(rows) < 2:
        return Parsed("unknown", "needs_review", {"reason": "no rows"})
    header = [str(c).strip().lower() for c in rows[0]]
    date_col = next((i for i, h in enumerate(header) if any(w in h for w in CSV_DATE_HINTS)), None)
    value_col = next((i for i, h in enumerate(header) if any(w in h for w in CSV_VALUE_HINTS)), None)
    if date_col is None or value_col is None:
        return Parsed("unknown", "needs_review", {"reason": "could not tell which columns hold the date and the amount",
                                                  "header": header})
    unit = "ft3" if any(w in header[value_col] for w in ("ft3", "cubic", "reading")) else "GJ"
    parsed_rows = []
    for row in rows[1:]:
        if max(date_col, value_col) >= len(row):
            continue
        when = find_dates(str(row[date_col]))
        try:
            value = float(str(row[value_col]).replace(",", "").replace("$", "").strip())
        except ValueError:
            continue
        if when:
            parsed_rows.append({"date": when[0].isoformat(), "value": value})
    kind = "readings" if unit == "ft3" else "usage"
    status = "parsed" if len(parsed_rows) >= 2 else "needs_review"
    return Parsed(kind, status, {"unit": unit, "rows": parsed_rows[:2000], "count": len(parsed_rows),
                                 "columns": {"date": header[date_col], "value": header[value_col]}})


def parse_upload(name: str, data: bytes) -> Parsed:
    suffix = Path(name).suffix.lower()
    if suffix == ".pdf":
        text = pdf_text(data)
        if not text.strip():
            return Parsed("bill", "needs_review",
                          {"reason": "no text in this PDF - a scan, or pypdf is not installed on the board"})
        return parse_bill_text(text)
    if suffix in (".csv", ".txt"):
        return parse_csv_text(data.decode("utf-8", "replace"))
    return Parsed("unknown", "needs_review", {"reason": f"{suffix or 'no extension'} is not a kind this reads"})


# ── storing ──

class DuplicateFile(ValueError):
    """The same bytes are already here - re-uploading a bill must not double it."""


def add_file(db: sqlite3.Connection, storage: Path, name: str, data: bytes,
             now: datetime | None = None) -> dict[str, Any]:
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError(f"{name} is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
    suffix = Path(name).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ValueError(f"{suffix or 'that'} is not a kind this page takes (PDF or CSV)")
    digest = hashlib.sha256(data).hexdigest()
    if db.execute("SELECT 1 FROM files WHERE sha256 = ?", (digest,)).fetchone():
        raise DuplicateFile(f"{name} is already here")

    storage.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", Path(name).name)[:80]
    stored = storage / f"{digest[:12]}-{safe}"
    stored.write_bytes(data)

    parsed = parse_upload(name, data)
    added = (now or datetime.now()).isoformat(timespec="seconds")
    cursor = db.execute(
        "INSERT INTO files (name, kind, sha256, bytes, stored_path, added_at, status, found)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (name, parsed.kind, digest, len(data), str(stored), added, parsed.status, json.dumps(parsed.found)))
    db.commit()
    return file_row(db, cursor.lastrowid)


def file_row(db: sqlite3.Connection, file_id: int) -> dict[str, Any]:
    row = db.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
    if row is None:
        raise KeyError(f"no file {file_id}")
    doc = dict(row)
    doc["found"] = json.loads(doc["found"])
    return doc


def files(db: sqlite3.Connection) -> list[dict[str, Any]]:
    out = []
    for row in db.execute("SELECT * FROM files ORDER BY id DESC"):
        doc = dict(row)
        found = json.loads(doc["found"])
        # The rows themselves can be thousands; the page wants the shape, not the data.
        if isinstance(found.get("rows"), list):
            found = {**found, "rows": found["rows"][:5]}
        doc["found"] = found
        out.append(doc)
    return out


def import_file(db: sqlite3.Connection, file_id: int,
                gj_per_cubic_foot: float = DEFAULT_GJ_PER_CUBIC_FOOT) -> dict[str, Any]:
    """Turn a parsed file into rows. Idempotent: importing twice adds nothing."""
    doc = file_row(db, file_id)
    found, kind = doc["found"], doc["kind"]
    added = 0
    if kind == "bill":
        if not (found.get("gj") and found.get("period_start") and found.get("period_end")):
            raise ValueError("this bill needs its period and gigajoules confirmed first")
        added = db.execute(
            "INSERT OR IGNORE INTO bills (period_start, period_end, gj, cost, file_id) VALUES (?, ?, ?, ?, ?)",
            (found["period_start"], found["period_end"], found["gj"], found.get("cost"), file_id)).rowcount
    elif kind in ("usage", "readings"):
        rows = found.get("rows") or []
        if not rows:
            raise ValueError("nothing in this file to import")
        for row in rows:
            if kind == "readings":
                cubic = float(row["value"])
                added += db.execute(
                    "INSERT OR IGNORE INTO readings (at, cubic_feet, gj, source, file_id) VALUES (?, ?, ?, 'file', ?)",
                    (f"{row['date']}T00:00:00", cubic, cubic * gj_per_cubic_foot, file_id)).rowcount
            else:
                when = date.fromisoformat(row["date"])
                end = date(when.year + (when.month == 12), (when.month % 12) + 1, 1)
                added += db.execute(
                    "INSERT OR IGNORE INTO bills (period_start, period_end, gj, cost, file_id) VALUES (?, ?, ?, NULL, ?)",
                    (when.isoformat(), end.isoformat(), float(row["value"]), file_id)).rowcount
    else:
        raise ValueError("this file was not understood, so there is nothing to import")
    db.execute("UPDATE files SET status = 'imported' WHERE id = ?", (file_id,))
    db.commit()
    return {"file": file_row(db, file_id), "added": added}


def add_reading(db: sqlite3.Connection, at: datetime, cubic_feet: float | None = None,
                gj: float | None = None, note: str | None = None,
                gj_per_cubic_foot: float = DEFAULT_GJ_PER_CUBIC_FOOT) -> dict[str, Any]:
    """One reading off the meter. Cubic feet is what the dial says; GJ is derived."""
    if cubic_feet is None and gj is None:
        raise ValueError("a reading needs a number")
    if cubic_feet is not None and cubic_feet < 0:
        raise ValueError("a meter reading cannot be negative")
    if gj is None and cubic_feet is not None:
        gj = cubic_feet * gj_per_cubic_foot
    db.execute("INSERT OR REPLACE INTO readings (at, cubic_feet, gj, source, note) VALUES (?, ?, ?, 'manual', ?)",
               (at.isoformat(timespec="seconds"), cubic_feet, gj, note))
    db.commit()
    return {"at": at.isoformat(timespec="seconds"), "cubic_feet": cubic_feet, "gj": gj}


def readings(db: sqlite3.Connection, limit: int = 500) -> list[dict[str, Any]]:
    return [dict(r) for r in db.execute("SELECT * FROM readings ORDER BY at DESC LIMIT ?", (limit,))]


def intervals(db: sqlite3.Connection) -> list[dict[str, Any]]:
    """What each pair of consecutive readings measured: the house's ground truth.

    A meter that goes backwards means it was replaced or misread, so that pair
    is dropped rather than counted as negative gas."""
    rows = [dict(r) for r in db.execute(
        "SELECT at, cubic_feet, gj FROM readings WHERE cubic_feet IS NOT NULL ORDER BY at")]
    out = []
    for before, after in zip(rows, rows[1:]):
        used = (after["cubic_feet"] or 0) - (before["cubic_feet"] or 0)
        hours = (datetime.fromisoformat(after["at"]) - datetime.fromisoformat(before["at"])).total_seconds() / 3600
        if used < 0 or hours <= 0:
            continue
        out.append({"start": before["at"], "end": after["at"], "hours": round(hours, 2),
                    "cubic_feet": round(used, 2),
                    "gj": round((after["gj"] or 0) - (before["gj"] or 0), 5)})
    return out


def record_runtime(db: sqlite3.Connection, days: Iterable[dict[str, Any]], source: str) -> int:
    """Furnace hours per day, from the Ecobee or the house memory."""
    count = 0
    for day in days:
        db.execute("INSERT OR REPLACE INTO runtime (day, furnace_hours, outdoor_mean_c, source)"
                   " VALUES (?, ?, ?, ?)",
                   (str(day["day"]), float(day["furnace_hours"]), day.get("outdoor_mean_c"), source))
        count += 1
    db.commit()
    return count


def derived_gj_per_cubic_foot(db: sqlite3.Connection) -> float | None:
    """The real conversion for this meter, when a bill and the readings that
    cover it are both in. Bills are the authority on it."""
    total_gj = total_cubic = 0.0
    for bill in db.execute("SELECT period_start, period_end, gj FROM bills"):
        start, end = f"{bill['period_start']}T00:00:00", f"{bill['period_end']}T23:59:59"
        covering = [i for i in intervals(db) if i["start"] >= start and i["end"] <= end]
        if not covering:
            continue
        cubic = sum(i["cubic_feet"] for i in covering)
        hours = sum(i["hours"] for i in covering)
        period_hours = (date.fromisoformat(bill["period_end"]) - date.fromisoformat(bill["period_start"])).days * 24
        if cubic <= 0 or period_hours <= 0 or hours < 0.8 * period_hours:
            continue                      # the readings must cover most of the bill to say anything
        total_gj += bill["gj"]
        total_cubic += cubic
    return round(total_gj / total_cubic, 7) if total_cubic > 0 else None


def inventory(db: sqlite3.Connection) -> dict[str, Any]:
    """What the house has to learn from, for the AI data page."""
    def one(query: str) -> sqlite3.Row:
        return db.execute(query).fetchone()

    bills = one("SELECT COUNT(*) n, MIN(period_start) first, MAX(period_end) last, SUM(gj) gj FROM bills")
    reads = one("SELECT COUNT(*) n, MIN(at) first, MAX(at) last FROM readings")
    runs = one("SELECT COUNT(*) n, MIN(day) first, MAX(day) last, SUM(furnace_hours) hours FROM runtime")
    return {
        "bills": {"count": bills["n"], "first": bills["first"], "last": bills["last"],
                  "gj": round(bills["gj"], 2) if bills["gj"] else 0.0},
        "readings": {"count": reads["n"], "first": reads["first"], "last": reads["last"],
                     "intervals": len(intervals(db))},
        "runtime": {"days": runs["n"], "first": runs["first"], "last": runs["last"],
                    "hours": round(runs["hours"], 1) if runs["hours"] else 0.0},
        "gj_per_cubic_foot": derived_gj_per_cubic_foot(db) or DEFAULT_GJ_PER_CUBIC_FOOT,
        "gj_per_cubic_foot_measured": derived_gj_per_cubic_foot(db) is not None,
    }


def runtime_from_house_memory(events_db: Path | str, since: date | None = None) -> list[dict[str, Any]]:
    """Furnace hours a day from the house memory's record of the thermostat.

    The fallback when the Ecobee's own history is not available. Home Assistant
    reports `hvac_action` when it changes, so a day's heating is the time
    between a "heating" and the next state - which is only as good as the
    recording: a gap in the house memory looks like a furnace that stayed on.
    Days whose last known state is still "heating" at midnight are closed there
    rather than run on into the next day.
    """
    import sqlite3 as _sqlite3

    db = _sqlite3.connect(f"file:{events_db}?mode=ro", uri=True)
    db.row_factory = _sqlite3.Row
    try:
        rows = list(db.execute(
            "SELECT ts, attrs FROM events WHERE entity_id = 'climate.my_ecobee' ORDER BY ts"))
    except _sqlite3.Error:
        return []
    finally:
        db.close()

    points: list[tuple[datetime, bool]] = []
    for row in rows:
        try:
            attrs = json.loads(row["attrs"] or "{}")
        except ValueError:
            continue
        action = attrs.get("hvac_action")
        if action is None:
            continue
        points.append((datetime.fromtimestamp(float(row["ts"])), action == "heating"))

    hours: dict[date, float] = {}
    for (when, heating), (next_when, _) in zip(points, points[1:]):
        if not heating:
            continue
        cursor = when
        while cursor < next_when:
            midnight = datetime.combine(cursor.date(), datetime.min.time()) + __import__("datetime").timedelta(days=1)
            stop = min(next_when, midnight)
            hours[cursor.date()] = hours.get(cursor.date(), 0.0) + (stop - cursor).total_seconds() / 3600
            cursor = stop
    days = [{"day": day.isoformat(), "furnace_hours": round(value, 3), "outdoor_mean_c": None}
            for day, value in sorted(hours.items()) if since is None or day >= since]
    # Days that were watched but never called for heat are real zeros, and the
    # model needs them: they are what measures the base load.
    watched = {when.date() for when, _ in points}
    known = {d["day"] for d in days}
    for day in sorted(watched):
        if day.isoformat() not in known and (since is None or day >= since):
            days.append({"day": day.isoformat(), "furnace_hours": 0.0, "outdoor_mean_c": None})
    return sorted(days, key=lambda d: d["day"])
