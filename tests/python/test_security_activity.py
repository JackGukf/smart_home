"""Recent activity (Security view) and Today at a glance (Status view).

  * a sensor firing again within ten minutes is one line, "4 times since";
  * only rises count - off to on - and only the kinds security cares about;
  * "today" is since the viewer's midnight, not the board's UTC one;
  * a line knows its room, so tapping it selects that room on the picture;
  * SOS asks before it sounds, now that it is one small button in a row.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from src.python import house_memory as hm
from src.python.web_app import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"
TZ = ZoneInfo("America/Vancouver")
NOW = datetime(2026, 9, 18, 10, 3, tzinfo=TZ)


def _at(hours_ago: float) -> float:
    return (NOW - timedelta(hours=hours_ago)).timestamp()


def _store(tmp_path: Path) -> hm.HouseMemory:
    memory = hm.HouseMemory(tmp_path / "events.db")
    memory.upsert_entities([
        {"entity_id": "binary_sensor.front_door", "attributes": {"device_class": "door", "friendly_name": "Door sensor front door"}},
        {"entity_id": "binary_sensor.entry", "attributes": {"device_class": "occupancy", "friendly_name": "Motion sensor and TH Entry Occupancy"}},
        {"entity_id": "binary_sensor.office_camera_npu_person", "attributes": {"device_class": "occupancy", "friendly_name": "Office Camera (NPU) Person"}},
        {"entity_id": "binary_sensor.panel_microphone", "attributes": {"friendly_name": "Voice Panel Microphone capturing"}},
    ])
    rise = lambda entity, hours_ago: hm.Event(_at(hours_ago), entity, "on", "off", None, None)
    memory.add_events([
        rise("binary_sensor.office_camera_npu_person", 0.02),
        rise("binary_sensor.office_camera_npu_person", 0.06),
        rise("binary_sensor.office_camera_npu_person", 0.10),   # three within ten minutes of each other
        rise("binary_sensor.office_camera_npu_person", 0.50),   # a separate moment
        rise("binary_sensor.front_door", 1.0),
        hm.Event(_at(0.9), "binary_sensor.front_door", "off", "on", None, None),  # closing is not an event
        rise("binary_sensor.entry", 9.9),                        # 00:09 today
        rise("binary_sensor.entry", 10.2),                       # 23:51 yesterday: recent, not today
        rise("binary_sensor.panel_microphone", 0.3),             # not security
    ], "live")
    return memory


def test_bursts_fold_and_only_security_rises_count(tmp_path: Path) -> None:
    memory = _store(tmp_path)
    result = hm.security_activity(memory._conn, "America/Vancouver", NOW.timestamp())

    lines = [(line["entity_id"].split(".")[1], line["kind"], line["count"]) for line in result["recent"]]
    assert lines == [
        ("office_camera_npu_person", "camera", 3),
        ("office_camera_npu_person", "camera", 1),
        ("front_door", "door", 1),
        ("entry", "motion", 1),
        ("entry", "motion", 1),
    ]
    assert result["recent"][0]["first_ts"] == pytest.approx(_at(0.10))


def test_today_is_the_viewers_day(tmp_path: Path) -> None:
    memory = _store(tmp_path)
    today = hm.security_activity(memory._conn, "America/Vancouver", NOW.timestamp())["today"]

    assert (today["people"], today["doors"], today["motion"]) == (4, 1, 1), "yesterday's 23:51 is not today"
    assert today["hour_now"] == 10
    assert today["hours"][0] == 1 and today["hours"][9] == 4 and today["hours"][10] == 1
    assert sum(today["hours"]) == 6


def test_the_endpoint_is_cached_and_sanitised(tmp_path: Path) -> None:
    _store(tmp_path).close()
    cache = hm.SummaryCache(tmp_path / "events.db", clock=lambda: NOW.timestamp())
    client = TestClient(create_app(discovery_path=tmp_path / "s.json", config_path=tmp_path / "d.yaml",
                                   check_camera_ports=False, memory_service=cache))

    body = client.get("/api/memory/security", params={"tz": "America/Vancouver"}).json()
    assert body["available"] is True and body["today"]["people"] == 4
    assert client.get("/api/memory/security", params={"tz": "../../x"}).json()["time_zone"] == "UTC"
    assert hm.SummaryCache(tmp_path / "missing.db").security("UTC") == {"available": False}


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
globalThis.shortZoneName = (n) => n.replace(/\s*\(NPU\)\s*Person$/, '');
globalThis.zoneRoom = (z) => (/office/i.test(z.name) ? 'Office' : null);
eval(src.match(/const ACTIVITY_WORDS = [^;]+;/)[0].replace('const ', 'globalThis.'));
eval(pick('activityTime') + pick('houseActivityHtml') + pick('statusTodayHtml') + pick('shortControlName'));
const t = (h, m) => new Date(2026, 8, 18, h, m).getTime() / 1000;
const data = { available: true,
  recent: [{ entity_id: 'binary_sensor.office_camera_npu_person', name: 'Office Camera (NPU) Person', kind: 'camera', ts: t(10, 2), first_ts: t(9, 56), count: 4 },
           { entity_id: 'binary_sensor.front_door', name: 'Door <front>', kind: 'door', ts: t(9, 4), first_ts: t(9, 4), count: 1 }],
  today: { doors: 3, people: 71, motion: 130, other: 4, hours: [14, 16, 0, 4, 0, 0, 6, 11, 80, 73, 4].concat(Array(13).fill(0)), hour_now: 10 } };
const card = houseActivityHtml(data);
const today = statusTodayHtml(data);
console.log(JSON.stringify({
  burst: card.includes('Office Camera<small> · person, 4 times since 09:56</small>'),
  room: card.includes('data-house-room="Office"'),
  noRoom: (card.match(/data-house-room=/g) || []).length === 1,
  escaped: card.includes('Door &lt;front>') && card.includes('opened'),
  total: card.includes('208 today'),
  missing: houseActivityHtml({ available: false }).includes('not running'),
  stats: today.includes('>3</b><span>doors opened') && today.includes('>71</b><span>people seen'),
  now: (today.match(/class="now"/g) || []).length === 1 && (today.match(/class="later"/g) || []).length === 13,
  control: shortControlName('Alarm system Arm beep'),
}));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_the_cards(tmp_path: Path) -> None:
    harness = tmp_path / "harness.js"
    harness.write_text(HARNESS, encoding="utf-8")
    out = subprocess.run(["node", str(harness), str(APP_JS)], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    result = json.loads(out.stdout)
    assert result.pop("control") == "Arm beep"
    assert result == {k: True for k in ("burst", "room", "noRoom", "escaped", "total", "missing", "stats", "now")}


def test_sos_asks_first() -> None:
    js = APP_JS.read_text(encoding="utf-8")
    handler = js[js.index('if (event.target.closest("#sosTriggerBtn")) {'):]
    handler = handler[:handler.index("return;\n  }") ]
    assert handler.index("window.confirm(") < handler.index("triggerSOS()")
