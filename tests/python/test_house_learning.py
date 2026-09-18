"""Phase 1: the nightly routine model.

  * activity is something happening (off to on), not a sensor stuck on - a
    camera holding "person" over a static shape all night is not a busy house;
  * the model learns a routine it is shown, predicts it better than a guess,
    and is scored on days it did not train on;
  * a candidate replaces the champion only when it is better on the same days;
  * what the routine did not expect is recorded silently, and a label of
    "normal" silences its like;
  * a run in the wrong time zone is refused rather than learned;
  * the Status tile and the digest read the result.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from src.python import house_learning as hl
from src.python import house_memory as hm
from src.python.web_app import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"
TZ = ZoneInfo("America/Vancouver")
MONDAY = datetime(2026, 8, 31, tzinfo=TZ)

ENTITIES = [
    {"entity_id": "binary_sensor.kitchen_occupancy", "attributes": {"device_class": "occupancy", "friendly_name": "Kitchen"}},
    {"entity_id": "binary_sensor.backyard_occupancy", "attributes": {"device_class": "occupancy", "friendly_name": "Motion sensor Backyard"}},
    {"entity_id": "binary_sensor.office_camera_npu_person", "attributes": {"friendly_name": "Office Camera (NPU) Person"}},
    {"entity_id": "binary_sensor.garage_camera_npu_person", "attributes": {"friendly_name": "Garage Camera (NPU) Person"}},
    {"entity_id": "binary_sensor.back_door", "attributes": {"device_class": "door", "friendly_name": "Back door"}},
    {"entity_id": "sensor.kitchen_temperature", "attributes": {"device_class": "temperature"}},
]


def _pulse(entity_id: str, at: datetime, seconds: int = 90) -> list[hm.Event]:
    return [hm.Event(at.timestamp(), entity_id, "on", "off", None, None),
            hm.Event(at.timestamp() + seconds, entity_id, "off", "on", None, None)]


def _house(tmp_path: Path, days: int, extra: list[hm.Event] = ()) -> Path:
    """A household that is up from 07:00 to 22:00 and asleep otherwise."""
    db = tmp_path / "events.db"
    memory = hm.HouseMemory(db)
    memory.upsert_entities(ENTITIES)
    events: list[hm.Event] = []
    for day in range(days):
        midnight = MONDAY + timedelta(days=day)
        if day == 0:
            # The kitchen is known to be off from the start, so the first day
            # is complete rather than unknown until its first event.
            events.append(hm.Event(midnight.timestamp() + 30, "binary_sensor.kitchen_occupancy",
                                   "off", "unavailable", None, None))
        # A heartbeat at 00:01 so the night is known (off), not missing.
        events += _pulse("binary_sensor.back_door", midnight.replace(hour=0, minute=1), 5)
        for hour in range(7, 23):
            events += _pulse("binary_sensor.kitchen_occupancy", midnight.replace(hour=hour, minute=10))
    memory.add_events(events + list(extra), "backfill")
    memory.close()
    return db


def test_signals_by_kind_and_place() -> None:
    rows = [{"entity_id": e["entity_id"], "name": e["attributes"].get("friendly_name"),
             "device_class": e["attributes"].get("device_class")} for e in ENTITIES]
    kinds = {s.entity_id.split(".")[1]: (s.kind, s.indoor) for s in hl.signals_from_entities(rows)}

    assert kinds == {
        "kitchen_occupancy": ("room", True),
        "backyard_occupancy": ("outdoor", False),
        "office_camera_npu_person": ("camera", True),
        "garage_camera_npu_person": ("camera", False),
        "back_door": ("door", False),
    }


def test_activity_is_a_rise_not_a_sensor_stuck_on() -> None:
    start = int(MONDAY.timestamp() // 3600)
    # On at 01:05 and held until 05:30: one event, then four quiet hours.
    rows = [(1, (MONDAY + timedelta(hours=1, minutes=5)).timestamp(), "on", "off"),
            (2, (MONDAY + timedelta(hours=5, minutes=30)).timestamp(), "off", "on"),
            (3, (MONDAY + timedelta(hours=7)).timestamp(), "unavailable", "off"),
            (4, (MONDAY + timedelta(hours=9, minutes=1)).timestamp(), "off", "unavailable")]

    cells = hl.hourly_cells(rows, start, start + 12)

    assert start not in cells, "before the first event nothing is known"
    assert cells[start + 1].active == 1 and cells[start + 1].first_event == 1
    assert [cells[start + h].active for h in (2, 3, 4, 5, 6)] == [0, 0, 0, 0, 0]
    assert start + 8 not in cells, "unavailable throughout is no data, not quiet"
    assert cells[start + 9].active == 0 and cells[start + 11].active == 0


def test_it_learns_the_routine_and_beats_a_guess(tmp_path: Path) -> None:
    db = _house(tmp_path, 14)
    now = (MONDAY + timedelta(days=14, hours=4)).timestamp()

    result = hl.run(db, "America/Vancouver", now=now, models_dir=tmp_path / "models")

    assert result["status"] == "warming_up" and result["days"] == 14
    assert result["metrics"]["house_accuracy"] == 1.0
    assert result["metrics"]["skill"] > 0.8
    routine = json.loads((tmp_path / "models" / "routine.json").read_text())["signals"]["house"]["p"]
    assert all(routine[d][3] < 0.1 for d in range(7)), "asleep at 03:00"
    assert all(routine[d][12] > 0.9 for d in range(7)), "up at noon"
    assert (tmp_path / "models" / "routine-2026-09-13.json").exists()


def test_too_little_data_is_collecting_not_a_model(tmp_path: Path) -> None:
    db = _house(tmp_path, 2)
    result = hl.run(db, "America/Vancouver", now=(MONDAY + timedelta(days=2, hours=4)).timestamp())
    assert result == {"status": "collecting", "days": 2}


def test_the_champion_stays_unless_beaten_by_a_margin(tmp_path: Path) -> None:
    db = _house(tmp_path, 12)
    conn = sqlite3.connect(db)
    frame = hl.load_frame(conn, TZ, (MONDAY + timedelta(days=12, hours=4)).timestamp())
    days = hl.complete_days(frame, (MONDAY + timedelta(days=12)).date())

    first = hl.choose(frame, days, None)
    assert first["promoted"] is True
    again = hl.choose(frame, days, first["config"])
    assert again["promoted"] is False and again["config"] == first["config"]

    # A champion that loses on these days by more than the margin is replaced.
    worst = max(hl.CONFIGS, key=lambda c: hl.score(frame, hl.fit(frame, hl.split(days)[0], c),
                                                    hl.split(days)[1]).get("brier", 0))
    challenged = hl.choose(frame, days, worst)
    if challenged["metrics"]["brier"] < hl.score(frame, hl.fit(frame, hl.split(days)[0], worst),
                                                 hl.split(days)[1])["brier"] * (1 - hl.PROMOTE_MARGIN):
        assert challenged["promoted"] is True


def test_the_unexpected_is_recorded_silently_and_a_label_silences_it(tmp_path: Path) -> None:
    three_am = MONDAY + timedelta(days=13, hours=3, minutes=20)
    db = _house(tmp_path, 14, extra=_pulse("binary_sensor.kitchen_occupancy", three_am))
    now = (MONDAY + timedelta(days=14, hours=4)).timestamp()

    hl.run(db, "America/Vancouver", now=now)
    conn = sqlite3.connect(db)
    alert = conn.execute("SELECT kind, entity_id, event_id, suppressed, detail FROM shadow_alerts").fetchall()
    assert len(alert) == 1
    kind, entity_id, event_id, suppressed, detail = alert[0]
    assert (kind, entity_id, suppressed) == ("unusual_time", "binary_sensor.kitchen_occupancy", 0)
    assert detail.startswith("03:00 · usually") and event_id

    # Running again does not record it twice.
    hl.run(db, "America/Vancouver", now=now + 60)
    assert conn.execute("SELECT COUNT(*) FROM shadow_alerts").fetchone()[0] == 1

    # You say it was normal: the next night's alerts of that kind at that hour are silenced.
    memory = hm.HouseMemory(db)
    memory.label(event_id, "normal")
    fine = hl.known_normal(conn, TZ)
    assert ("binary_sensor.kitchen_occupancy", 3) in fine and ("binary_sensor.kitchen_occupancy", 4) in fine


def test_a_room_gone_quiet_when_it_is_always_busy(tmp_path: Path) -> None:
    db = _house(tmp_path, 14)
    conn = sqlite3.connect(db)
    now = (MONDAY + timedelta(days=13, hours=16)).timestamp()
    # Day 13: the kitchen stops at 11:00 - the store knows it is off, but nothing happens.
    conn.execute("DELETE FROM events WHERE ts >= ? AND entity_id = 'binary_sensor.kitchen_occupancy'",
                 ((MONDAY + timedelta(days=13, hours=11)).timestamp(),))
    conn.commit()
    frame = hl.load_frame(conn, TZ, now)
    days = hl.complete_days(frame, (MONDAY + timedelta(days=13)).date())
    models = hl.fit(frame, days, hl.DEFAULT_CONFIG)

    alerts = hl.find_alerts(frame, models, int(now // 3600) - 8, int(now // 3600))
    quiet = [a for a in alerts if a.kind == "unusually_quiet"]
    assert len(quiet) == 1 and quiet[0].entity_id == "binary_sensor.kitchen_occupancy"
    assert quiet[0].detail.startswith("quiet 3 h from 11:00")


def test_summary_digest_and_endpoint(tmp_path: Path) -> None:
    db = _house(tmp_path, 14)
    now = (MONDAY + timedelta(days=14, hours=4)).timestamp()
    hl.run(db, "America/Vancouver", now=now)

    conn = sqlite3.connect(db)
    summary = hl.learning_summary(conn, now)
    assert summary["runs"] == 1 and summary["status"] == "warming_up"
    assert len(summary["routine"]) == 7 and len(summary["routine"][0]) == 24
    assert summary["history"][0]["skill"] > 0.8

    note = hl.digest_note(db)
    assert note.startswith("house learning, 14 days in (still warming up): predicts whether the house is active 100%")

    client = TestClient(create_app(discovery_path=tmp_path / "s.json", config_path=tmp_path / "d.yaml",
                                   check_camera_ports=False, memory_service=hm.SummaryCache(db)))
    learning = client.get("/api/memory/summary", params={"tz": "America/Vancouver"}).json()["learning"]
    assert learning["runs"] == 1 and learning["days"] == 14


def test_no_store_and_no_runs_are_quiet(tmp_path: Path) -> None:
    assert hl.digest_note(tmp_path / "missing.db") is None
    db = _house(tmp_path, 1)
    assert hl.learning_summary(sqlite3.connect(db)) == {"runs": 0}
    assert hl.digest_note(db) is None


def test_it_refuses_to_learn_without_the_house_time_zone(tmp_path: Path, monkeypatch, capsys) -> None:
    db = _house(tmp_path, 5)
    monkeypatch.delenv("HOUSE_TZ", raising=False)
    monkeypatch.delenv("HOME_ASSISTANT_TOKEN", raising=False)
    monkeypatch.setattr(hl, "house_time_zone", lambda base_url, token: None)
    monkeypatch.setattr("sys.argv", ["house_learning", "--db", str(db), "--models", str(tmp_path / "m")])
    monkeypatch.setattr("src.python.automation_author.load_dotenv", lambda path: None)

    assert hl.main() == 1
    assert "time zone" in capsys.readouterr().err
    assert hl.learning_summary(sqlite3.connect(db)) == {"runs": 0}


def test_the_nightly_units() -> None:
    unit_dir = PROJECT_ROOT / "deploy" / "systemd" / "user"
    service = (unit_dir / "house-learning.service").read_text(encoding="utf-8")
    timer = (unit_dir / "house-learning.timer").read_text(encoding="utf-8")
    installer = (PROJECT_ROOT / "scripts" / "install-dashboard-service.sh").read_text(encoding="utf-8")

    assert "ExecStart=/home/orangepi/smart_home_AI/.venv/bin/python -m src.python.house_learning" in service
    assert "Type=oneshot" in service
    # The board runs on UTC; 03:30 there is the middle of the evening here.
    assert "OnCalendar=*-*-* 03:30:00 America/Vancouver" in timer and "Persistent=true" in timer
    assert "enable --now house-learning.timer" in installer
    services = installer[installer.index("SERVICE_NAMES=("):installer.index(")", installer.index("SERVICE_NAMES=("))]
    assert "house-learning" not in services, "a deploy must not run the job"


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
globalThis.escapeHtml = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');
globalThis.statusName = (s) => s;
globalThis.learnAgo = () => '2 h ago';
for (const c of ['LEARN_WEEKDAYS', 'LEARN_LABELS', 'LEARN_ALERT_TEXT']) {
  eval(src.match(new RegExp(`const ${c} = [\\s\\S]*?;\\n`))[0].replace('const ', 'globalThis.'));
}
eval(pick('learnRoutineHtml') + pick('groupLearnAlerts') + pick('learnAlertsHtml'));
const routine = Array.from({ length: 7 }, () => Array.from({ length: 24 }, (_, h) => (h > 6 && h < 23 ? 0.95 : 0.02)));
const alerts = learnAlertsHtml({ alerts: [
  { id: 1, ts: 0, kind: 'unusual_time', name: '<Kitchen>', detail: 'active at 03:00', event_id: 9, label: null },
  { id: 2, ts: 0, kind: 'unusually_quiet', name: 'Hall', detail: 'quiet for 3 hours', event_id: null, label: null },
  { id: 3, ts: 5, kind: 'unusual_time', name: 'Door', detail: 'x', event_id: 4, label: 'normal' },
  { id: 4, ts: 0, kind: 'unusual_time', name: 'Upstairs', detail: 'x', event_id: 10, label: null },
  { id: 5, ts: 0, kind: 'unusual_time', name: 'Bedroom', detail: 'x', event_id: 11, label: null },
], alert_labels: { unusual: 1, normal: 3 } });
console.log(JSON.stringify({
  cells: (learnRoutineHtml(routine).match(/<i style=/g) || []).length,
  bad: learnRoutineHtml(null),
  buttons: (alerts.match(/data-learn-label=/g) || []).length,
  escaped: alerts.includes('&lt;Kitchen>'),
  precision: /25% worth it so far/.test(alerts),
  rows: (alerts.match(/<li /g) || []).length,
  merged: alerts.includes('&lt;Kitchen>, Upstairs +1'),
}));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_the_tile_draws_the_week_and_labels_only_what_can_be_labelled(tmp_path: Path) -> None:
    harness = tmp_path / "harness.js"
    harness.write_text(HARNESS, encoding="utf-8")
    out = subprocess.run(["node", str(harness), str(APP_JS)], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    result = json.loads(out.stdout)

    assert result["cells"] == 168
    assert "No routine yet" in result["bad"]
    assert result["buttons"] == 3, "one alert has an event to label; a quiet hour and a labelled one do not"
    assert result["escaped"] and result["precision"]
    assert result["rows"] == 3, "the three sensors of one moment are one row"
    assert result["merged"]
