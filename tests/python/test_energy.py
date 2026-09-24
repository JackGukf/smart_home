"""The Energy card and view: sample data until the PowerLync is paired, live
electricity from Home Assistant after, each said so on screen; and the
Discovery apps that replaced three sidebar entries."""
from __future__ import annotations

import importlib.util
import io
import json
import tarfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

import yaml
from fastapi.testclient import TestClient

from src.python import energy, web_app

STATIC = Path(__file__).resolve().parents[2] / "src" / "python" / "web_static"


def test_sample_data_says_it_is_sample_data():
    snap = energy.snapshot(datetime(2026, 9, 18, 23, 48))
    assert snap["sample"] is True and "PowerLync" in snap["source"]


def test_the_figures_are_a_plausible_house_and_add_up():
    snap = energy.snapshot(datetime(2026, 9, 18, 23, 48))
    e, g = snap["electricity"], snap["gas"]

    assert 0.25 <= e["kw_now"] <= 6
    assert len(e["last_hour_kw"]) == 60 and e["last_hour_kw"][-1] == e["kw_now"]
    assert len(e["today_hourly_kwh"]) == 24                     # 23 whole hours and the one under way
    assert abs(sum(e["today_hourly_kwh"]) - e["today_kwh"]) < 0.2
    assert 12 <= e["last_24h_kwh"] <= 40                        # about 21 kWh on a usual day
    # Whole periods, so the view reads the same just after midnight as at dinner:
    # the last 24 whole hours, and 30 whole days ending yesterday.
    assert len(e["last_24h_hourly_kwh"]) == 24 and abs(sum(e["last_24h_hourly_kwh"]) - e["last_24h_kwh"]) < 0.2
    assert e["last_24h_start_hour"] == 23 and len(e["usual_24h_hourly_kwh"]) == 24
    assert len(e["days"]) == 30 and e["days"][-1]["date"] == "2026-09-17"
    # Gas in GJ, as FortisBC bills, daily at best.
    assert len(g["days"]) == 30 and g["days"][-1]["date"] == "2026-09-17"
    assert g["yesterday_gj"] == g["days"][-1]["gj"] and 0.05 < g["yesterday_gj"] < 1.5


def test_the_same_moment_reads_the_same_on_every_screen():
    at = datetime(2026, 9, 18, 20, 5)
    assert energy.snapshot(at) == energy.snapshot(at)


def test_gas_follows_the_season():
    winter = energy.snapshot(datetime(2027, 1, 15, 12))["gas"]["yesterday_gj"]
    summer = energy.snapshot(datetime(2027, 7, 15, 12))["gas"]["yesterday_gj"]
    assert winter > summer * 2


def test_the_dashboard_serves_it(tmp_path):
    cfg = tmp_path / "devices.local.yaml"
    cfg.write_text(yaml.dump({}), encoding="utf-8")
    doc = TestClient(web_app.create_app(config_path=cfg, check_camera_ports=False)).get("/api/energy").json()
    assert doc["sample"] is True and {"electricity", "gas"} <= set(doc)


def test_the_card_and_the_view_show_the_sample_flag():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "app.js").read_text(encoding="utf-8")

    assert 'data-home-card="energy"' in html and 'id="homeEnergySample"' in html
    assert 'data-view-panel="energy"' in html and 'id="energySampleNote"' in html
    # Per section: each of the two says whether it is sample data on its own.
    # The card's pill is for a card that is entirely invented; a half that is
    # made up carries its own "sample" in its subtitle.
    assert "sample.hidden = !(e.sample && g.sample)" in js
    assert "note.hidden = !e.sample && !g.sample" in js
    # Gas: the sample column is labelled, and real bills get their own column.
    assert 'pill: "Sample"' in js and "gasColumnHtml(g)" in js


def test_energy_sits_between_cameras_and_devices_in_the_sidebar():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    views = html[html.index('<div class="sidebar-section">Views</div>'):html.index('<div class="sidebar-section">System</div>')]
    assert views.index('data-view="cameras"') < views.index('data-view="energy"') < views.index('data-view="devices"')


