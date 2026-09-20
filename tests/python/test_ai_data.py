"""AI data: what the models learn from - bills, meter readings, exports.

Nothing is imported on sight: a file is parsed, what was found is shown, and it
becomes rows only when asked. These tests hold that line, and the arithmetic
that turns two meter readings into a measured amount of gas.
"""
from __future__ import annotations

import json
from datetime import date, datetime

import pytest

from src.python import ai_data


@pytest.fixture()
def db(tmp_path):
    return ai_data.connect(tmp_path / "gas.db")


BILL_TEXT = """
FortisBC Energy Inc.
Billing period  2026-01-05  to  2026-02-04
Natural gas used            8.42 GJ
Delivery charge             $31.10
Total amount due            $102.77
"""


def test_a_bill_is_read_for_the_few_things_every_bill_has():
    parsed = ai_data.parse_bill_text(BILL_TEXT)
    assert parsed.kind == "bill" and parsed.status == "parsed"
    assert parsed.found["gj"] == 8.42 and parsed.found["cost"] == 102.77
    assert parsed.found["period_start"] == "2026-01-05" and parsed.found["period_end"] == "2026-02-04"
    assert parsed.found["days"] == 30


def test_a_bill_that_does_not_read_cleanly_waits_for_a_person():
    assert ai_data.parse_bill_text("a page with no numbers on it").status == "needs_review"
    # A period nobody bills over is a misread, not a two-year bill.
    wrong = ai_data.parse_bill_text("2024-01-01 to 2026-02-04 total 9.1 GJ")
    assert wrong.status == "needs_review"


def test_dates_are_read_in_the_three_shapes_bills_use():
    assert date(2026, 2, 4) in ai_data.find_dates("Feb 4, 2026")
    assert date(2026, 2, 4) in ai_data.find_dates("2/4/2026")
    assert date(2026, 2, 4) in ai_data.find_dates("2026-02-04")


def test_a_csv_has_its_columns_detected_not_configured():
    parsed = ai_data.parse_csv_text("Date,Usage (GJ),Cost\n2026-01-31,8.42,102.77\n2026-02-28,7.10,91.02\n")
    assert parsed.kind == "usage" and parsed.status == "parsed"
    assert parsed.found["count"] == 2 and parsed.found["rows"][0] == {"date": "2026-01-31", "value": 8.42}

    readings = ai_data.parse_csv_text("day,meter reading ft3\n2026-09-01,4100\n2026-09-02,4118\n")
    assert readings.kind == "readings" and readings.found["unit"] == "ft3"

    assert ai_data.parse_csv_text("a,b\n1,2\n").status == "needs_review"


def test_a_file_is_stored_parsed_and_not_imported(db, tmp_path):
    doc = ai_data.add_file(db, tmp_path / "files", "fortisbc-2026-02.csv",
                           b"Date,Usage (GJ)\n2026-01-31,8.42\n2026-02-28,7.10\n")
    assert doc["status"] == "parsed" and doc["kind"] == "usage"
    assert not db.execute("SELECT * FROM bills").fetchall()      # parsed, not imported

    result = ai_data.import_file(db, doc["id"])
    assert result["added"] == 2 and result["file"]["status"] == "imported"
    assert len(db.execute("SELECT * FROM bills").fetchall()) == 2
    # Importing again adds nothing: a bill must not double because someone clicked twice.
    assert ai_data.import_file(db, doc["id"])["added"] == 0


def test_the_same_file_twice_is_refused(db, tmp_path):
    ai_data.add_file(db, tmp_path / "files", "bill.csv", b"Date,GJ\n2026-01-31,8.42\n2026-02-28,7.1\n")
    with pytest.raises(ai_data.DuplicateFile):
        ai_data.add_file(db, tmp_path / "files", "bill-copy.csv", b"Date,GJ\n2026-01-31,8.42\n2026-02-28,7.1\n")


def test_uploads_are_bounded_and_of_known_kinds(db, tmp_path):
    with pytest.raises(ValueError, match="not a kind"):
        ai_data.add_file(db, tmp_path / "files", "photo.jpg", b"\xff\xd8\xff")
    with pytest.raises(ValueError, match="larger than"):
        ai_data.add_file(db, tmp_path / "files", "huge.csv", b"x" * (ai_data.MAX_UPLOAD_BYTES + 1))


def test_two_readings_measure_exactly_what_was_burned(db):
    ai_data.add_reading(db, datetime(2026, 9, 18, 20, 0), cubic_feet=4100)
    ai_data.add_reading(db, datetime(2026, 9, 19, 20, 0), cubic_feet=4118)
    [interval] = ai_data.intervals(db)
    assert interval["cubic_feet"] == 18 and interval["hours"] == 24
    assert interval["gj"] == pytest.approx(18 * ai_data.DEFAULT_GJ_PER_CUBIC_FOOT, abs=1e-5)


