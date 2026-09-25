"""Phase 0: the house memory keeps every event, and what you said about it.

  * a state change is kept; an attribute-only update is not, except where the
    attributes are the point (the thermostat starting to heat);
  * camera snapshot rotations and device diagnostics are not house activity;
  * the recorder's opening point is not a change, and a backfill that
    overlaps the live stream stores nothing twice;
  * "a day" is the viewer's day, and today does not count until it is over;
  * labels come from a fixed list, on events that exist;
  * the service is installed with the dashboard and yields to the house.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from src.python import house_memory as hm
from src.python import house_memory_collector as collector
from src.python.web_app import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"
T0 = datetime(2026, 9, 14, 7, 0, tzinfo=ZoneInfo("America/Vancouver"))  # a Monday


def _state(state, when: datetime, **attributes) -> dict:
    return {"state": state, "last_updated": when.isoformat(), "last_changed": when.isoformat(), "attributes": attributes}


def test_a_change_is_kept_and_an_attribute_update_is_not() -> None:
    before = _state("off", T0, friendly_name="Entry")
    assert hm.event_from_states("binary_sensor.entry", _state("on", T0), before).state == "on"
    assert hm.event_from_states("binary_sensor.entry", _state("off", T0, brightness=3), before) is None


def test_the_thermostat_is_kept_when_it_starts_heating() -> None:
    idle = _state("heat", T0, hvac_action="idle", current_temperature=20.5, temperature=21)
    heating = _state("heat", T0 + timedelta(minutes=3), hvac_action="heating", current_temperature=20.5, temperature=21)

    event = hm.event_from_states("climate.my_ecobee", heating, idle)

    assert event is not None and json.loads(event.attrs)["hvac_action"] == "heating"
    assert hm.event_from_states("climate.my_ecobee", idle, idle) is None


@pytest.mark.parametrize("entity_id", [
    "camera.living_room_camera", "update.zigbee2mqtt", "sensor.voice_panel_psram_free",
    "sensor.0xa4c1_linkquality", "sensor.panel_wifi_signal",
])
def test_noise_is_not_house_activity(entity_id: str) -> None:
    assert not hm.wanted(entity_id)


def test_numbers_are_kept_as_numbers() -> None:
    event = hm.event_from_states("sensor.office_temperature", _state("21.4", T0), _state("21.3", T0))
    assert event.value == 21.4
    assert hm.event_from_states("sensor.x", _state("nan", T0), _state("1", T0)).value is None


def test_the_recorders_opening_point_is_not_an_event() -> None:
    series = [
        {"entity_id": "binary_sensor.entry", **_state("off", T0)},  # the state at the window's start
        _state("on", T0 + timedelta(minutes=5)),
        _state("off", T0 + timedelta(minutes=6)),
    ]
    events = hm.events_from_history(series)
    assert [e.state for e in events] == ["on", "off"]
    assert events[0].entity_id == "binary_sensor.entry"


def test_the_same_event_twice_is_stored_once(tmp_path: Path) -> None:
    memory = hm.HouseMemory(tmp_path / "events.db")
    event = hm.event_from_states("binary_sensor.entry", _state("on", T0), _state("off", T0))

    assert memory.add_events([event], "live") == 1
    assert memory.add_events([event], "backfill") == 0


def _fill_days(memory: hm.HouseMemory, days: int, start: datetime = T0) -> None:
    events = []
    for day in range(days):
        for hour in range(24):
            at = (start.replace(hour=0) + timedelta(days=day, hours=hour, minutes=10)).timestamp()
            events.append(hm.Event(at, "binary_sensor.entry", "on", "off", None, None))
    memory.add_events(events, "backfill")


def test_days_are_the_viewers_days_and_today_is_not_yet_complete(tmp_path: Path) -> None:
    memory = hm.HouseMemory(tmp_path / "events.db")
    _fill_days(memory, 8)  # Monday 14th to Monday 21st, local
    now = (T0 + timedelta(days=7, hours=12)).timestamp()  # Monday 21st, midday

    summary = memory.summary("America/Vancouver", now)

    assert summary["days_complete"] == 7
    assert summary["weekday_coverage"] == [1, 1, 1, 1, 1, 1, 1]
    assert summary["ready"] is False
    assert summary["daily"][-1] == {"date": "2026-09-21", "events": 24, "complete": False}


def test_review_lists_unlabelled_doors_and_cameras_and_labels_replace(tmp_path: Path) -> None:
    memory = hm.HouseMemory(tmp_path / "events.db")
    memory.upsert_entities([
        {"entity_id": "binary_sensor.back_door", "attributes": {"device_class": "door", "friendly_name": "Back door"}},
        {"entity_id": "binary_sensor.entry", "attributes": {"device_class": "occupancy"}},
    ])
    now = T0.timestamp()
    memory.add_events([
        hm.Event(now - 60, "binary_sensor.back_door", "on", "off", None, None),
        hm.Event(now - 50, "binary_sensor.garage_camera_npu_person", "on", "off", None, None),
        hm.Event(now - 40, "binary_sensor.entry", "on", "off", None, None),  # motion is not reviewed
        hm.Event(now - 30, "binary_sensor.back_door", "off", "on", None, None),  # closing is not
    ], "live")

    review = memory.summary("UTC", now)["review"]
    assert [r["kind"] for r in review] == ["camera", "door"]

    memory.label(review[0]["id"], "false_alarm")
    memory.label(review[0]["id"], "normal")
    summary = memory.summary("UTC", now)
    assert [r["kind"] for r in summary["review"]] == ["door"]
    assert summary["labels"] == {"normal": 1, "false_alarm": 0, "unusual": 0}

    with pytest.raises(hm.FeedbackError):
        memory.label(review[0]["id"], "delete_everything")
    with pytest.raises(hm.FeedbackError):
        memory.label(999_999, "normal")


def test_the_collector_is_running_only_while_it_beats(tmp_path: Path) -> None:
    memory = hm.HouseMemory(tmp_path / "events.db")
    now = T0.timestamp()
    assert memory.summary("UTC", now)["collector"]["running"] is False
    memory.set_meta("collector_heartbeat", now - 30)
    assert memory.summary("UTC", now)["collector"]["running"] is True
    assert memory.summary("UTC", now + hm.HEARTBEAT_STALE_S)["collector"]["running"] is False


def test_a_restart_backfills_only_the_gap(tmp_path: Path, monkeypatch) -> None:
    memory = hm.HouseMemory(tmp_path / "events.db")
    now = T0.timestamp()
    last = now - 3600
    memory.add_events([hm.Event(last, "binary_sensor.entry", "on", "off", None, None)], "live")
    asked: list[str] = []

    def ha_get(base_url, token, path, timeout=15.0):
        asked.append(path)
        if path == "/api/states":
            return [{"entity_id": "binary_sensor.entry", "attributes": {"friendly_name": "Entry"}},
                    {"entity_id": "camera.garage", "attributes": {}}]
        return [[{"entity_id": "binary_sensor.entry", **_state("on", datetime.fromtimestamp(last, timezone.utc))},
                 _state("off", datetime.fromtimestamp(now - 600, timezone.utc))]]

    monkeypatch.setattr(collector, "ha_get", ha_get)
    added = collector.backfill(memory, "http://ha", "token", now=now)

    history = [p for p in asked if p.startswith("/api/history")]
    assert len(history) == 1, "one hour of gap is one request"
    assert hm.utc_iso(last - 300).replace(":", "%3A") in history[0]
    assert "camera.garage" not in history[0]
    assert added == 1


def test_the_live_stream_learns_new_entities(tmp_path: Path) -> None:
    memory = hm.HouseMemory(tmp_path / "events.db")
    live = collector.Collector(memory, "http://ha", "token")
    live.handle({"type": "event", "event": {"data": {
        "entity_id": "binary_sensor.shed_door",
        "old_state": None,
        "new_state": _state("off", T0, device_class="door", friendly_name="Shed door"),
    }}})
    live.flush()
    row = memory._conn.execute("SELECT name, device_class FROM entities").fetchone()
    assert tuple(row) == ("Shed door", "door")
    assert live.seen == 1


def test_the_endpoints_sanitise_the_zone_and_refuse_bad_labels(tmp_path: Path) -> None:
    memory = hm.HouseMemory(tmp_path / "events.db")
    memory.add_events([hm.Event(T0.timestamp(), "binary_sensor.entry", "on", "off", None, None)], "live")
    client = TestClient(create_app(
        discovery_path=tmp_path / "switches.json", config_path=tmp_path / "devices.yaml",
        check_camera_ports=False, memory_service=hm.SummaryCache(tmp_path / "events.db"),
    ))

    assert client.get("/api/memory/summary", params={"tz": "America/Vancouver"}).json()["time_zone"] == "America/Vancouver"
    assert client.get("/api/memory/summary", params={"tz": "../../etc/passwd"}).json()["time_zone"] == "UTC"
    assert client.post("/api/memory/feedback", json={"event_id": 1, "label": "normal"}).status_code == 200
    assert client.post("/api/memory/feedback", json={"event_id": 1, "label": "rm -rf"}).status_code == 400
    assert client.post("/api/memory/feedback", json={"event_id": 42, "label": "normal"}).status_code == 400


def test_before_the_collector_runs_the_tile_says_so(tmp_path: Path) -> None:
    assert hm.SummaryCache(tmp_path / "missing.db").summary("UTC") == {"available": False}


def test_the_service_is_installed_with_the_dashboard() -> None:
    unit = (PROJECT_ROOT / "deploy" / "systemd" / "user" / "house-memory.service").read_text(encoding="utf-8")
    installer = (PROJECT_ROOT / "scripts" / "install-dashboard-service.sh").read_text(encoding="utf-8")

    assert "ExecStart=/home/orangepi/smart_home_AI/.venv/bin/python -m src.python.house_memory_collector" in unit
    assert "WorkingDirectory=/home/orangepi/smart_home_AI" in unit
    assert "Restart=always" in unit and "Nice=10" in unit
    assert '"house-memory.service"' in installer


HARNESS = r"""
const src = require('fs').readFileSync(process.argv[2], 'utf8');
const pick = (name) => {
  const at = src.indexOf(`function ${name}(`);
  let depth = 0, i = src.indexOf('{', at);
  for (; i < src.length; i++) {
    if (src[i] === '{') depth++;
    else if (src[i] === '}') { depth--; if (depth === 0) return src.slice(at, i + 1); }
  }
};
eval(pick('learnDaysToReady'));
const thursday = new Date(2026, 8, 17, 12);
console.log(JSON.stringify([
  learnDaysToReady([4, 4, 4, 4, 4, 4, 4], 4, thursday),
  learnDaysToReady([4, 4, 4, 3, 4, 4, 4], 4, thursday),   // one more Thursday: today
  learnDaysToReady([4, 4, 4, 4, 3, 4, 4], 4, thursday),   // one more Friday: tomorrow
  learnDaysToReady([3, 4, 4, 4, 4, 4, 4], 4, thursday),   // one more Monday: in 5 days
  learnDaysToReady([0, 0, 0, 0, 0, 0, 0], 4, thursday),
]));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_the_countdown_to_phase_one(tmp_path: Path) -> None:
    harness = tmp_path / "harness.js"
    harness.write_text(HARNESS, encoding="utf-8")
    out = subprocess.run(["node", str(harness), str(APP_JS)], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout) == [0, 1, 2, 5, 28]