def test_discovery_is_one_entry_with_three_apps_that_come_back_to_it():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    views = html[html.index('<div class="sidebar-section">Views</div>'):html.index('<div class="sidebar-section">System</div>')]

    assert 'data-view="discover"' in views
    assert '<div class="sidebar-section">Discovery</div>' not in html
    launcher = html[html.index('data-view-panel="discover"'):html.index('data-view-panel="cameras"')]
    for page in ("discovery", "zigbee", "bluetooth"):
        assert f'data-view="{page}"' not in views, f"{page} left the sidebar"
        assert f'class="app-tile" data-goto-view="{page}"' in launcher
        panel = html[html.index(f'data-view-panel="{page}"'):]
        panel = panel[:panel.index("</div>")]
        assert 'class="page-back" data-goto-view="discover"' in panel, f"{page} needs a way back"
    assert 'discovery: "discover", zigbee: "discover", bluetooth: "discover"' in js


# ── Live electricity ──

NOW = datetime(2026, 10, 2, 18, 30)
POWER = "sensor.powerlync_energy_monitor_000528_grid_instantaneous_demand"
ENERGY = "sensor.powerlync_energy_monitor_000528_grid_total_energy_consumed"


def _states(extra=()):
    ids = [POWER, ENERGY,
           "sensor.powerlync_energy_monitor_000528_plug_instantaneous_demand",
           "sensor.powerlync_energy_monitor_000528_plug_energy_delivered", *extra]
    return [{"entity_id": i, "state": "1840.0"} for i in ids]


def test_the_house_meter_is_found_and_the_built_in_plug_is_not():
    assert energy.find_powerlync_entities(_states()) == (POWER, ENERGY)
    assert energy.find_powerlync_entities([{"entity_id": "sensor.kitchen_power", "state": "3"}]) is None
    # The README's older naming, without "grid_", still reads as the house.
    old = [{"entity_id": "sensor.powerlync_energy_monitor_1_instantaneous_demand", "state": "859.0"},
           {"entity_id": "sensor.powerlync_energy_monitor_1_total_energy_consumed", "state": "64732.4"},
           {"entity_id": "sensor.powerlync_energy_monitor_1_local_instantaneous_demand", "state": "0.0"}]
    assert energy.find_powerlync_entities(old) == ("sensor.powerlync_energy_monitor_1_instantaneous_demand",
                                                   "sensor.powerlync_energy_monitor_1_total_energy_consumed")


def test_a_powerlync_the_meter_has_never_reported_to_is_not_live_yet():
    # Paired with Home Assistant, not joined to the meter: every sensor exists and reads 0.
    unjoined = [{**s, "state": "0.0"} for s in _states()]
    assert energy.find_powerlync_entities(unjoined) is None
    for register in ("unknown", "unavailable"):
        states = [{**s, "state": register} if s["entity_id"] == ENERGY else s for s in _states()]
        assert energy.find_powerlync_entities(states) is None
    # A house using nothing this minute is still a live meter: only the register decides.
    idle = [{**s, "state": "0.0"} if s["entity_id"] == POWER else s for s in _states()]
    assert energy.find_powerlync_entities(idle) == (POWER, ENERGY)


def test_sample_data_while_the_meter_has_not_reported_then_live_once_it_does():
    ha = FakeHA([{**s, "state": "0.0"} for s in _states()])
    clock = [0.0]
    source = energy.LiveEnergy("http://ha", lambda: "token", ha.get_json, ha.statistics, clock=lambda: clock[0])
    assert source.snapshot(NOW)["electricity"]["sample"] is True
    ha.states = _states()
    clock[0] += energy.DISCOVERY_SECONDS
    assert source.snapshot(NOW)["electricity"]["sample"] is False


def _iso(t: datetime) -> str:
    return t.astimezone().isoformat()


def _hourly(days: int, kwh: float = 0.9):
    start = NOW.replace(minute=0) - timedelta(days=days)
    rows, t = [], start
    while t < NOW.replace(minute=0):
        rows.append({"start": int(t.timestamp() * 1000), "end": int((t + timedelta(hours=1)).timestamp() * 1000),
                     "change": kwh})
        t += timedelta(hours=1)
    return rows


