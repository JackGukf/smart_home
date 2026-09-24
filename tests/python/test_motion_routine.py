"""The motion routine by area: the usual day, the chosen day, the last motion."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from src.python import house_memory, motion_routine, web_app

STATIC = Path(__file__).resolve().parents[2] / "src" / "python" / "web_static"
DAY = date(2026, 9, 23)
NOW = datetime(2026, 9, 23, 20, 0)
OFFICE = ["binary_sensor.office_pir_motion"]
FAMILY = ["binary_sensor.8jt7_motion", "binary_sensor.0xa4c138d00106c90d_presence"]


def _db(tmp_path: Path, events: list[tuple[datetime, str, str]]) -> Path:
    path = tmp_path / "events.db"
    conn = house_memory.connect(path)
    conn.executemany("INSERT INTO events (ts, entity_id, state, source) VALUES (?, ?, ?, 'live')",
                     [(t.timestamp(), e, s) for t, e, s in events])
    conn.commit()
    conn.close()
    return path


def test_usual_counts_days_not_events_and_an_area_is_its_sensors_together(tmp_path):
    events = []
    for back in range(1, 8):                         # 7 of the 14 days, 07:xx, both family room sensors
        morning = datetime.combine(DAY - timedelta(days=back), datetime.min.time()) + timedelta(hours=7)
        events += [(morning, FAMILY[0], "on"), (morning + timedelta(minutes=5), FAMILY[1], "on"),
                   (morning + timedelta(minutes=9), FAMILY[0], "off")]
    doc = motion_routine.routine_from_path(_db(tmp_path, events), {"Family Room": FAMILY}, DAY, NOW)
    usual = doc["areas"]["Family Room"]["usual"]
    assert usual[7] == 0.5 and sum(usual) == 0.5    # one day counts once, "off" is not motion


def test_the_day_is_in_five_minute_steps_and_last_is_the_newest_motion(tmp_path):
    events = [(NOW - timedelta(hours=2, minutes=3), OFFICE[0], "on"),    # 17:57 -> 17:55
              (NOW - timedelta(hours=2, minutes=1), OFFICE[0], "on"),    # same step
              (NOW - timedelta(minutes=30), OFFICE[0], "on"),            # 19:30
              (NOW - timedelta(days=20), OFFICE[0], "on")]               # outside the window
    doc = motion_routine.routine_from_path(_db(tmp_path, events), {"Office": OFFICE, "Garage": []}, DAY, NOW)
    office = doc["areas"]["Office"]
    assert office["day"] == [17 * 60 + 55, 19 * 60 + 30]
    assert office["last"] == (NOW - timedelta(minutes=30)).timestamp()
    assert sum(office["usual"]) == 0                 # 20 days ago is not in the usual
    assert doc["areas"]["Garage"] == {"usual": [0.0] * 24, "day": [], "last": None, "entities": []}


def test_cameras_join_their_area_by_name_and_the_rest_become_areas(tmp_path):
    cams = ["binary_sensor.office_camera_npu_person", "binary_sensor.frontyard_camera_npu_person",
            "binary_sensor.garage_camera_npu_person"]
    path = _db(tmp_path, [(NOW - timedelta(hours=1), c, "on") for c in cams])
    doc = motion_routine.routine_from_path(path, {"Office": [], "Front Yard": ["binary_sensor.x_presence"]}, DAY, NOW)
    assert doc["areas"]["Office"]["entities"] == [cams[0]]
    assert doc["areas"]["Front Yard"]["entities"] == ["binary_sensor.x_presence", cams[1]]
    assert doc["areas"]["Garage"]["entities"] == [cams[2]] and doc["areas"]["Garage"]["last"]


def test_an_area_quiet_for_weeks_still_has_its_last_motion(tmp_path):
    long_ago = NOW - timedelta(days=30)
    doc = motion_routine.routine_from_path(_db(tmp_path, [(long_ago, OFFICE[0], "on")]), {"Office": OFFICE}, DAY, NOW)
    assert doc["areas"]["Office"]["last"] == long_ago.timestamp()


def test_the_endpoint_checks_what_it_is_given(tmp_path):
    cfg = tmp_path / "devices.local.yaml"
    cfg.write_text(yaml.dump({}), encoding="utf-8")
    db = _db(tmp_path, [(datetime.now() - timedelta(minutes=5), OFFICE[0], "on")])
    app = web_app.create_app(config_path=cfg, check_camera_ports=False,
                             memory_service=house_memory.SummaryCache(db))
    client = TestClient(app)
    doc = client.post("/api/motion/routine", json={"areas": {"Office": OFFICE}}).json()
    assert doc["day"] == date.today().isoformat() and doc["areas"]["Office"]["last"]
    assert client.post("/api/motion/routine", json={"areas": {"x": ["1; DROP TABLE"]}}).status_code == 400
    assert client.post("/api/motion/routine", json={"areas": {}, "day": "yesterday"}).status_code == 400
    missing = web_app.create_app(config_path=cfg, check_camera_ports=False,
                                 memory_service=house_memory.SummaryCache(tmp_path / "none.db"))
    assert TestClient(missing).post("/api/motion/routine", json={"areas": {}}).status_code == 503


def test_the_motion_view_has_the_routine_and_it_opens_the_timeline_on_tap():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    assert 'id="motionRoutine"' in html
    assert "function renderMotionPlaces(" in js and "function renderMotionTimeline(" in js
    assert 'data-routine-area="' in js           # each area row opens the timeline