def test_a_meter_that_goes_backwards_is_dropped_not_counted(db):
    ai_data.add_reading(db, datetime(2026, 9, 18, 20, 0), cubic_feet=4100)
    ai_data.add_reading(db, datetime(2026, 9, 19, 20, 0), cubic_feet=40)     # misread, or a new meter
    ai_data.add_reading(db, datetime(2026, 9, 20, 20, 0), cubic_feet=58)
    assert [i["cubic_feet"] for i in ai_data.intervals(db)] == [18]


def test_the_conversion_comes_from_a_bill_once_the_readings_cover_one(db):
    assert ai_data.derived_gj_per_cubic_foot(db) is None          # nothing to say yet
    db.execute("INSERT INTO bills (period_start, period_end, gj) VALUES ('2026-09-01','2026-09-11',11.0)")
    for day in range(1, 12):
        ai_data.add_reading(db, datetime(2026, 9, day, 0, 0), cubic_feet=1000 * day)
    db.commit()
    # 10,000 cubic feet over the period billed at 11 GJ.
    assert ai_data.derived_gj_per_cubic_foot(db) == pytest.approx(0.0011, abs=1e-5)


def test_inventory_says_what_the_house_has(db, tmp_path):
    ai_data.add_reading(db, datetime(2026, 9, 18, 20, 0), cubic_feet=4100)
    ai_data.add_reading(db, datetime(2026, 9, 19, 20, 0), cubic_feet=4118)
    ai_data.record_runtime(db, [{"day": "2026-09-19", "furnace_hours": 2.5, "outdoor_mean_c": 6.0}], "ecobee")
    doc = ai_data.inventory(db)
    assert doc["readings"]["count"] == 2 and doc["readings"]["intervals"] == 1
    assert doc["runtime"]["days"] == 1 and doc["runtime"]["hours"] == 2.5
    assert doc["bills"]["count"] == 0
    assert doc["gj_per_cubic_foot_measured"] is False


def test_runtime_can_be_recovered_from_the_house_memory(tmp_path, db):
    """The fallback when Ecobee's own history is not available: Home Assistant
    reports hvac_action when it changes, so heating is the time until the next
    state, and a day nobody called for heat is a real zero."""
    import sqlite3
    from datetime import timedelta

    events = tmp_path / "events.db"
    memory = sqlite3.connect(events)
    memory.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, ts REAL, entity_id TEXT, attrs TEXT)")
    start = datetime(2026, 11, 2, 6, 0)
    rows = [(start, "heating"), (start + timedelta(hours=2), "idle"),
            (start + timedelta(hours=8), "heating"), (start + timedelta(hours=9, minutes=30), "idle"),
            (start + timedelta(days=1), "idle")]
    for when, action in rows:
        memory.execute("INSERT INTO events (ts, entity_id, attrs) VALUES (?, 'climate.my_ecobee', ?)",
                       (when.timestamp(), json.dumps({"hvac_action": action})))
    memory.commit()
    memory.close()

    days = ai_data.runtime_from_house_memory(events)
    by_day = {d["day"]: d["furnace_hours"] for d in days}
    assert by_day["2026-11-02"] == pytest.approx(3.5)     # 2 h + 1.5 h
    assert by_day["2026-11-03"] == 0.0                    # watched, never heated
    assert ai_data.record_runtime(db, days, "house-memory") == len(days)


def test_the_owners_export_reads_day_first_and_keeps_both_dates(db, tmp_path):
    """FortisBC's 24-month export: two date columns, day-first dates, and a
    period average temperature. Read month-first, 22/07/2026 is not a date at
    all and the whole file came back empty - which is what happened."""
    csv = ("Bill from date,Bill to date,# of days,Billed GJ,Average temperature\n"
           "22/07/2026,18/08/2026,28,0.9,19\n"
           "19/06/2026,21/07/2026,33,1.3,18\n"
           "21/01/2025,18/02/2025,29,14.9,0\n")
    parsed = ai_data.parse_csv_text(csv)
    assert parsed.kind == "bills" and parsed.status == "parsed"
    assert parsed.found["date_order"] == "day-first" and parsed.found["count"] == 3
    assert parsed.found["rows"][0] == {"start": "2026-07-22", "end": "2026-08-18",
                                       "gj": 0.9, "days": 27, "avg_temp_c": 19.0}
    doc = ai_data.add_file(db, tmp_path / "files", "history.csv", csv.encode())
    assert ai_data.import_file(db, doc["id"])["added"] == 3
    assert db.execute("SELECT avg_temp_c FROM bills ORDER BY period_start").fetchone()["avg_temp_c"] == 0.0


def test_a_row_whose_dates_disagree_with_its_own_day_count_is_held_back(db):
    """The '# of days' column is the check that the dates were read the right
    way round, not just another field to import."""
    parsed = ai_data.parse_csv_text("From,To,# of days,GJ\n01/02/2026,01/03/2026,90,4.0\n"
                                    "01/04/2026,01/05/2026,30,3.0\n")
    assert parsed.found["mismatched_rows"] == 1 and parsed.status == "needs_review"


def test_a_bill_pdf_with_day_first_dates_reads_too():
    parsed = ai_data.parse_bill_text("Billing period 22/07/2026 to 18/08/2026\n"
                                     "Natural gas used 0.9 GJ\nTotal amount due $41.20")
    assert parsed.found["period_start"] == "2026-07-22" and parsed.found["period_end"] == "2026-08-18"
    assert parsed.found["gj"] == 0.9 and parsed.status == "parsed"