def test_live_electricity_is_built_from_the_recorder():
    history = [{"state": "400", "last_changed": _iso(NOW - timedelta(minutes=90))},
               {"state": "2400", "last_changed": _iso(NOW - timedelta(minutes=10, seconds=30))},
               {"state": "unavailable", "last_changed": _iso(NOW - timedelta(minutes=3, seconds=30))},
               {"state": "1840", "last_changed": _iso(NOW - timedelta(minutes=1, seconds=30))}]
    daily = [{"start": _iso((NOW - timedelta(days=d)).replace(hour=0, minute=0)), "change": 20.0 + d}
             for d in range(5, 0, -1)] + [{"start": _iso(NOW.replace(hour=0, minute=0)), "change": 9.0}]
    e = energy.build_live_electricity(NOW, {"state": "1840.0"}, history, _hourly(5), daily)

    assert e["sample"] is False and e["kw_now"] == 1.84 and e["state"] == "busy"
    assert len(e["last_hour_kw"]) == 60 and e["last_hour_kw"][0] == 0.4
    assert e["last_hour_kw"][-11] == 2.4 and e["last_hour_kw"][-3] is None and e["last_hour_kw"][-1] == 1.84
    assert len(e["last_24h_hourly_kwh"]) == 24 and e["last_24h_kwh"] == pytest.approx(21.6)
    assert e["last_24h_start_hour"] == 18 and e["today_kwh"] == pytest.approx(16.2)
    assert e["usual_24h_hourly_kwh"] == [0.9] * 24 and e["base_kw"] == 0.9
    # Whole days only, oldest first, ending yesterday: today's partial day is not a bar.
    assert [d["date"] for d in e["days"]][-1] == "2026-10-01" and len(e["days"]) == 5


def test_a_newly_paired_meter_has_no_usual_day_and_short_history():
    e = energy.build_live_electricity(NOW, {"state": "unavailable"}, [], _hourly(1)[-5:], [])
    assert e["kw_now"] is None and e["state"] == "unknown"
    assert e["usual_hourly_kwh"] is None and e["usual_24h_hourly_kwh"] is None
    assert e["last_24h_hourly_kwh"][:19] == [None] * 19 and e["last_24h_kwh"] == pytest.approx(4.5)
    assert e["days"] == [] and e["base_kw"] == 0.9


class FakeHA:
    def __init__(self, states):
        self.states = states
        self.calls: list[str] = []
        self.down = False

    def get_json(self, path):
        self.calls.append(path)
        if self.down:
            raise OSError("connection refused")
        if path == "/api/states":
            return self.states
        if path.startswith("/api/states/"):
            return {"entity_id": path.rsplit("/", 1)[1], "state": "1840.0"}
        if path.startswith("/api/history/period/"):
            return [[{"state": "1840.0", "last_changed": _iso(NOW - timedelta(minutes=30))}]]
        raise AssertionError(path)

    def statistics(self, statistic_id, start, end, period):
        assert statistic_id == ENERGY
        return _hourly(5) if period == "hour" else []


def test_sample_data_until_the_powerlync_appears_then_live():
    ha = FakeHA([])
    clock = [0.0]
    source = energy.LiveEnergy("http://ha", lambda: "token", ha.get_json, ha.statistics, clock=lambda: clock[0])

    doc = source.snapshot(NOW)
    assert doc["electricity"]["sample"] is True
    source.snapshot(NOW)
    assert ha.calls.count("/api/states") == 1          # not asked again every 15 s

    ha.states = _states()
    clock[0] += energy.DISCOVERY_SECONDS
    doc = source.snapshot(NOW)
    assert doc["electricity"]["sample"] is False and doc["electricity"]["kw_now"] == 1.84
    assert doc["gas"]["sample"] is True and doc["entities"] == {"power": POWER, "energy": ENERGY}
    assert f"filter_entity_id={POWER}" in next(c for c in ha.calls if c.startswith("/api/history"))


def test_once_live_home_assistant_down_is_an_error_not_sample_data():
    ha = FakeHA(_states())
    source = energy.LiveEnergy("http://ha", lambda: "token", ha.get_json, ha.statistics, clock=lambda: 1000.0)
    source.snapshot(NOW)
    ha.down = True
    source._cache.clear()
    with pytest.raises(OSError):
        source.snapshot(NOW)


