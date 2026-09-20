"""Estimating gas from furnace runtime, corrected by what the meter actually said.

The FortisBC meter cannot be read from the house (docs/energy-monitoring.md), so
gas is *inferred*: the Ecobee knows to the second when the furnace burned, and a
furnace burns at a fixed rate, so

    gas over a period  =  base x days  +  rate x furnace hours

where **base** is everything that is not the furnace - water heater, cooking,
the dryer - and **rate** is what the furnace burns in an hour. Neither is
assumed: both are fitted from things that were really measured.

Two ways to know how hard the furnace worked, and the fit uses whichever the
house can actually supply:

  * **furnace hours**, from the Ecobee. Exact, and only available for periods
    the thermostat's history covers.
  * **heating degree days**, from the average outdoor temperature a bill
    carries: how far below a balance temperature the weather sat, times the
    days. Coarser, but it reaches back as far as the bills do - two years, in
    this house, before the Ecobee has been asked anything.

        gas over a period  =  base x days  +  slope x degree days

    The balance temperature - the outdoor temperature at which this house stops
    needing heat - is not assumed either; it is fitted by trying a range and
    keeping whichever explains the bills best.

Three kinds of observation, and they are all the same shape - an amount of gas
over a stretch of time:

  * **meter readings**, a pair at a time. Exact, short, and the most useful.
  * **bills**, a month at a time. Less sharp, but there are two years of them,
    and summer bills measure the base load almost on their own.
  * nothing else. A model fitted on its own output would be an opinion.

Fitted by least squares with both terms held at or above zero: a negative base
load or a furnace that produces gas are arithmetic, not physics.

What it cannot do: a modulating furnace (one that burns at varying rates) breaks
the fixed-rate assumption, and this house's single-stage furnace is why the
assumption holds. `fit()` reports its error against the readings, so if that
assumption is wrong the numbers say so rather than the model claiming to be
right.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

MIN_OBSERVATIONS = 4
MIN_HEATING_HOURS = 5.0   # below this, "rate" would be fitted on noise
GJ_PER_HOUR_SANITY = (0.02, 0.35)   # a house furnace: roughly 20,000 to 350,000 BTU/h
MIN_TEMPERATURE_OBSERVATIONS = 6
BALANCE_TEMPERATURES = [10 + 0.5 * i for i in range(21)]   # 10 to 20 degC, the range a house sits in


@dataclass
class Observation:
    start: datetime
    end: datetime
    gj: float
    source: str           # reading | bill
    days: float = 0.0
    furnace_hours: float = 0.0
    covered: bool = True  # is there runtime data for the whole stretch?
    avg_temp_c: float | None = None

    def __post_init__(self) -> None:
        self.days = (self.end - self.start).total_seconds() / 86400

    def degree_days(self, balance_c: float) -> float | None:
        """How far below the balance temperature the weather sat, times the days.

        A period averaging 19 degC needs no heat at all, and gives zero - which
        is what makes a summer bill measure the base load on its own."""
        if self.avg_temp_c is None:
            return None
        return max(0.0, balance_c - self.avg_temp_c) * self.days


@dataclass
class Fit:
    status: str                       # fitted | waiting_for_heating | not_enough_data
    kind: str = "none"                # runtime | degree_day | base_only
    base_gj_per_day: float | None = None
    gj_per_furnace_hour: float | None = None
    gj_per_degree_day: float | None = None
    balance_temp_c: float | None = None
    alternatives: list[dict[str, Any]] = field(default_factory=list)
    observations: int = 0
    mean_abs_error_gj: float | None = None
    error_percent: float | None = None
    heating_hours: float = 0.0
    fitted_at: str = ""
    note: str = ""
    sources: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in self.__dict__.items()}

    def estimate(self, furnace_hours: float = 0.0, days: float = 1.0,
                 avg_temp_c: float | None = None) -> float | None:
        """Gas over a stretch: from furnace hours, or from the weather, or just
        the base load - whichever this fit was built on and the caller can say."""
        if self.base_gj_per_day is None:
            return None
        total = self.base_gj_per_day * days
        if self.kind == "runtime":
            total += (self.gj_per_furnace_hour or 0.0) * furnace_hours
        elif self.kind == "degree_day":
            if avg_temp_c is None:
                return None
            degree_days = max(0.0, (self.balance_temp_c or 0.0) - avg_temp_c) * days
            total += (self.gj_per_degree_day or 0.0) * degree_days
        return round(total, 3)


def runtime_by_day(db: sqlite3.Connection) -> dict[date, float]:
    return {date.fromisoformat(row["day"]): float(row["furnace_hours"])
            for row in db.execute("SELECT day, furnace_hours FROM runtime")}


def _hours_between(runtime: dict[date, float], start: datetime, end: datetime) -> tuple[float, bool]:
    """Furnace hours in a window, and whether every day of it is accounted for.

    Part days count their share: a reading taken at 8pm splits that day."""
    total = 0.0
    covered = True
    day = start.date()
    while day <= end.date():
        midnight = datetime.combine(day, datetime.min.time())
        day_start = max(start, midnight)
        day_end = min(end, midnight + timedelta(days=1))
        share = max(0.0, (day_end - day_start).total_seconds() / 86400)
        hours = runtime.get(day)
        if hours is None:
            # A reading taken at midnight touches the next day for zero seconds;
            # having no runtime for that day is not a hole in this observation.
            covered = covered and share == 0
        else:
            total += hours * share
        day += timedelta(days=1)
    return total, covered


def runtime_trusted_from(db: sqlite3.Connection) -> date | None:
    """The first day the thermostat ever recorded the furnace running.

    Ecobee's report gives zeros for days before the thermostat was driving the
    furnace, and a zero is indistinguishable from an idle day - except that
    the house was billed 14.9 GJ that January. So runtime is believed only from
    the first hour it ever saw; before that it is *unknown*, not zero, and the
    bills from then are left to the degree-day model.
    """
    row = db.execute("SELECT MIN(day) AS day FROM runtime WHERE furnace_hours > 0").fetchone()
    return date.fromisoformat(row["day"]) if row and row["day"] else None


def observations(db: sqlite3.Connection) -> list[Observation]:
    """Everything measured, as gas over a stretch of time."""
    from src.python import ai_data

    runtime = runtime_by_day(db)
    trusted_from = runtime_trusted_from(db)

    def believable(start: datetime, end: datetime, covered: bool) -> bool:
        return covered and trusted_from is not None and start.date() >= trusted_from

    out: list[Observation] = []
    for interval in ai_data.intervals(db):
        start, end = datetime.fromisoformat(interval["start"]), datetime.fromisoformat(interval["end"])
        hours, covered = _hours_between(runtime, start, end)
        covered = believable(start, end, covered)
        out.append(Observation(start, end, float(interval["gj"]), "reading", furnace_hours=hours, covered=covered))
    from src.python import ai_data as _ai_data

    dropped = {clash["other"]["id"] for clash in _ai_data.overlapping_bills(db)}
    for bill in db.execute("SELECT id, period_start, period_end, gj, avg_temp_c FROM bills"):
        if bill["id"] in dropped:
            continue    # the same gas as another bill; counting it twice would skew the fit
        start = datetime.fromisoformat(f"{bill['period_start']}T00:00:00")
        end = datetime.fromisoformat(f"{bill['period_end']}T00:00:00")
        if end <= start:
            continue
        hours, covered = _hours_between(runtime, start, end)
        out.append(Observation(start, end, float(bill["gj"]), "bill", furnace_hours=hours,
                               covered=believable(start, end, covered), avg_temp_c=bill["avg_temp_c"]))
    return sorted(out, key=lambda o: o.start)


def _least_squares(design, target):
    """Fit, hold both terms at or above zero, and score. numpy only."""
    import numpy as np

    coefficients, *_ = np.linalg.lstsq(design, target, rcond=None)
    base, slope = (max(0.0, float(c)) for c in coefficients)
    predicted = design[:, 0] * base + design[:, 1] * slope
    return base, slope, predicted


def _fit_runtime(usable: list[Observation]) -> Fit | None:
    """base x days + rate x furnace hours, on the stretches the thermostat covers."""
    import numpy as np

    rows = [o for o in usable if o.covered]
    heating = sum(o.furnace_hours for o in rows)
    if len(rows) < MIN_OBSERVATIONS or heating < MIN_HEATING_HOURS:
        return None
    design = np.array([[o.days, o.furnace_hours] for o in rows], dtype=float)
    target = np.array([o.gj for o in rows], dtype=float)
    base, rate, predicted = _least_squares(design, target)
    note = ""
    if not GJ_PER_HOUR_SANITY[0] <= rate <= GJ_PER_HOUR_SANITY[1]:
        rate = min(max(rate, GJ_PER_HOUR_SANITY[0]), GJ_PER_HOUR_SANITY[1])
        remainder = target - design[:, 1] * rate
        base = max(0.0, float((remainder / design[:, 0]).mean()))
        predicted = design[:, 0] * base + design[:, 1] * rate
        note = "the fitted furnace rate was outside what a house furnace can burn, so it was capped"
    return Fit("fitted", kind="runtime", base_gj_per_day=base, gj_per_furnace_hour=rate,
               observations=len(rows), heating_hours=round(heating, 2),
               mean_abs_error_gj=float(np.abs(predicted - target).mean()),
               error_percent=_percent(predicted, target), note=note, sources=_sources(rows))


def _fit_degree_day(usable: list[Observation]) -> Fit | None:
    """base x days + slope x degree days, with the balance temperature fitted too.

    This is what the two years of bills support: each carries the period's
    average outdoor temperature, and the summer ones - where the furnace never
    ran - pin the base load on their own."""
    import numpy as np

    rows = [o for o in usable if o.avg_temp_c is not None]
    if len(rows) < MIN_TEMPERATURE_OBSERVATIONS:
        return None
    target = np.array([o.gj for o in rows], dtype=float)
    best: tuple[float, float, float, Any, float] | None = None
    for balance in BALANCE_TEMPERATURES:
        design = np.array([[o.days, o.degree_days(balance) or 0.0] for o in rows], dtype=float)
        if design[:, 1].max() <= 0:
            continue                      # every period above the balance point: nothing to fit
        base, slope, predicted = _least_squares(design, target)
        error = float(np.abs(predicted - target).mean())
        if best is None or error < best[0]:
            best = (error, base, slope, predicted, balance)
    if best is None:
        return None
    error, base, slope, predicted, balance = best
    heating = sum(o.furnace_hours for o in rows)
    return Fit("fitted", kind="degree_day", base_gj_per_day=base, gj_per_degree_day=slope,
               balance_temp_c=balance, observations=len(rows), heating_hours=round(heating, 2),
               mean_abs_error_gj=error, error_percent=_percent(predicted, target),
               sources=_sources(rows))


def _sources(rows: list[Observation]) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        out[row.source] = out.get(row.source, 0) + 1
    return out


def fit(db: sqlite3.Connection, now: datetime | None = None) -> Fit:
    """The best account of this house's gas that its own records support.

    Both models are fitted where the data allows, and the one that explains the
    measurements better wins; the other is kept beside it, so the page can show
    that the choice was made on evidence rather than by preference."""
    import numpy as np

    now = now or datetime.now()
    at = now.isoformat(timespec="seconds")
    usable = [o for o in observations(db) if o.days > 0 and o.gj >= 0]
    covered = [o for o in usable if o.covered]

    if len(usable) < MIN_OBSERVATIONS:
        return Fit("not_enough_data", observations=len(usable), fitted_at=at, sources=_sources(usable),
                   note=f"{len(usable)} measured stretches; {MIN_OBSERVATIONS} is the least this will fit on")

    candidates = [f for f in (_fit_runtime(usable), _fit_degree_day(usable)) if f]
    if candidates:
        best = min(candidates, key=lambda f: f.error_percent if f.error_percent is not None else 1e9)
        best.fitted_at = at
        best.alternatives = [{"kind": f.kind, "error_percent": f.error_percent,
                              "base_gj_per_day": round(f.base_gj_per_day, 4) if f.base_gj_per_day else None,
                              "observations": f.observations}
                             for f in candidates if f is not best]
        return best

    # Nothing to separate the furnace from the rest: learn the base load, which
    # is what a summer bill measures, and say what is missing.
    rows = covered or usable
    days = np.array([o.days for o in rows], dtype=float)
    target = np.array([o.gj for o in rows], dtype=float)
    base = float(target.sum() / days.sum())
    predicted = days * base
    heating = sum(o.furnace_hours for o in rows)
    return Fit("waiting_for_heating", kind="base_only", base_gj_per_day=base,
               observations=len(rows), heating_hours=round(heating, 2),
               mean_abs_error_gj=float(np.abs(predicted - target).mean()),
               error_percent=_percent(predicted, target), fitted_at=at, sources=_sources(rows),
               note="no furnace runtime and no temperatures yet; base load only")


def _percent(predicted: Any, target: Any) -> float | None:
    total = float(sum(target))
    if total <= 0:
        return None
    return round(100 * float(abs(predicted - target).sum()) / total, 2)


def daily_outdoor(db: sqlite3.Connection) -> dict[date, float]:
    """Each day's mean outdoor temperature, as the Ecobee reported it."""
    return {date.fromisoformat(row["day"]): float(row["outdoor_mean_c"])
            for row in db.execute("SELECT day, outdoor_mean_c FROM runtime WHERE outdoor_mean_c IS NOT NULL")}


