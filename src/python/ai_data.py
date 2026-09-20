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
    avg_temp_c REAL,                 -- some exports carry it; the degree-day model uses it
    file_id INTEGER,
    UNIQUE (period_start, period_end)
);
-- Electricity, from BC Hydro's own exports and bills. Only dates, amounts and
-- money are kept: the files carry the account holder, the account number and
-- the service address, and none of that is any use to a model.
CREATE TABLE IF NOT EXISTS power_periods (
    id INTEGER PRIMARY KEY,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    kwh REAL NOT NULL,
    cost REAL,
    tier1_price REAL,
    tier2_price REAL,
    tier2_threshold_kwh REAL,
    basic_per_day REAL,
    source TEXT NOT NULL,            -- bill | usage
    file_id INTEGER,
    UNIQUE (period_start, period_end, source)
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
    # Databases made before 2026-09-19 have no avg_temp_c; adding it is the
    # whole migration, and SQLite has no "ADD COLUMN IF NOT EXISTS".
    if "avg_temp_c" not in {row["name"] for row in db.execute("PRAGMA table_info(bills)")}:
        db.execute("ALTER TABLE bills ADD COLUMN avg_temp_c REAL")
        db.commit()
    return db


# ── parsing ──

@dataclass
class Parsed:
    kind: str
    status: str
    found: dict[str, Any]


SLASH_DATE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
DATE_PATTERNS = (
    (re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"), ("y", "m", "d")),
    (SLASH_DATE, ("m", "d", "y")),
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


def parse_date_column(values: list[str]) -> tuple[list[date | None], str]:
    """A whole column of dates at once, so 22/07/2026 is not thrown away.

    `01/02/2026` is the second of January in one country and the first of
    February in another, and no single value can say which. A column usually
    can: if any day-part is above 12 the order is settled. When even the column
    is ambiguous, day-first is assumed - which is what FortisBC's export uses -
    and the caller checks the result against the "# of days" column."""
    slashed = [SLASH_DATE.search(str(v) or "") for v in values]
    firsts = [int(m.group(1)) for m in slashed if m]
    seconds = [int(m.group(2)) for m in slashed if m]
    order = "day-first"
    if firsts and max(firsts) > 12:
        order = "day-first"
    elif seconds and max(seconds) > 12:
        order = "month-first"
    out: list[date | None] = []
    for value, match in zip(values, slashed):
        if match:
            first, second, year = (int(g) for g in match.groups())
            day, month = (first, second) if order == "day-first" else (second, first)
            try:
                out.append(date(year, month, day))
                continue
            except ValueError:
                out.append(None)
                continue
        found = find_dates(str(value))
        out.append(found[0] if found else None)
    return out, order


def find_dates(text: str) -> list[date]:
    """Dates loose in text - a PDF bill, a cell. A slashed date with a first
    part above 12 can only be day-first (22/07/2026); otherwise month-first is
    assumed, which is what a North American statement prints. A column of them
    is better decided all at once: see `parse_date_column`."""
    found: list[date] = []
    for pattern, order in DATE_PATTERNS:
        for match in pattern.finditer(text):
            groups = match.groups()
            if pattern is SLASH_DATE and int(groups[0]) > 12:
                order = ("d", "m", "y")
            when = _as_date(groups, order)
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
        # A gas bill covers a month. A wider span means the page's earliest and
        # latest dates were picked up - a previous-reading date, a due date -
        # rather than the billing period, so a person should look.
        status = "parsed" if 20 <= span <= 45 else "needs_review"
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


def _column(header: list[str], *words: str) -> int | None:
    return next((i for i, h in enumerate(header) if any(w in h for w in words)), None)


def _numbers(rows: list[list[str]], index: int | None) -> list[float | None]:
    if index is None:
        return [None] * len(rows)
    out: list[float | None] = []
    for row in rows:
        try:
            out.append(float(str(row[index]).replace(",", "").replace("$", "").strip()))
        except (ValueError, IndexError):
            out.append(None)
    return out


def parse_bill_history(header: list[str], rows: list[list[str]]) -> Parsed | None:
    """FortisBC's 24-month export: from, to, days, GJ, average temperature.

    Two date columns is what marks it out. The "# of days" column is not just
    imported - it is the check that the dates were read the right way round."""
    date_columns = [i for i, h in enumerate(header)
                    if any(w in h for w in ("date", "from", "to", "period", "start", "end"))]
    if len(date_columns) < 2:
        return None
    starts, order = parse_date_column([row[date_columns[0]] if date_columns[0] < len(row) else "" for row in rows])
    ends, _ = parse_date_column([row[date_columns[1]] if date_columns[1] < len(row) else "" for row in rows])
    gj_column = _column(header, "gj", "usage", "consumption", "energy")
    if gj_column is None:
        return None
    amounts = _numbers(rows, gj_column)
    days_column = _column(header, "days")
    stated_days = _numbers(rows, days_column)
    temps = _numbers(rows, _column(header, "temp"))

    parsed, mismatched = [], 0
    for start, end, gj, days, temp in zip(starts, ends, amounts, stated_days, temps):
        if not (start and end and gj is not None) or end <= start:
            continue
        span = (end - start).days
        if days is not None and abs(span - days) > 1:
            mismatched += 1        # the dates do not match the row's own day count
            continue
        parsed.append({"start": start.isoformat(), "end": end.isoformat(), "gj": gj,
                       "days": span, "avg_temp_c": temp})
    if not parsed:
        return None
    found = {"rows": parsed[:400], "count": len(parsed), "unit": "GJ", "date_order": order,
             "columns": {"start": header[date_columns[0]], "end": header[date_columns[1]],
                         "gj": header[gj_column]},
             "with_temperature": sum(1 for row in parsed if row["avg_temp_c"] is not None),
             "mismatched_rows": mismatched}
    return Parsed("bills", "parsed" if mismatched == 0 else "needs_review", found)


# BC Hydro's monthly export: one row a month, "Interval Start Date/Time" and
# "Net Consumption (kWh)". The rest of the columns are the account's identity.
def parse_power_usage_csv(header: list[str], rows: list[list[str]]) -> Parsed | None:
    date_col = _column(header, "interval start")
    kwh_col = _column(header, "consumption (kwh)", "net consumption")
    if date_col is None or kwh_col is None:
        return None
    starts, order = parse_date_column([r[date_col] if date_col < len(r) else "" for r in rows])
    amounts = _numbers(rows, kwh_col)
    points = sorted(((s, k) for s, k in zip(starts, amounts) if s and k is not None),
                    key=lambda p: p[0])
    if len(points) < 2:
        return None
    parsed = []
    for (start, kwh), (next_start, _) in zip(points, points[1:] + [(None, None)]):
        # A month, or less if the next row comes sooner. Never more: a missing
        # month would otherwise become one period ten months long.
        end = min(next_start, _month_after(start)) if next_start else _month_after(start)
        parsed.append({"start": start.isoformat(), "end": end.isoformat(), "kwh": kwh,
                       "days": (end - start).days})
    return Parsed("power_usage", "parsed", {"rows": parsed, "count": len(parsed), "unit": "kWh",
                                            "date_order": order,
                                            "columns": {"date": header[date_col], "kwh": header[kwh_col]}})


def _month_after(day: date) -> date:
    return date(day.year + (day.month == 12), (day.month % 12) + 1, day.day if day.day <= 28 else 28)


# BC Hydro's billing export: several rows an invoice, and the one that matters
# is "Detail: Usage" - it carries the billing period, the kWh and the charges.
def parse_power_billing_csv(header: list[str], rows: list[list[str]]) -> Parsed | None:
    from_col, to_col = _column(header, "from date"), _column(header, "to date")
    kwh_col = _column(header, "kwh usage")
    if from_col is None or to_col is None or kwh_col is None:
        return None
    invoice_col = _column(header, "invoice number")
    due_col = _column(header, "amount due")
    type_col = _column(header, "type")

    # What each invoice was actually asked for, from its "Amount Due" row.
    due_by_invoice: dict[str, float] = {}
    if invoice_col is not None and due_col is not None:
        for row in rows:
            if max(invoice_col, due_col) >= len(row):
                continue
            try:
                due = float(str(row[due_col]).replace(",", "").replace("$", "").strip())
            except ValueError:
                continue
            kind = str(row[type_col]).strip().lower() if type_col is not None and type_col < len(row) else ""
            if kind.startswith("amount due"):
                due_by_invoice[str(row[invoice_col]).strip()] = due

    starts, order = parse_date_column([r[from_col] if from_col < len(r) else "" for r in rows])
    ends, _ = parse_date_column([r[to_col] if to_col < len(r) else "" for r in rows])
    kwh = _numbers(rows, kwh_col)
    basic = _numbers(rows, _column(header, "basic charge"))
    usage = _numbers(rows, _column(header, "usage charge"))

    parsed = []
    for row, start, end, amount, basic_charge, usage_charge in zip(rows, starts, ends, kwh, basic, usage):
        if not (start and end and amount is not None) or end <= start:
            continue
        invoice = str(row[invoice_col]).strip() if invoice_col is not None and invoice_col < len(row) else ""
        cost = due_by_invoice.get(invoice)
        if cost is None and (basic_charge is not None or usage_charge is not None):
            cost = round((basic_charge or 0) + (usage_charge or 0), 2)
        parsed.append({"start": start.isoformat(), "end": end.isoformat(), "kwh": amount,
                       "days": (end - start).days, "cost": cost})
    if not parsed:
        return None
    return Parsed("power_bills", "parsed", {"rows": parsed, "count": len(parsed), "unit": "kWh",
                                            "date_order": order,
                                            "with_cost": sum(1 for r in parsed if r["cost"] is not None)})


# "Your bill for Jan 20, 2026 to Mar 19, 2026". Both halves are matched as
# whole dates: a lazy ".{6,20}?" stops at "Mar 19," and loses the year.
_DATE_SHAPE = r"(?:[A-Z][a-z]{2,8}\.?\s+\d{1,2},?\s+\d{4}|\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2})"
POWER_PERIOD = re.compile(rf"your bill for\s+({_DATE_SHAPE})\s+to\s+({_DATE_SHAPE})", re.I)
POWER_USED = re.compile(r"([\d,]+)\s*kWh used over\s*(\d+)\s*days", re.I)
POWER_TIER = re.compile(r"Tier\s*(\d):\s*([\d,]+)\s*kWh\s*x\s*\$([\d.]+)\s*/kWh", re.I)
POWER_BASIC = re.compile(r"Basic Charge\s*(\d+)\s*days\s*x\s*\$([\d.]+)\s*/day", re.I)
POWER_THRESHOLD = re.compile(r"Tier 2\s*threshold of\s*([\d,]+)\s*kWh", re.I)
POWER_TOTAL = re.compile(r"total due[^$]{0,40}\$\s?([\d,]+\.\d{2})", re.I)


def parse_power_bill_text(text: str) -> Parsed | None:
    """A BC Hydro bill: the period, the kilowatt hours, and the tier prices.

    The figures are written plainly on the page ("631 kWh used over 59 days"),
    which is a happier parse than the gas bill's - no guessing which two of the
    page's dates are the billing period."""
    flat = " ".join(text.split())
    used = POWER_USED.search(flat)
    period = POWER_PERIOD.search(flat)
    if not used or not period:
        return None
    starts = find_dates(period.group(1))
    ends = find_dates(period.group(2))
    if not starts or not ends:
        return None
    tiers: dict[int, tuple[float, float]] = {}
    for tier, amount, price in POWER_TIER.findall(flat):
        tiers[int(tier)] = (float(amount.replace(",", "")), float(price))   # last wins: the newest price
    basic_charges = POWER_BASIC.findall(flat)    # last wins, as with the tiers
    threshold = POWER_THRESHOLD.search(flat)
    # A bill that spans a rate change is written as two blocks - "172 kWh used
    # over 12 days" at the old price and "719 kWh over 50 days" at the new one.
    # The period is the whole bill; the usage is all of it.
    blocks = [(float(k.replace(",", "")), int(d)) for k, d in POWER_USED.findall(flat)]
    kwh = sum(k for k, _ in blocks)
    days = sum(d for _, d in blocks)
    total = POWER_TOTAL.search(flat)
    found: dict[str, Any] = {
        "rows": [{"start": starts[0].isoformat(), "end": ends[0].isoformat(), "kwh": kwh,
                  "days": days,
                  "cost": float(total.group(1).replace(",", "")) if total else None,
                  "blocks": len(blocks),
                  # The newest price on the bill is the one in force now.
                  "tier1_price": tiers.get(1, (None, None))[1],
                  "tier2_price": tiers.get(2, (None, None))[1],
                  "tier2_threshold_kwh": float(threshold.group(1).replace(",", "")) if threshold else None,
                  "basic_per_day": float(basic_charges[-1][1]) if basic_charges else None}],
        "count": 1, "unit": "kWh",
    }
    stated = (ends[0] - starts[0]).days
    status = "parsed" if abs(stated - days) <= 1 and 20 <= days <= 75 else "needs_review"
    return Parsed("power_bills", status, found)


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
    for reader in (parse_power_usage_csv, parse_power_billing_csv, parse_bill_history):
        found = reader(header, rows[1:])
        if found:
            return found
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
        return parse_power_bill_text(text) or parse_bill_text(text)
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
    elif kind == "bills":
        for row in found.get("rows") or []:
            added += db.execute(
                "INSERT OR IGNORE INTO bills (period_start, period_end, gj, cost, avg_temp_c, file_id)"
                " VALUES (?, ?, ?, NULL, ?, ?)",
                (row["start"], row["end"], float(row["gj"]), row.get("avg_temp_c"), file_id)).rowcount
    elif kind in ("power_usage", "power_bills"):
        source = "bill" if kind == "power_bills" else "usage"
        for row in found.get("rows") or []:
            # A period can arrive twice: the yearly export has what it cost, the
            # bill PDF has the tier prices. Merge rather than keep the first.
            added += db.execute(
                "INSERT INTO power_periods (period_start, period_end, kwh, cost, tier1_price,"
                " tier2_price, tier2_threshold_kwh, basic_per_day, source, file_id)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT (period_start, period_end, source) DO UPDATE SET"
                "   cost = COALESCE(excluded.cost, cost),"
                "   tier1_price = COALESCE(excluded.tier1_price, tier1_price),"
                "   tier2_price = COALESCE(excluded.tier2_price, tier2_price),"
                "   tier2_threshold_kwh = COALESCE(excluded.tier2_threshold_kwh, tier2_threshold_kwh),"
                "   basic_per_day = COALESCE(excluded.basic_per_day, basic_per_day)",
                (row["start"], row["end"], float(row["kwh"]), row.get("cost"), row.get("tier1_price"),
                 row.get("tier2_price"), row.get("tier2_threshold_kwh"), row.get("basic_per_day"),
                 source, file_id)).rowcount
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
    power = one("SELECT COUNT(*) n, MIN(period_start) first, MAX(period_end) last, SUM(kwh) kwh,"
                " SUM(CASE WHEN cost IS NOT NULL THEN 1 ELSE 0 END) costed FROM power_periods")
    return {
        "electricity": {"count": power["n"], "first": power["first"], "last": power["last"],
                        "kwh": round(power["kwh"], 1) if power["kwh"] else 0.0,
                        "with_cost": power["costed"] or 0},
        "bills": {"count": bills["n"], "first": bills["first"], "last": bills["last"],
                  "gj": round(bills["gj"], 2) if bills["gj"] else 0.0},
        "readings": {"count": reads["n"], "first": reads["first"], "last": reads["last"],
                     "intervals": len(intervals(db))},
        "runtime": {"days": runs["n"], "first": runs["first"], "last": runs["last"],
                    "hours": round(runs["hours"], 1) if runs["hours"] else 0.0},
        "gj_per_cubic_foot": derived_gj_per_cubic_foot(db) or DEFAULT_GJ_PER_CUBIC_FOOT,
        "gj_per_cubic_foot_measured": derived_gj_per_cubic_foot(db) is not None,
    }


HEATING_EQUIPMENT = ("auxheat", "heatpump", "compheat")   # what ecobee calls the heat stages


def _is_heating(attrs: dict[str, Any]) -> bool | None:
    """Was the furnace burning, as far as this record can say?

    `equipment_running` is the better witness where it exists: it names what the
    thermostat switched on, so the fan running on its own - which burns no gas -
    is not mistaken for heat. `hvac_action` is the fallback, and says "heating"
    for the same thing."""
    equipment = attrs.get("equipment_running")
    if equipment is not None:
        names = str(equipment).lower()
        return any(word in names for word in HEATING_EQUIPMENT)
    action = attrs.get("hvac_action")
    return None if action is None else action == "heating"


def runtime_from_house_memory(events_db: Path | str, since: date | None = None,
                              entity_ids: tuple[str, ...] = ("climate.my_ecobee_2", "climate.my_ecobee")
                              ) -> list[dict[str, Any]]:
    """Furnace hours a day from the house memory's record of the thermostat.

    What there is until ecobee's own history is fetched. Home Assistant reports
    a change when it happens, so a day's heating is the time between the furnace
    coming on and the next record - only as good as the recording: a gap in the
    house memory looks like a furnace that stayed on. Days whose last known
    state is still heating at midnight are closed there rather than run into the
    next day.

    The entities are tried in order and the first with any records wins: the
    cloud integration's entity (`equipment_running`) before the HomeKit one
    (`hvac_action`), because it can tell a running fan from burning gas.
    """
    import sqlite3 as _sqlite3

    db = _sqlite3.connect(f"file:{events_db}?mode=ro", uri=True)
    db.row_factory = _sqlite3.Row
    rows: list[Any] = []
    try:
        for entity_id in entity_ids:
            rows = list(db.execute("SELECT ts, attrs FROM events WHERE entity_id = ? ORDER BY ts",
                                   (entity_id,)))
            if len(rows) > 1:
                break
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
        heating = _is_heating(attrs)
        if heating is None:
            continue
        points.append((datetime.fromtimestamp(float(row["ts"])), heating))

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


def reparse_file(db: sqlite3.Connection, file_id: int) -> dict[str, Any]:
    """Read a stored file again with today's parser.

    Files uploaded before a parser learned something - day-first dates, a new
    export shape - are still on disk; this gives them a second chance without
    asking the owner to find the original again."""
    doc = file_row(db, file_id)
    data = Path(doc["stored_path"]).read_bytes()
    parsed = parse_upload(doc["name"], data)
    status = "imported" if doc["status"] == "imported" else parsed.status
    if parsed.kind != doc["kind"]:
        # It was read as something else before - kilowatt hours as gigajoules,
        # in the case that prompted this. Whatever it put in must come out.
        for table in ("bills", "readings", "power_periods"):
            db.execute(f"DELETE FROM {table} WHERE file_id = ?", (file_id,))
        status = parsed.status
    db.execute("UPDATE files SET kind = ?, status = ?, found = ? WHERE id = ?",
               (parsed.kind, status, json.dumps(parsed.found), file_id))
    db.commit()
    return file_row(db, file_id)


def delete_file(db: sqlite3.Connection, file_id: int) -> dict[str, Any]:
    """Forget a file and everything it put in: the way to undo a bad import."""
    doc = file_row(db, file_id)
    removed = {
        "bills": db.execute("DELETE FROM bills WHERE file_id = ?", (file_id,)).rowcount,
        "readings": db.execute("DELETE FROM readings WHERE file_id = ?", (file_id,)).rowcount,
        "electricity": db.execute("DELETE FROM power_periods WHERE file_id = ?", (file_id,)).rowcount,
    }
    db.execute("DELETE FROM files WHERE id = ?", (file_id,))
    db.commit()
    stored = Path(doc["stored_path"])
    if stored.is_file():
        stored.unlink()
    return {"name": doc["name"], "removed": removed}


def overlapping_bills(db: sqlite3.Connection) -> list[dict[str, Any]]:
    """Billing periods that cover days another bill already covers.

    A PDF of a bill and a line in the yearly export are often the same gas
    twice, and a fit that counts it twice is wrong in a way nothing announces."""
    rows = [dict(r) for r in db.execute(
        "SELECT id, period_start, period_end, gj, avg_temp_c, file_id FROM bills ORDER BY period_start")]
    clashes = []
    for i, first in enumerate(rows):
        for second in rows[i + 1:]:
            if second["period_start"] < first["period_end"] and second["period_end"] > first["period_start"]:
                clashes.append({"kept": _richer(first, second), "other": _poorer(first, second)})
    return clashes


def _quality(bill: dict[str, Any]) -> tuple:
    """Which of two overlapping bills to believe: the one carrying a period
    temperature (it came from the export, with its own day count), then the
    shorter period, which is the less likely to be two dates from one page."""
    span = (date.fromisoformat(bill["period_end"]) - date.fromisoformat(bill["period_start"])).days
    return (bill.get("avg_temp_c") is not None, -span)


def _richer(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    return a if _quality(a) >= _quality(b) else b


def _poorer(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    return b if _quality(a) >= _quality(b) else a