def test_equipment_running_is_believed_over_hvac_action():
    """ecobee's `equipment_running` names what was switched on, so the fan
    running by itself - which burns no gas - is not counted as heat."""
    assert ai_data._is_heating({"equipment_running": "auxHeat1,fan"}) is True
    assert ai_data._is_heating({"equipment_running": "fan"}) is False
    assert ai_data._is_heating({"equipment_running": "compCool1,fan"}) is False
    assert ai_data._is_heating({"equipment_running": ""}) is False
    # The HomeKit entity has no such attribute, so hvac_action stands in.
    assert ai_data._is_heating({"hvac_action": "heating"}) is True
    assert ai_data._is_heating({"hvac_action": "idle"}) is False
    assert ai_data._is_heating({}) is None
    # And a thermostat that reports both is read from the better one.
    assert ai_data._is_heating({"equipment_running": "fan", "hvac_action": "heating"}) is False


def test_bc_hydro_monthly_export_becomes_months(db, tmp_path):
    """BC Hydro's export gives a start date and a figure; the period runs to the
    next row, or a month, whichever is sooner - a missing month must not become
    one ten-month period."""
    csv = ('"Account Holder","Account Number","Interval Start Date/Time","Net Consumption (kWh)","Peak Demand (kW)"\n'
           '"A B","0","2024-09-01","366.00","N/A"\n"A B","0","2024-10-01","425.00","N/A"\n'
           '"A B","0","2025-06-01","411.00","N/A"\n')
    parsed = ai_data.parse_csv_text(csv)
    assert parsed.kind == "power_usage" and parsed.status == "parsed"
    assert parsed.found["rows"][0] == {"start": "2024-09-01", "end": "2024-10-01", "kwh": 366.0, "days": 30}
    assert parsed.found["rows"][1]["end"] == "2024-11-01", "the gap is not swallowed"

    doc = ai_data.add_file(db, tmp_path / "files", "usage.csv", csv.encode())
    assert ai_data.import_file(db, doc["id"])["added"] == 3
    assert ai_data.inventory(db)["electricity"]["count"] == 3
    # Kilowatt hours must not land in the gas table.
    assert ai_data.inventory(db)["bills"]["count"] == 0


def test_a_bc_hydro_bill_pdf_reads_its_period_usage_and_tiers():
    text = ("Your bill for Mar 20, 2026 to May 20, 2026\n"
            "172 kWh used over 12 days\n719 kWh used over 50 days\n"
            "Basic Charge 12 days x $0.2330 /day\nBasic Charge 50 days x $0.2344 /day\n"
            "Tier 1: 172 kWh x $0.1172 /kWh\nTier 1: 719 kWh x $0.1187 /kWh\n"
            "Tier 2: 0 kWh x $0.1408 /kWh\n"
            "You were 485 kWh below your Tier 2 threshold of 1,376 kWh this billing period.\n"
            "TOTAL DUE $127.48")
    parsed = ai_data.parse_power_bill_text(text)
    assert parsed.kind == "power_bills" and parsed.status == "parsed"
    [row] = parsed.found["rows"]
    # A bill spanning a rate change is written in two blocks; both are the bill.
    assert row["kwh"] == 891.0 and row["days"] == 62 and row["blocks"] == 2
    assert row["start"] == "2026-03-20" and row["end"] == "2026-05-20"
    assert row["cost"] == 127.48
    assert row["tier1_price"] == 0.1187, "the newest price on the bill is the one in force"
    assert row["tier2_threshold_kwh"] == 1376.0 and row["basic_per_day"] == 0.2344


def test_the_export_and_the_pdf_of_the_same_period_are_merged(db, tmp_path):
    """The yearly export has what it cost; the bill PDF has the tier prices.
    Keeping only the first would lose one of them."""
    csv = ('"Invoice Number","Type","Amount Due","From Date","To Date","kWh Usage"\n'
           '"1","Amount Due","131.73",,,\n'
           '"1","Detail: Usage",,"2026-05-21","2026-07-20","920.0"\n')
    first = ai_data.add_file(db, tmp_path / "files", "billing.csv", csv.encode())
    ai_data.import_file(db, first["id"])

    text = ("Your bill for May 21, 2026 to Jul 20, 2026\n920 kWh used over 61 days\n"
            "Tier 1: 920 kWh x $0.1187 /kWh\nBasic Charge 61 days x $0.2344 /day\n")
    second = ai_data.add_file(db, tmp_path / "files", "bill.pdf.csv", text.encode())
    db.execute("UPDATE files SET kind='power_bills', found=? WHERE id=?",
               (json.dumps(ai_data.parse_power_bill_text(text).found), second["id"]))
    db.commit()
    ai_data.import_file(db, second["id"])

    [row] = db.execute("SELECT * FROM power_periods").fetchall()
    assert row["cost"] == 131.73 and row["tier1_price"] == 0.1187
