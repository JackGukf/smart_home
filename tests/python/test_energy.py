"""The Energy card and view: sample data until the PowerLync is paired, said so
on screen, and the Discovery apps that replaced three sidebar entries."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

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
    assert "sample.hidden = !latestEnergy.sample" in js and "note.hidden = !latestEnergy.sample" in js


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
