"""The Status view: a board of small charts from four logs.

  * the resource logger's own file becomes hourly memory/temperature/load, and
    a line it cannot parse is skipped rather than fatal;
  * an event is a rise from "off": the state the window opened in, and a
    sensor coming back from "unavailable", are not something happening;
  * services are asked about by name from a fixed list, in the scope each one
    lives in - a system unit asked about as a user unit reads "not-found";
  * phone batteries are not house batteries;
  * the view draws gaps where there were no samples, rather than a line
    pretending to know.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.python import status_overview as so
from src.python.web_app import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"
INDEX_HTML = PROJECT_ROOT / "src" / "python" / "web_static" / "index.html"

START = datetime(2026, 9, 17, 3, 0, tzinfo=timezone.utc)
NOW = START + timedelta(hours=24)


def _iso(hours: float) -> str:
    return (START + timedelta(hours=hours)).isoformat()


def test_the_resource_log_becomes_hourly_averages(tmp_path: Path) -> None:
    log = tmp_path / "resource-history.log"
    log.write_text("\n".join([
        f"{(START - timedelta(hours=1)).isoformat()} mem_used=9999M avail=1M load=9.00/9.00 temp=99C",
        f"{START.isoformat()} BOOT uptime=11",
        f"{_iso(0.1)} mem_used=8000M avail=7000M load=3.00/3.10 temp=40C python=1093M",
        f"{_iso(0.6)} mem_used=8200M avail=6800M load=4.00/3.50 temp=42C",
        "garbage that is not a sample",
        f"{_iso(23.5)} mem_used=8500M avail=6500M load=2.00/2.00 temp=45C",
    ]) + "\n", encoding="utf-8")

    board = so.read_resource_history(log, START, NOW)

    assert board["mem"][0] == 8100 and board["temp"][0] == 41 and board["load"][0] == 3.5
    assert board["mem"][23] == 8500
    assert board["mem"][1:23] == [None] * 22, "an hour without samples is a gap, not a zero"
    assert 9999 not in board["mem"], "samples before the window are not in it"
    assert board["boot"] == START.isoformat()


def test_a_missing_log_is_reported_not_raised(tmp_path: Path) -> None:
    assert so.read_resource_history(tmp_path / "nope.log", START, NOW)["status"] == "missing"


def test_events_are_rises_from_off_and_minutes_are_spread_across_hours() -> None:
    meta = {"binary_sensor.kitchen": {"name": "Kitchen", "kind": "motion"}}
    history = [[
        {"entity_id": "binary_sensor.kitchen", "state": "on", "last_changed": _iso(0)},  # window opened on
        {"state": "off", "last_changed": _iso(0.25)},
        {"state": "on", "last_changed": _iso(1.5)},                                    # 1 event, hour 1
        {"state": "off", "last_changed": _iso(2.25)},                                  # 30 + 15 minutes
        {"state": "unavailable", "last_changed": _iso(5)},
        {"state": "on", "last_changed": _iso(5.5)},                                    # after a restart: not an event
        {"state": "off", "last_changed": _iso(5.6)},
        {"state": "on", "last_changed": _iso(23.5)},                                   # still on at the end
    ]]

    [kitchen] = so.hourly_activity(history, START, NOW, meta)

    assert kitchen["counts"][0] == 0
    assert kitchen["counts"][1] == 1 and kitchen["counts"][5] == 0 and kitchen["counts"][23] == 1
    assert kitchen["total"] == 2
    assert kitchen["minutes"][0] == 15 and kitchen["minutes"][1] == 30 and kitchen["minutes"][2] == 15
    assert kitchen["minutes"][23] == 30, "an on-period still open at the end runs to now"


def test_which_binary_sensors_count_as_activity() -> None:
    states = [
        {"entity_id": "binary_sensor.garage_camera_npu_person", "attributes": {"friendly_name": "Garage Camera (NPU) Person"}},
        {"entity_id": "binary_sensor.entry_occupancy", "attributes": {"device_class": "occupancy"}},
        {"entity_id": "binary_sensor.back_door", "attributes": {"device_class": "door"}},
        {"entity_id": "binary_sensor.leak", "attributes": {"device_class": "moisture"}},
        {"entity_id": "binary_sensor.update_available", "attributes": {"device_class": "update"}},
        {"entity_id": "sensor.kitchen_motion", "attributes": {"device_class": "motion"}},
    ]
    kinds = {s["entity_id"]: s["kind"] for s in so.activity_sensors(states)}

    assert kinds == {
        "binary_sensor.garage_camera_npu_person": "camera",
        "binary_sensor.entry_occupancy": "motion",
        "binary_sensor.back_door": "door",
        "binary_sensor.leak": "safety",
    }


def test_batteries_lowest_first_without_phones() -> None:
    states = [
        {"entity_id": "sensor.leak_battery", "state": "26", "attributes": {"device_class": "battery", "friendly_name": "Leak Battery"}},
        {"entity_id": "sensor.iphone_15_battery_level", "state": "3", "attributes": {"device_class": "battery"}},
        {"entity_id": "sensor.door_battery", "state": "100", "attributes": {"device_class": "battery", "friendly_name": "Door Battery"}},
        {"entity_id": "sensor.smoke_battery", "state": "unavailable", "attributes": {"device_class": "battery"}},
    ]
    assert so.batteries(states) == [{"name": "Leak", "percent": 26}, {"name": "Door", "percent": 100}]


def test_services_are_asked_in_their_own_scope_and_only_from_the_list() -> None:
    asked: list[list[str]] = []

    def runner(command: list[str]) -> str:
        asked.append(command)
        if command[:2] == ["docker", "ps"]:
            return "homeassistant\nmosquitto\nzigbee2mqtt\n" + ("wyoming-piper\n" if "-a" in command else "")
        return "inactive" if command[-1] == "ollama.service" else "active"

    services = {s["unit"]: s for s in so.service_states(runner)}

    assert ["systemctl", "is-active", "matter-server.service"] in asked, "a system unit, asked as one"
    assert ["systemctl", "--user", "is-active", "go2rtc.service"] in asked
    assert services["ollama.service"]["ok"] is False
    assert services["homeassistant"]["ok"] is True
    assert services["wyoming-piper"]["state"] == "stopped"
    assert services["wyoming-whisper"]["state"] == "unknown"
    allowed = {unit for unit, _, _ in so.SERVICE_UNITS}
    assert all(c[-1] in allowed for c in asked if c[0] == "systemctl")


def test_the_overview_is_cached_and_degrades_without_home_assistant(tmp_path: Path) -> None:
    clock = [NOW.timestamp()]
    calls: list[str] = []

    def fetch(url: str, headers: dict[str, str]):
        calls.append(url)
        raise OSError("refused")

    service = so.StatusOverview("http://ha", lambda: "token", resource_log=tmp_path / "log",
                                fetch=fetch, runner=lambda command: "", clock=lambda: clock[0])
    first = service.overview()
    assert first["status"] == "home_assistant_unavailable"
    assert first["services"], "the board's own checks still answer"
    assert len(first["hours"]) == 24

    clock[0] += 60
    assert service.overview() is first and len(calls) == 1
    clock[0] += so.CACHE_SECONDS
    service.overview()
    assert len(calls) == 2


def test_history_failure_preserves_local_status_and_ha_batteries(tmp_path: Path) -> None:
    states = [
        {"entity_id": "binary_sensor.entry", "state": "off", "attributes": {"device_class": "door"}},
        {"entity_id": "sensor.leak_battery", "state": "26", "attributes": {"device_class": "battery"}},
    ]

    def fetch(url: str, headers: dict[str, str]):
        if "/api/states" in url:
            return states
        raise ValueError("invalid history response")

    service = so.StatusOverview("http://ha", lambda: "token", resource_log=tmp_path / "log",
                                fetch=fetch, runner=lambda command: "", clock=lambda: NOW.timestamp())
    result = service.overview()
    assert result["status"] == "home_assistant_history_unavailable"
    assert result["batteries"][0]["percent"] == 26
    assert result["services"] and len(result["hours"]) == 24


def test_malformed_ha_states_do_not_crash_status(tmp_path: Path) -> None:
    service = so.StatusOverview("http://ha", lambda: "token", resource_log=tmp_path / "log",
                                fetch=lambda url, headers: {"error": "offline"},
                                runner=lambda command: "", clock=lambda: NOW.timestamp())
    result = service.overview()
    assert result["status"] == "home_assistant_unavailable"
    assert result["services"] and result["board"]["status"] == "missing"


def test_the_endpoint_serves_the_overview(tmp_path: Path) -> None:
    class Fake:
        def overview(self):
            return {"status": "ok", "activity": []}

    client = TestClient(create_app(
        discovery_path=tmp_path / "switches.json",
        config_path=tmp_path / "devices.yaml",
        check_camera_ports=False,
        status_service=Fake(),
    ))
    assert client.get("/api/status/overview").json() == {"status": "ok", "activity": []}


def test_the_view_has_the_small_charts_and_keeps_the_digest_and_network_card() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    status = html[html.index('data-view-panel="status"'):html.index('data-view-panel="lights"')]

    for chart in ("statusActivity", "statusBusiest", "statusCameras", "statusMemory",
                  "statusTemp", "statusBatteries", "statusServices"):
        assert f'id="{chart}"' in status
    assert 'id="digestCard"' in status and 'id="openNetworkModal"' in status


HARNESS = r"""
const src = require('fs').readFileSync(process.argv[2], 'utf8');
const pick = (name) => {
  const at = src.indexOf(`function ${name}(`);
  if (at < 0) throw new Error(`missing function ${name}`);
  let depth = 0, i = src.indexOf('{', at);
  for (; i < src.length; i++) {
    if (src[i] === '{') depth++;
    else if (src[i] === '}') { depth--; if (depth === 0) return src.slice(at, i + 1); }
  }
  throw new Error(`unbalanced ${name}`);
};
globalThis.escapeHtml = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');
eval(src.match(/const ZONE_NAME_TRANSLATIONS = [^;]+;/)[0].replace('const ', 'globalThis.'));
eval(pick('shortZoneName') + pick('statusName') + pick('statusUptime') + pick('statusHourLabel')
  + pick('statusSparklineSvg') + pick('statusBarsHtml') + pick('statusColumnsSvg'));
