"""Estimating gas from furnace runtime, corrected by what the meter actually said.

The FortisBC meter cannot be read from the house (docs/energy-monitoring.md), so
gas is *inferred*: the Ecobee knows to the second when the furnace burned, and a
furnace burns at a fixed rate, so

    gas over a period  =  base x days  +  rate x furnace hours

where **base** is everything that is not the furnace - water heater, cooking,
the dryer - and **rate** is what the furnace burns in an hour. Neither is
assumed: both are fitted from things that were really measured.

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


@dataclass
class Observation:
    start: datetime
    end: datetime
    gj: float
    source: str           # reading | bill
    days: float = 0.0
    furnace_hours: float = 0.0
    covered: bool = True  # is there runtime data for the whole stretch?

    def __post_init__(self) -> None:
        self.days = (self.end - self.start).total_seconds() / 86400


@dataclass
class Fit:
    status: str                       # fitted | waiting_for_heating | not_enough_data
    base_gj_per_day: float | None = None
    gj_per_furnace_hour: float | None = None
    observations: int = 0
    mean_abs_error_gj: float | None = None
    error_percent: float | None = None
    heating_hours: float = 0.0
    fitted_at: str = ""
    note: str = ""
    sources: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in self.__dict__.items()}

    def estimate(self, furnace_hours: float, days: float = 1.0) -> float | None:
        if self.base_gj_per_day is None:
            return None
        rate = self.gj_per_furnace_hour or 0.0
        return round(self.base_gj_per_day * days + rate * furnace_hours, 3)


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


def observations(db: sqlite3.Connection) -> list[Observation]:
    """Everything measured, as gas over a stretch of time."""
    from src.python import ai_data

    runtime = runtime_by_day(db)
    out: list[Observation] = []
    for interval in ai_data.intervals(db):
        start, end = datetime.fromisoformat(interval["start"]), datetime.fromisoformat(interval["end"])
        hours, covered = _hours_between(runtime, start, end)
        out.append(Observation(start, end, float(interval["gj"]), "reading", furnace_hours=hours, covered=covered))
    for bill in db.execute("SELECT period_start, period_end, gj FROM bills"):
        start = datetime.fromisoformat(f"{bill['period_start']}T00:00:00")
        end = datetime.fromisoformat(f"{bill['period_end']}T00:00:00")
        if end <= start:
            continue
        hours, covered = _hours_between(runtime, start, end)
        out.append(Observation(start, end, float(bill["gj"]), "bill", furnace_hours=hours, covered=covered))
    return sorted(out, key=lambda o: o.start)


def fit(db: sqlite3.Connection, now: datetime | None = None) -> Fit:
    """Fit base load and furnace rate on everything that was really measured."""
    import numpy as np

    now = now or datetime.now()
    usable = [o for o in observations(db) if o.covered and o.days > 0 and o.gj >= 0]
    sources: dict[str, int] = {}
    for observation in usable:
        sources[observation.source] = sources.get(observation.source, 0) + 1
    heating = sum(o.furnace_hours for o in usable)

    if len(usable) < MIN_OBSERVATIONS:
        return Fit("not_enough_data", observations=len(usable), heating_hours=round(heating, 2),
                   fitted_at=now.isoformat(timespec="seconds"), sources=sources,
                   note=f"{len(usable)} measured stretches; {MIN_OBSERVATIONS} is the least this will fit on")

    design = np.array([[o.days, o.furnace_hours] for o in usable], dtype=float)
    target = np.array([o.gj for o in usable], dtype=float)

    if heating < MIN_HEATING_HOURS:
        # No furnace worth speaking of: the base load is all there is to learn,
        # and it is learnable - that is what a summer bill measures.
        base = float(target.sum() / design[:, 0].sum())
        predicted = design[:, 0] * base
        return Fit("waiting_for_heating", base_gj_per_day=base, gj_per_furnace_hour=None,
                   observations=len(usable), heating_hours=round(heating, 2),
                   mean_abs_error_gj=float(np.abs(predicted - target).mean()),
                   error_percent=_percent(predicted, target),
                   fitted_at=now.isoformat(timespec="seconds"), sources=sources,
                   note="the furnace has barely run; base load only until it does")

    coefficients, *_ = np.linalg.lstsq(design, target, rcond=None)
    base, rate = (max(0.0, float(c)) for c in coefficients)
    if not GJ_PER_HOUR_SANITY[0] <= rate <= GJ_PER_HOUR_SANITY[1]:
        # Refit with the furnace pinned to a plausible rate rather than shipping
        # a number that no domestic furnace could produce.
        rate = min(max(rate, GJ_PER_HOUR_SANITY[0]), GJ_PER_HOUR_SANITY[1])
        remainder = target - design[:, 1] * rate
        base = max(0.0, float((remainder / design[:, 0]).mean()))
        note = "the fitted furnace rate was outside what a house furnace can burn, so it was capped"
    else:
        note = ""
    predicted = design[:, 0] * base + design[:, 1] * rate
    return Fit("fitted", base_gj_per_day=base, gj_per_furnace_hour=rate, observations=len(usable),
               mean_abs_error_gj=float(np.abs(predicted - target).mean()),
               error_percent=_percent(predicted, target), heating_hours=round(heating, 2),
               fitted_at=now.isoformat(timespec="seconds"), sources=sources, note=note)


def _percent(predicted: Any, target: Any) -> float | None:
    total = float(sum(target))
    if total <= 0:
        return None
    return round(100 * float(abs(predicted - target).sum()) / total, 2)


def daily_estimates(db: sqlite3.Connection, model: Fit, days: int = 30,
                    today: date | None = None) -> list[dict[str, Any]]:
    """What each of the last days probably used, for the dashboard's gas column."""
    if model.base_gj_per_day is None:
        return []
    runtime = runtime_by_day(db)
    today = today or date.today()
    out = []
    for step in range(days, 0, -1):
        day = today - timedelta(days=step)
        hours = runtime.get(day)
        out.append({"date": day.isoformat(),
                    "gj": model.estimate(hours or 0.0),
                    "furnace_hours": hours,
                    "estimated": True,
                    "runtime_known": hours is not None})
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
    }
