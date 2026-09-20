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
    # Per section: once electricity is live, gas is still sample data and says so.
    assert "sample.hidden = !e.sample" in js and "note.hidden = !e.sample && !g.sample" in js
    assert 'g.sample ? "Sample" : "Read daily"' in js


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
    old = [{"entity_id": "sensor.powerlync_energy_monitor_1_instantaneous_demand"},
           {"entity_id": "sensor.powerlync_energy_monitor_1_total_energy_consumed"},
           {"entity_id": "sensor.powerlync_energy_monitor_1_local_instantaneous_demand"}]
    assert energy.find_powerlync_entities(old) == ("sensor.powerlync_energy_monitor_1_instantaneous_demand",
                                                   "sensor.powerlync_energy_monitor_1_total_energy_consumed")


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