const hours = Array.from({ length: 24 }, (_, h) => new Date(Date.UTC(2026, 8, 17, 3 + h)).toISOString());
const spark = statusSparklineSvg([40, 41, null, null, 42, 43], 'camera', '°C');
console.log(JSON.stringify({
  names: ['水浸传感器', 'Garage Camera (NPU) Person', 'Motion sensor and TH Entry Occupancy'].map(statusName),
  zone: shortZoneName('水浸传感器 Moisture'),
  uptime: [statusUptime('2026-09-13T03:40:00Z', Date.parse('2026-09-17T23:10:00Z')), statusUptime('2026-09-17T20:00:00Z', Date.parse('2026-09-17T23:10:00Z')), statusUptime('nonsense')],
  lines: (spark.match(/class="st-line/g) || []).length,
  sparkNow: /now 43°C/.test(spark),
  emptySpark: statusSparklineSvg([null, null], 'motion'),
  bars: statusBarsHtml([{ name: '<b>', value: 5, kind: 'camera' }], 10),
  emptyBars: statusBarsHtml([], 1),
  columns: (statusColumnsSvg(hours.map((_, i) => i), hours).match(/<rect/g) || []).length,
}));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_the_charts_draw_gaps_names_and_escape(tmp_path: Path) -> None:
    harness = tmp_path / "harness.js"
    harness.write_text(HARNESS, encoding="utf-8")
    out = subprocess.run(["node", str(harness), str(APP_JS)], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    result = json.loads(out.stdout)

    assert result["names"] == ["Water sensor", "Garage", "Entry"]
    assert result["zone"] == "Water sensor", "the Security and Home cards translate the name too"
    assert result["uptime"] == ["4 d 19 h", "3 h", None]
    assert result["lines"] == 2, "missing hours split the line in two"
    assert result["sparkNow"]
    assert "No samples" in result["emptySpark"]
    assert "&lt;b>" in result["bars"] and "<b>" not in result["bars"].replace("<b class", "")
    assert 'width:50.0%' in result["bars"]
    assert "Nothing in the last 24 hours" in result["emptyBars"]
    assert result["columns"] == 24