def daily_estimates(db: sqlite3.Connection, model: Fit, days: int = 30,
                    today: date | None = None) -> list[dict[str, Any]]:
    """What each of the last days probably used, for the dashboard's gas column.

    A day is only estimated when the model's own input is known for it: furnace
    hours for the runtime model, an outdoor temperature for the degree-day one.
    A day with neither gets no number rather than a base load pretending to be
    a whole day."""
    if model.base_gj_per_day is None:
        return []
    runtime = runtime_by_day(db)
    outdoor = daily_outdoor(db)
    today = today or date.today()
    out = []
    for step in range(days, 0, -1):
        day = today - timedelta(days=step)
        hours = runtime.get(day)
        temperature = outdoor.get(day)
        known = hours is not None if model.kind == "runtime" else temperature is not None
        out.append({"date": day.isoformat(),
                    "gj": model.estimate(hours or 0.0, 1.0, temperature) if known else None,
                    "furnace_hours": hours,
                    "outdoor_mean_c": temperature,
                    "estimated": True,
                    "runtime_known": known})
    return out


def report(db: sqlite3.Connection, now: datetime | None = None) -> dict[str, Any]:
    """The gas model as the AI data page shows it."""
    from src.python import ai_data

    model = fit(db, now)
    today = (now or datetime.now()).date()
    return {
        "model": model.as_dict(),
        "inventory": ai_data.inventory(db),
        "days": daily_estimates(db, model, 30, today),
        "yesterday_gj": next((d["gj"] for d in reversed(daily_estimates(db, model, 2, today))
                              if d["runtime_known"]), None),
        "monthly_estimate_gj": model.estimate(days=30, avg_temp_c=_recent_temperature(db, today),
                                              furnace_hours=_recent_hours(db, today)),
    }


def _recent_temperature(db: sqlite3.Connection, today: date, days: int = 30) -> float | None:
    temps = [t for day, t in daily_outdoor(db).items() if today - timedelta(days=days) <= day <= today]
    return round(sum(temps) / len(temps), 2) if temps else None


def _recent_hours(db: sqlite3.Connection, today: date, days: int = 30) -> float:
    return sum(h for day, h in runtime_by_day(db).items() if today - timedelta(days=days) <= day <= today)
