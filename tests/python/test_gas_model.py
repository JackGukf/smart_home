"""Gas from furnace runtime, corrected by the meter.

The FortisBC meter cannot be read from the house, so gas is inferred from how
long the furnace burned. These tests build houses whose real base load and
furnace rate are known, and check the fit recovers them - and that it refuses
to answer when it has not been shown enough.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from src.python import ai_data, gas_model

BASE = 0.11      # GJ a day that is not the furnace
RATE = 0.098     # GJ per hour of furnace


@pytest.fixture()
def db(tmp_path):
    return ai_data.connect(tmp_path / "gas.db")


def a_winter(db, days: int = 30, start: date = date(2026, 1, 1), hours=lambda d: 3.0 + (d % 5) * 0.5):
    """Runtime, and meter readings that agree with BASE and RATE exactly."""
    cubic = 4000.0
    per_cubic = ai_data.DEFAULT_GJ_PER_CUBIC_FOOT
    ai_data.record_runtime(db, [{"day": (start + timedelta(days=d)).isoformat(),
                                 "furnace_hours": hours(d), "outdoor_mean_c": 2.0} for d in range(days)], "ecobee")
    ai_data.add_reading(db, datetime.combine(start, datetime.min.time()), cubic_feet=cubic)
    for d in range(days):
        cubic += (BASE + RATE * hours(d)) / per_cubic
        ai_data.add_reading(db, datetime.combine(start + timedelta(days=d + 1), datetime.min.time()),
                            cubic_feet=round(cubic, 1))
    return start


def test_it_recovers_the_base_load_and_the_furnace_rate(db):
    a_winter(db)
    model = gas_model.fit(db, now=datetime(2026, 2, 1))

    assert model.status == "fitted"
    assert model.base_gj_per_day == pytest.approx(BASE, abs=0.01)
    assert model.gj_per_furnace_hour == pytest.approx(RATE, abs=0.01)
    assert model.error_percent < 2
    assert model.sources["reading"] == 30


def test_an_estimate_is_base_plus_the_furnace(db):
    a_winter(db)
    model = gas_model.fit(db, now=datetime(2026, 2, 1))
    assert model.estimate(furnace_hours=3.0) == pytest.approx(BASE + 3 * RATE, abs=0.02)
    assert model.estimate(furnace_hours=0.0) == pytest.approx(BASE, abs=0.02)
    assert model.estimate(furnace_hours=10.0, days=2) == pytest.approx(2 * BASE + 10 * RATE, abs=0.04)


def test_bills_alone_fit_it_too(db):
    """Two years of bills and Ecobee's runtime history: no meter readings at all,
    which is the state the house is actually in."""
    day = date(2025, 1, 1)
    while day < date(2026, 1, 1):
        hours = 5.0 if day.month in (11, 12, 1, 2, 3) else 0.2
        ai_data.record_runtime(db, [{"day": day.isoformat(), "furnace_hours": hours, "outdoor_mean_c": 5.0}], "ecobee")
        day += timedelta(days=1)
    start = date(2025, 1, 1)
    while start < date(2025, 12, 1):
        end = date(start.year, start.month + 1, 1)
        hours = sum(gas_model.runtime_by_day(db).get(start + timedelta(days=d), 0)
                    for d in range((end - start).days))
        db.execute("INSERT INTO bills (period_start, period_end, gj) VALUES (?, ?, ?)",
                   (start.isoformat(), end.isoformat(), BASE * (end - start).days + RATE * hours))
        start = end
    db.commit()

    model = gas_model.fit(db, now=datetime(2026, 1, 1))
    assert model.status == "fitted" and model.sources == {"bill": 11}
    assert model.base_gj_per_day == pytest.approx(BASE, abs=0.02)
    assert model.gj_per_furnace_hour == pytest.approx(RATE, abs=0.02)


def test_before_the_furnace_runs_it_says_so_and_still_learns_the_base(db):
    """September in Vancouver: the thermostat has never called for heat. The
    base load is learnable; the furnace rate is not, and is not guessed."""
    a_winter(db, days=20, start=date(2026, 8, 1), hours=lambda d: 0.0)
    model = gas_model.fit(db, now=datetime(2026, 9, 1))

    assert model.status == "waiting_for_heating"
    assert model.base_gj_per_day == pytest.approx(BASE, abs=0.01)
    assert model.gj_per_furnace_hour is None
    assert "barely run" in model.note
    assert model.estimate(furnace_hours=0.0) == pytest.approx(BASE, abs=0.01)


def test_with_almost_nothing_it_refuses_rather_than_guesses(db):
    ai_data.add_reading(db, datetime(2026, 1, 1), cubic_feet=4000)
    ai_data.add_reading(db, datetime(2026, 1, 2), cubic_feet=4100)
    model = gas_model.fit(db, now=datetime(2026, 1, 3))
    assert model.status == "not_enough_data" and model.base_gj_per_day is None
    assert model.estimate(furnace_hours=3) is None


def test_a_stretch_with_no_runtime_data_is_not_used(db):
    a_winter(db, days=10)
    db.execute("DELETE FROM runtime WHERE day >= '2026-01-05'")   # the Ecobee was offline
    db.commit()
    model = gas_model.fit(db, now=datetime(2026, 2, 1))
    assert model.observations == 4, "only the stretches the thermostat can account for"


def test_an_impossible_furnace_rate_is_capped_and_said(db):
    """A fit can produce a furnace that burns ten times what any house furnace
    can. That is arithmetic winning over physics, and it gets capped."""
    for day in range(8):
        ai_data.record_runtime(db, [{"day": f"2026-01-0{day + 1}", "furnace_hours": 2.0}], "ecobee")
    cubic = 1000.0
    ai_data.add_reading(db, datetime(2026, 1, 1), cubic_feet=cubic)
    for day in range(2, 8):
        cubic += 3.0 / ai_data.DEFAULT_GJ_PER_CUBIC_FOOT          # 3 GJ a day on 2 h of furnace
        ai_data.add_reading(db, datetime(2026, 1, day), cubic_feet=cubic)
    model = gas_model.fit(db, now=datetime(2026, 2, 1))
    assert model.gj_per_furnace_hour <= gas_model.GJ_PER_HOUR_SANITY[1]
    assert "capped" in model.note


def test_the_report_the_page_shows(db):
    a_winter(db, days=30, start=date(2026, 1, 1))
    doc = gas_model.report(db, now=datetime(2026, 1, 31, 9))
    assert doc["model"]["status"] == "fitted"
    assert len(doc["days"]) == 30 and doc["days"][-1]["estimated"] is True
    assert doc["yesterday_gj"] == pytest.approx(BASE + RATE * 3.5, abs=0.4)
    assert doc["inventory"]["runtime"]["days"] == 30
