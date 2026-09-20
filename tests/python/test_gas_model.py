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
    assert model.kind == "base_only" and "base load only" in model.note
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


# ── The owner's real 24 months of FortisBC bills (2024-08 to 2026-08) ──
#
# Day-first dates, a period average temperature, and - the owner's own point -
# July and August with the furnace off, so those bills measure the hot water
# tank on its own. Kept verbatim because it is the house this has to fit.

REAL_BILLS = """Bill from date,Bill to date,# of days,Billed GJ,Average temperature
22/07/2026,18/08/2026,28,0.9,19
19/06/2026,21/07/2026,33,1.3,18
22/05/2026,18/06/2026,28,1.9,16
21/04/2026,21/05/2026,31,3.4,13
21/03/2026,20/04/2026,31,9,8
20/02/2026,20/03/2026,29,9.4,6
21/01/2026,19/02/2026,30,9.3,6
18/12/2025,20/01/2026,34,12.8,5
19/11/2025,17/12/2025,29,9,7
21/10/2025,18/11/2025,29,7.8,9
20/09/2025,20/10/2025,31,4.5,13
21/08/2025,19/09/2025,30,0.9,18
18/07/2025,20/08/2025,34,1.2,18
18/06/2025,17/07/2025,30,1.1,18
17/05/2025,17/06/2025,32,2.7,15
17/04/2025,16/05/2025,30,4.1,12
19/03/2025,16/04/2025,29,6.9,9
19/02/2025,18/03/2025,28,8.8,7
21/01/2025,18/02/2025,29,14.9,0
18/12/2024,20/01/2025,34,13.5,5
21/11/2024,17/12/2024,27,10.2,5
19/10/2024,20/11/2024,33,9.9,9
20/09/2024,18/10/2024,29,4.6,13
21/08/2024,19/09/2024,30,1.3,16
"""


def loaded(db, tmp_path):
    from src.python import ai_data as data
    doc = data.add_file(db, tmp_path / "files", "gas-history.csv", REAL_BILLS.encode())
    data.import_file(db, doc["id"])
    return doc


def test_the_owners_two_years_of_bills_fit_without_any_runtime(db, tmp_path):
    """No Ecobee history at all: the bills' own average temperatures carry it."""
    doc = loaded(db, tmp_path)
    assert doc["kind"] == "bills" and doc["found"]["count"] == 24
    assert doc["found"]["date_order"] == "day-first"     # 22/07/2026 is July, not month 22

    model = gas_model.fit(db, now=datetime(2026, 9, 19))
    assert model.status == "fitted" and model.kind == "degree_day"
    assert model.observations == 24 and model.sources == {"bill": 24}
    assert model.error_percent < 8
    # A Vancouver house stops needing heat somewhere in the teens.
    assert 12 <= model.balance_temp_c <= 20


def test_july_and_august_measure_the_hot_water_tank(db, tmp_path):
    """The owner's point: with the furnace off, a summer bill is the base load.
    0.9-1.3 GJ over 28-34 days is about 0.035 GJ a day, and the fit must land
    there rather than smearing the furnace across the year."""
    loaded(db, tmp_path)
    model = gas_model.fit(db, now=datetime(2026, 9, 19))

    assert model.base_gj_per_day == pytest.approx(0.035, abs=0.008)
    # A summer month, predicted from the weather alone.
    assert model.estimate(days=28, avg_temp_c=19) == pytest.approx(0.9, abs=0.35)
    assert model.estimate(days=30, avg_temp_c=18) == pytest.approx(1.1, abs=0.35)
    # And the coldest month in the two years.
    assert model.estimate(days=29, avg_temp_c=0) == pytest.approx(14.9, abs=1.2)


def test_every_one_of_the_owners_bills_is_explained_within_a_gigajoule_and_a_half(db, tmp_path):
    loaded(db, tmp_path)
    model = gas_model.fit(db, now=datetime(2026, 9, 19))
    for observation in gas_model.observations(db):
        predicted = model.estimate(days=observation.days, avg_temp_c=observation.avg_temp_c)
        assert abs(predicted - observation.gj) < 1.5, f"{observation.start.date()}: {predicted} vs {observation.gj}"


def test_runtime_wins_when_there_is_runtime_to_use(db, tmp_path):
    """Both models are fitted where the data allows; the better one is used and
    the other is kept beside it, so the choice is visible."""
    loaded(db, tmp_path)
    a_winter(db, days=40, start=date(2026, 10, 1))      # readings and Ecobee runtime
    model = gas_model.fit(db, now=datetime(2026, 12, 1))
    assert model.kind == "runtime"
    assert [a["kind"] for a in model.alternatives] == ["degree_day"]
    assert model.gj_per_furnace_hour == pytest.approx(RATE, abs=0.02)


def test_zeros_from_before_the_thermostat_drove_the_furnace_are_not_believed(db, tmp_path):
    """The owner's ecobee reported outdoor temperatures from Sept 2024 but no
    furnace time until 2025-03-08, while January 2025 was billed 14.9 GJ. Those
    zeros are missing data, not idle days, and fitting on them put the base load
    at 0.17 GJ/day - four times what the summer bills measure."""
    loaded(db, tmp_path)
    day = date(2024, 9, 18)
    while day < date(2026, 9, 19):
        heating = day >= date(2025, 3, 8) and day.month in (10, 11, 12, 1, 2, 3, 4)
        ai_data.record_runtime(db, [{"day": day.isoformat(),
                                     "furnace_hours": 4.0 if heating else 0.0,
                                     "outdoor_mean_c": 5.0}], "ecobee")
        day += timedelta(days=1)

    assert gas_model.runtime_trusted_from(db) == date(2025, 3, 8)
    seen = [o for o in gas_model.observations(db) if o.covered]
    assert all(o.start.date() >= date(2025, 3, 8) for o in seen)
    assert any(o.start.date() < date(2025, 3, 8) for o in gas_model.observations(db)), "they are kept, just not trusted"

    model = gas_model.fit(db, now=datetime(2026, 9, 19))
    # Whichever model wins, the base load stays near what July and August say.
    assert model.base_gj_per_day == pytest.approx(0.037, abs=0.02)


def test_with_no_runtime_at_all_nothing_is_trusted(db, tmp_path):
    loaded(db, tmp_path)
    ai_data.record_runtime(db, [{"day": "2026-08-01", "furnace_hours": 0.0, "outdoor_mean_c": 19.0}], "ecobee")
    assert gas_model.runtime_trusted_from(db) is None
    assert not any(o.covered for o in gas_model.observations(db))
    assert gas_model.fit(db, now=datetime(2026, 9, 19)).kind == "degree_day"