def test_the_armed_log_keeps_people_outdoors_only_while_the_alarm_was_armed(tmp_path: Path) -> None:
    memory = hm.HouseMemory(tmp_path / "events.db")
    t = 1_790_000_000.0
    alarm = "alarm_control_panel.duo_gong_neng_bao_jing_zhu_ji"
    garage = "binary_sensor.garage_camera_npu_person"
    backyard = "binary_sensor.0xa4c1382ad5555219_presence"
    office = "binary_sensor.office_camera_npu_person"           # indoors: never in this log
    ev = lambda ts, entity, state, old: hm.Event(t + ts, entity, state, old, None, None)
    memory.add_events([
        ev(0, garage, "on", "off"),                  # disarmed: not logged
        ev(100, alarm, "armed_away", "disarmed"),
        ev(200, garage, "on", "off"),
        ev(300, backyard, "on", "off"),
        ev(350, office, "on", "off"),
        ev(400, hm.ALARM_SPEAKER, "on", "off"),
        ev(500, alarm, "disarmed", "armed_away"),
        ev(600, backyard, "on", "off"),              # disarmed again: not logged
    ], "live")

    log = hm.armed_log(memory._conn, t + 700)

    assert [(line["entity_id"], line["kind"]) for line in log["recent"]] == [
        (hm.ALARM_SPEAKER, "speaker"), (backyard, "motion"), (garage, "camera")]
    assert log["armed_now"] is False


def test_an_alarm_armed_before_the_window_opens_counts_from_its_start(tmp_path: Path) -> None:
    memory = hm.HouseMemory(tmp_path / "events.db")
    t = 1_790_000_000.0
    memory.add_events([
        hm.Event(t, "alarm_control_panel.panel", "armed_home", "disarmed", None, None),
        hm.Event(t + 8 * 86400, "binary_sensor.frontyard_camera_npu_person", "on", "off", None, None),
    ], "live")
    now = t + 8 * 86400 + 60
    assert hm.armed_spans(memory._conn, now - 7 * 86400, now) == [(now - 7 * 86400, now)]
    log = hm.armed_log(memory._conn, now)
    assert log["armed_now"] is True and len(log["recent"]) == 1