def test_no_token_and_home_assistant_down_before_pairing_are_both_sample_data():
    ha = FakeHA(_states())
    assert energy.LiveEnergy("http://ha", lambda: None, ha.get_json, ha.statistics).snapshot(NOW)["electricity"]["sample"]
    assert ha.calls == []
    ha.down = True
    assert energy.LiveEnergy("http://ha", lambda: "t", ha.get_json, ha.statistics).snapshot(NOW)["electricity"]["sample"]


def test_the_endpoint_is_a_502_when_home_assistant_fails(tmp_path):
    cfg = tmp_path / "devices.local.yaml"
    cfg.write_text(yaml.dump({}), encoding="utf-8")
    ha = FakeHA(_states())
    source = energy.LiveEnergy("http://ha", lambda: "token", ha.get_json, ha.statistics)
    client = TestClient(web_app.create_app(config_path=cfg, check_camera_ports=False, energy_source=source))
    assert client.get("/api/energy").json()["electricity"]["sample"] is False
    ha.down = True
    source._cache.clear()
    assert client.get("/api/energy").status_code == 502


# ── The setup script ──

def _setup_script():
    path = Path(__file__).resolve().parents[2] / "scripts" / "setup-ha-powerlync.py"
    spec = importlib.util.spec_from_file_location("setup_ha_powerlync", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_setup_picks_the_powerlync_out_of_the_homekit_accessories():
    setup = _setup_script()
    form = {"data_schema": [{"name": "device", "type": "select", "options": [
        ["Eve Energy 1A2B", "Eve Energy 1A2B (Outlet)"], ["Powerlync-001-000528", "Powerlync-001-000528 (Outlet)"]]}]}
    assert setup.powerlync_choice(form) == "Powerlync-001-000528"
    assert setup.powerlync_choice({"data_schema": [{"name": "device", "options": [["Eve", "Eve"]]}]}) is None
    assert setup.SETUP_CODE.match("123-45-678") and setup.SETUP_CODE.match("12345678")
    assert not setup.SETUP_CODE.match("1234-5678")


def test_setup_installs_the_component_once(tmp_path):
    setup = _setup_script()
    files = {name: f"# {name}\n" for name in setup.COMPONENT_FILES}
    assert len(setup.ensure_component(tmp_path, files, apply=False)) == 5
    assert not (tmp_path / "custom_components").exists()     # a dry run writes nothing
    assert len(setup.ensure_component(tmp_path, files, apply=True)) == 5
    assert setup.ensure_component(tmp_path, files, apply=True) == []


def test_setup_takes_only_the_component_from_the_archive(monkeypatch):
    setup = _setup_script()
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name in (*setup.COMPONENT_FILES, "README.md", "../evil.py"):
            member = f"repo-sha/custom_components/powerlync_energy/{name}" if name != "README.md" else "repo-sha/README.md"
            data = name.encode()
            info = tarfile.TarInfo(member)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(setup, "urlopen", lambda url, timeout: Response(buf.getvalue()))
    assert sorted(setup.fetch_component()) == sorted(setup.COMPONENT_FILES)


# ── Last night's forecast on the Energy view ──

def test_a_forecast_is_shown_only_while_it_is_fresh(tmp_path):
    path = tmp_path / "energy_forecast.json"
    doc = {"model": "lightgbm", "at": datetime(2026, 10, 2, 3, 45).isoformat(),
           "next_24h_total": 19.4, "hourly": [{"at": "2026-10-02T04:00:00", "value": 0.8}],
           "scores": [{"model": "lightgbm", "mae": 0.08, "skill": 0.12}]}
    path.write_text(json.dumps(doc), encoding="utf-8")

    assert energy.read_forecast(path, datetime(2026, 10, 2, 9))["model"] == "lightgbm"
    # The job runs nightly; a file from two days ago means it stopped running.
    assert energy.read_forecast(path, datetime(2026, 10, 4, 9)) is None
    assert energy.read_forecast(tmp_path / "nope.json", datetime(2026, 10, 2, 9)) is None
    path.write_text("not json", encoding="utf-8")
    assert energy.read_forecast(path, datetime(2026, 10, 2, 9)) is None


def test_the_endpoint_carries_the_forecast(tmp_path):
    cfg = tmp_path / "devices.local.yaml"
    cfg.write_text(yaml.dump({}), encoding="utf-8")
    path = tmp_path / "energy_forecast.json"
    path.write_text(json.dumps({"model": "chronos-2", "at": datetime.now().isoformat(),
                                "next_24h_total": 21.0, "hourly": [{"at": "x", "value": 1}],
                                "scores": []}), encoding="utf-8")
    client = TestClient(web_app.create_app(config_path=cfg, check_camera_ports=False,
                                           energy_forecast_path=path))
    assert client.get("/api/energy").json()["forecast"]["model"] == "chronos-2"

    empty = TestClient(web_app.create_app(config_path=cfg, check_camera_ports=False,
                                          energy_forecast_path=tmp_path / "missing.json"))
    assert empty.get("/api/energy").json()["forecast"] is None   # nothing to show, and that is fine


def test_the_view_names_the_model_that_wrote_the_forecast():
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "function energyForecastHtml" in js and "Next 24 hours" in js
    assert "escapeHtml(forecast.model)" in js          # the model is named on screen
    assert "energyForecastHtml(latestEnergy.forecast" in js


# ── Gas from the owner's own bills ──

BILL_CSV = ("Bill from date,Bill to date,# of days,Billed GJ,Average temperature\n"
            "22/07/2026,18/08/2026,28,0.9,19\n"
            "19/06/2026,21/07/2026,33,1.3,18\n"
            "22/05/2026,18/06/2026,28,1.9,16\n"
            "21/04/2026,21/05/2026,31,3.4,13\n"
            "21/03/2026,20/04/2026,31,9,8\n"
            "20/02/2026,20/03/2026,29,9.4,6\n"
            "18/07/2025,20/08/2025,34,1.2,18\n"
            "21/01/2025,18/02/2025,29,14.9,0\n")


def _with_bills(tmp_path):
    from src.python import ai_data
    db = ai_data.connect(tmp_path / "ai-data" / "gas.db")
    doc = ai_data.add_file(db, tmp_path / "ai-data" / "files", "history.csv", BILL_CSV.encode())
    ai_data.import_file(db, doc["id"])
    db.close()
    return tmp_path / "ai-data" / "gas.db"


def test_gas_is_billing_periods_not_invented_days(tmp_path):
    """The meter cannot be read, so the gas column shows what was really
    measured - each bill - rather than daily bars nobody measured."""
    doc = energy.gas_from_records(_with_bills(tmp_path), now=datetime(2026, 9, 19))

    assert doc["sample"] is False and doc["provider"] == "FortisBC"
    assert len(doc["periods"]) == 8 and doc["periods"][-1]["gj"] == 0.9
    assert doc["last_period_gj"] == 0.9 and doc["last_period"]["days"] == 27
    assert doc["gj_per_day"] == pytest.approx(0.033, abs=0.002)
    assert doc["model"]["kind"] == "degree_day"
    # No cost on this export, so the price per GJ is the illustrative one and says so.
    assert doc["rate_measured"] is False and doc["rate"] == energy.GAS_RATE


def test_the_same_period_last_year_is_the_comparison_people_make(tmp_path):
    doc = energy.gas_from_records(_with_bills(tmp_path), now=datetime(2026, 9, 19))
    year = doc["same_period_last_year"]
    assert year["end"] == "2025-08-20" and year["gj"] == 1.2
    assert year["change_percent"] == -25       # 0.9 against 1.2 a year earlier


def test_without_any_bills_the_gas_column_stays_sample_data(tmp_path):
    assert energy.gas_from_records(tmp_path / "nothing" / "gas.db") is None


def test_the_endpoint_serves_real_gas_once_a_bill_is_in(tmp_path):
    cfg = tmp_path / "devices.local.yaml"
    cfg.write_text(yaml.dump({}), encoding="utf-8")
    _with_bills(tmp_path)
    client = TestClient(web_app.create_app(config_path=cfg, check_camera_ports=False,
                                           ai_data_dir=tmp_path / "ai-data"))
    gas = client.get("/api/energy").json()["gas"]
    assert gas["sample"] is False and gas["last_period_gj"] == 0.9
    assert "periods" in gas and gas["model"]["base_gj_per_day"] > 0


def test_the_view_draws_bills_and_names_what_fitted_them():
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "function gasColumnHtml" in js and "GJ in the last bill" in js
    assert "fitted to your bills and the weather" in js
    assert "Same period last year" in js and "Hot water & cooking" in js
    # The sample path is still there for a house with no bills uploaded.
    assert "g.sample ? energyColumnHtml({" in js


def test_a_duplicated_period_is_not_a_bar_but_its_money_still_counts(tmp_path):
    """The owner's invoice PDFs cover days the yearly export already covers.
    Drawing both would show the same gas twice; but the PDF is where the
    dollars are, so the price per GJ still comes from it."""
    from src.python import ai_data

    path = _with_bills(tmp_path)
    db = ai_data.connect(path)
    db.execute("INSERT INTO bills (period_start, period_end, gj, cost) VALUES "
               "('2026-06-18','2026-08-12',1.9,31.82)")
    db.commit()
    db.close()

    doc = energy.gas_from_records(path, now=datetime(2026, 9, 19))
    assert doc["duplicates_ignored"] == 1
    assert all(p["end"] != "2026-08-12" for p in doc["periods"]), "the duplicate is not drawn"
    assert doc["last_period_gj"] == 0.9
    assert doc["rate_measured"] is True and doc["rate"] == pytest.approx(31.82 / 1.9, abs=0.01)


# ── Electricity from BC Hydro's exports, before the PowerLync ──

POWER_USAGE_CSV = ('"Account Holder","Account Number","Interval Start Date/Time","Net Consumption (kWh)"\n'
                   '"A B","0","2025-07-01","366.00"\n"A B","0","2025-08-01","425.00"\n'
                   '"A B","0","2025-09-01","411.00"\n"A B","0","2026-07-01","445.00"\n'
                   '"A B","0","2026-08-01","422.00"\n"A B","0","2026-09-01","500.00"\n')
POWER_BILL_CSV = ('"Invoice Number","Type","Amount Due","From Date","To Date","kWh Usage","Basic Charge","Usage Charge"\n'
                  '"1","Amount Due","82.99",,,,,\n'
                  '"1","Detail: Usage",,"2026-07-20","2026-09-18","714.0","13.74","78.33"\n')


def _with_power(tmp_path):
    from src.python import ai_data
    db = ai_data.connect(tmp_path / "ai-data" / "gas.db")
    for name, text in (("usage.csv", POWER_USAGE_CSV), ("billing.csv", POWER_BILL_CSV)):
        doc = ai_data.add_file(db, tmp_path / "ai-data" / "files", name, text.encode())
        ai_data.import_file(db, doc["id"])
    db.close()
    return tmp_path / "ai-data" / "gas.db"


def test_uploaded_bc_hydro_history_becomes_the_electricity_column(tmp_path):
    doc = energy.electricity_from_records(_with_power(tmp_path), now=datetime(2026, 9, 19))

    assert doc["sample"] is False and doc["mode"] == "records"
    assert doc["provider"] == "BC Hydro" and doc["period_kind"] == "month"
    assert len(doc["periods"]) == 6 and doc["last_period_kwh"] == 500.0
    # The money comes from the billing export, not from a guess.
    assert doc["rate_measured"] is True and doc["rate"] == pytest.approx(82.99 / 714, abs=0.0005)
    assert doc["last_bill"]["kwh"] == 714.0 and doc["last_bill"]["cost"] == 82.99


def test_a_year_on_year_comparison_comes_out_of_it(tmp_path):
    doc = energy.electricity_from_records(_with_power(tmp_path), now=datetime(2026, 9, 19))
    year = doc["same_period_last_year"]
    assert year["end"] == "2025-10-01" and year["kwh"] == 411.0
    assert year["change_percent"] == 22      # 500 against 411


def test_records_mode_never_pretends_to_be_live(tmp_path):
    cfg = tmp_path / "devices.local.yaml"
    cfg.write_text(yaml.dump({}), encoding="utf-8")
    _with_power(tmp_path)
    client = TestClient(web_app.create_app(config_path=cfg, check_camera_ports=False,
                                           ai_data_dir=tmp_path / "ai-data"))
    e = client.get("/api/energy").json()["electricity"]
    assert e["mode"] == "records" and e["sample"] is False
    assert "kw_now" not in e and "last_24h_kwh" not in e, "there is no now without a meter"

    js = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "function powerRecordsColumnHtml" in js
    assert "there is no \"now\" and no last-24-hours line yet" in js
    # The hourly forecast belongs to the live meter, not to monthly bills.
    assert 'e.mode === "records" ? "" : energyForecastHtml' in js


def test_the_home_card_shows_the_flow_with_or_without_a_reading():
    """The flow replaced the electricity-and-gas halves (2026-09-24). Without a
    reading it waits, and the figures come from the bills - gas included, which
    has two years of real history."""
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    home = js[js.index("function renderHomeEnergy()"):js.index("function energyColumnHtml(")]
    assert home.count("energyFlowCompactSvg(m)") == 2          # waiting, and live
    assert "Gas, last bill" in home and "g.last_period_gj" in home
    assert "day.soFar" in home and "energyMoney(day.pace * m.price)" in home
    assert "function homeElectricityHalf" not in js


# ── The power flow and the bill in progress ──

def test_a_paired_but_silent_powerlync_is_reported_as_waiting_for_the_meter():
    silent = FakeHA([{**s, "state": "0.0"} for s in _states()])
    doc = energy.LiveEnergy("http://ha", lambda: "t", silent.get_json, silent.statistics).snapshot(NOW)
    assert doc["electricity"]["sample"] is True and doc["meter"] == "waiting"
    nothing = FakeHA([])
    assert "meter" not in energy.LiveEnergy("http://ha", lambda: "t", nothing.get_json, nothing.statistics).snapshot(NOW)


def test_furnace_state_tells_the_fan_from_the_burner():
    assert energy.furnace_state({"equipment_running": "fan,compHeat1"}) == "heating"
    assert energy.furnace_state({"equipment_running": "fan"}) == "fan"
    assert energy.furnace_state({"equipment_running": ""}) == "idle"
    assert energy.furnace_state({"hvac_action": "heating"}) == "heating"
    assert energy.furnace_state({"hvac_action": "idle"}) == "idle"
    assert energy.furnace_state({}) is None and energy.furnace_state(None) is None


def test_heat_map_and_nights_leave_unfinished_hours_blank():
    doc = energy.snapshot(NOW)["electricity"]
    assert len(doc["heat"]) == energy.HEAT_DAYS and all(len(r["hours"]) == 24 for r in doc["heat"])
    today = doc["heat"][-1]
    assert today["date"] == NOW.date().isoformat()
    assert today["hours"][NOW.hour - 1] is not None and today["hours"][NOW.hour] is None
    night = doc["base_nights"][-1]
    assert night["kw"] == min(today["hours"][:6])


RECORDS = {"tier1_price": 0.1187, "tier2_price": 0.1408, "tier2_threshold_kwh": 1354.0, "basic_per_day": 0.2344,
           "tier_bill_days": 60, "last_bill": {"start": "2026-05-21", "end": "2026-07-20", "kwh": 920.0, "cost": 131.73}}


def test_the_bill_rolls_forward_from_the_last_one_and_prices_by_step():
    now = datetime(2026, 9, 28, 12, 0)             # the period after 07-20 + 60 is 09-18 .. 11-17
    days = [{"date": f"2026-09-{d:02d}", "kwh": 15.0} for d in range(18, 28)]
    bill = energy.bill_progress(RECORDS, {"days": days, "today_kwh": 7.5}, now)
    assert (bill["start"], bill["end"], bill["days"], bill["day"]) == ("2026-09-18", "2026-11-17", 60, 11)
    assert bill["kwh"] == 157.5 and bill["partial"] is False and bill["threshold_kwh"] == 1354
    assert bill["projected_kwh"] == 900                # 15 kWh a day for 60 days
    assert bill["projected_cost"] == round(900 * 0.1187 + 60 * 0.2344, 2)
    heavy = energy.bill_progress(RECORDS, {"days": [{**d, "kwh": 30.0} for d in days], "today_kwh": 15.0}, now)
    assert heavy["projected_kwh"] == 1800
    assert heavy["projected_cost"] == round(1354 * 0.1187 + 446 * 0.1408 + 60 * 0.2344, 2)


def test_days_before_the_first_reading_are_not_guessed():
    now = datetime(2026, 9, 28, 12, 0)
    days = [{"date": f"2026-09-{d:02d}", "kwh": 15.0} for d in range(24, 28)]
    bill = energy.bill_progress(RECORDS, {"days": days, "today_kwh": 7.5}, now)
    assert bill["partial"] is True and bill["counted_from"] == "2026-09-24"
    assert bill["kwh"] == 67.5 and bill["projected_kwh"] == round(67.5 + 15 * (50 - 0.5))


def test_no_priced_bill_means_no_bill_card():
    assert energy.bill_progress(None, {"days": []}) is None
    assert energy.bill_progress({**RECORDS, "tier2_threshold_kwh": None}, {"days": []}) is None


def test_the_preview_keeps_sample_electricity_where_bills_would_replace_it(tmp_path, monkeypatch):
    cfg = tmp_path / "devices.local.yaml"
    cfg.write_text(yaml.dump({}), encoding="utf-8")
    monkeypatch.setattr(web_app, "_furnace_now", lambda path: "fan")
    monkeypatch.setattr(energy, "electricity_from_records", lambda path: {**RECORDS, "sample": False, "mode": "records"})
    client = TestClient(web_app.create_app(config_path=cfg, check_camera_ports=False))
    plain = client.get("/api/energy").json()
    assert plain["electricity"]["mode"] == "records" and plain["preview"] is False
    preview = client.get("/api/energy?preview=1").json()
    assert preview["electricity"]["sample"] is True and preview["preview"] is True
    assert preview["electricity"]["bill"]["threshold_kwh"] == 1354 and preview["furnace"] == "fan"


def test_the_live_view_has_its_cards_and_the_flow_draws_no_blur():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    for card in ("energyStatus", "energyLive", "energyFlow", "energyNow", "energyDay", "energyBill", "energyBase", "energyHeat"):
        assert f'id="{card}"' in html
    flow = js[js.index("/* ── The power flow ──"):js.index("function renderEnergyView()")]
    # The particles animate; a blur filter would be re-rendered every frame on
    # the wall panel's Raspberry Pi 4. Glow is a wide faint stroke instead.
    assert "feGaussianBlur" not in flow and "filter=" not in flow
    assert "energyFlowCompactSvg(m)" in js[js.index("function renderHomeEnergy()"):]


def test_the_flow_shows_while_waiting_for_the_meter():
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    view = js[js.index("function renderEnergyView()"):]
    # Bills mode (no reading) still draws the flow, alone and waiting.
    assert 'classList.toggle("flow-only", !live)' in view
    assert "else renderEnergyFlowCard(energyFlowModel(e, g, latestEnergy.furnace))" in view
    assert "Waiting for the first meter reading" in js
    home = js[js.index("function renderHomeEnergy()"):]
    assert home.index("energyFlowCompactSvg(m)") < home.index('if (e.mode === "records")') + 400


def test_the_registers_first_reading_is_not_consumption():
    # 2026-09-24: the register went 0 -> 104491.9 kWh at 09:20 and Home
    # Assistant booked all of it to the 09:00 hour.
    midnight = NOW.replace(hour=0, minute=0)
    hourly = [{"start": _iso(midnight + timedelta(hours=h)), "change": 0.0, "state": 0.0} for h in range(9)]
    hourly.append({"start": _iso(midnight + timedelta(hours=9)), "change": 104492.4, "state": 104492.4})
    hourly += [{"start": _iso(midnight + timedelta(hours=h)), "change": 0.6, "state": 104492.4 + 0.6 * (h - 9)}
               for h in range(10, NOW.hour)]
    daily = [{"start": _iso(midnight - timedelta(days=1)), "change": 0.0, "state": 0.0}]
    e = energy.build_live_electricity(NOW, None, [], hourly, daily)

    assert e["today_hourly_kwh"][:10] == [None] * 10       # not zeros: the meter was not reporting
    assert e["today_kwh"] == pytest.approx(0.6 * (NOW.hour - 10))
    assert e["base_kw"] == 0.6 and e["days"] == []


def test_metered_kwh_rejects_what_no_house_can_draw():
    assert energy.metered_kwh({"change": 2.5}) == 2.5                    # no state asked for: trusted
    assert energy.metered_kwh({"change": 2.5, "state": 0}) is None       # register not reporting
    assert energy.metered_kwh({"change": 60.0, "state": 9e4}) is None    # a jump, not an hour
    assert energy.metered_kwh({"change": 60.0, "state": 9e4}, hours=24) == 60.0
    assert energy.metered_kwh({"change": -1.0, "state": 9e4}) is None
