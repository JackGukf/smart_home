"""The Motion group.

Motion is a *reading filter* over the sensor groups, not a device kind. Five of
the seven motion sensors on this board are combined "Motion sensor and TH" units
that also report temperature, humidity and illuminance, so classifying the
device as motion — the way Bridges classifies a gateway — would pull those
readings out of Environment. The test that matters most here is the one
asserting that does not happen.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"
INDEX_HTML = PROJECT_ROOT / "src" / "python" / "web_static" / "index.html"

HARNESS_PRELUDE = """
const src = require('fs').readFileSync(process.argv[2], 'utf8');
const pick = (name) => {
  const at = src.indexOf(`function ${name}`);
  if (at < 0) throw new Error(`missing function ${name}`);
  let depth = 0, i = src.indexOf('{', at);
  for (; i < src.length; i++) {
    if (src[i] === '{') depth++;
    else if (src[i] === '}') { depth--; if (depth === 0) return src.slice(at, i + 1); }
  }
  throw new Error(`unbalanced ${name}`);
};
const constOf = (name) => {
  const m = src.match(new RegExp(`const ${name}[\\\\s\\\\S]*?;`));
  if (!m) throw new Error(`missing const ${name}`);
  return m[0];
};
"""

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def _run_node(script: str, tmp_path: Path) -> dict:
    harness = tmp_path / "harness.js"
    harness.write_text(HARNESS_PRELUDE + script, encoding="utf-8")
    out = subprocess.run(["node", str(harness), str(APP_JS)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


# One real device from the board: a Zigbee unit reporting occupancy *and*
# temperature, humidity, illuminance and battery on the same physical sensor.
COMBINED = """[
  { id: 'r1', name: 'Motion sensor and TH bedroom Occupancy', device_class: 'occupancy', state: 'off' },
  { id: 'r2', name: 'Motion sensor and TH bedroom Temperature', device_class: 'temperature', state: '21.4' },
  { id: 'r3', name: 'Motion sensor and TH bedroom Humidity', device_class: 'humidity', state: '48' },
  { id: 'r4', name: 'Motion sensor and TH bedroom Illuminance', device_class: 'illuminance', state: '120' },
  { id: 'r5', name: 'Motion sensor and TH bedroom Battery', device_class: 'battery', state: '100' }
]"""

FILTER_JS = """
globalThis.expandSensorReadings = (r) => r;
eval(constOf('ENVIRONMENT_CAPABILITIES') + constOf('KNOWN_SENSOR_CAPABILITIES')
   + pick('sensorCapabilityKey') + pick('filterReadingsForView') + pick('groupHasViewContent'));
"""


def test_a_combined_sensor_keeps_its_temperature_in_environment(tmp_path: Path) -> None:
    """The reason Motion is a reading filter rather than a device kind.

    The same physical sensor appears in both groups, showing what each group is
    about. A device-kind approach would move it wholly into Motion and leave
    Environment a temperature short.
    """
    result = _run_node(f"""
{FILTER_JS}
const readings = {COMBINED};
const keys = (mode) => filterReadingsForView(readings, mode).map(sensorCapabilityKey);
console.log(JSON.stringify({{
  motion: keys('motion'),
  environment: keys('environment'),
  sensors: keys('sensors'),
}}));
""", tmp_path)

    # Motion shows the occupancy reading, and battery, which every view carries.
    assert result["motion"] == ["motion", "battery"]
    # Environment is untouched by Motion existing.
    assert "temperature" in result["environment"]
    assert "humidity" in result["environment"]
    # And the motion reading still appears in Sensors -- Motion narrows, it does
    # not carve the reading out.
    assert "motion" in result["sensors"]


def test_a_sensor_with_no_motion_reading_stays_out_of_the_group(tmp_path: Path) -> None:
    """Sensors is the catch-all and takes anything unclassifiable; Motion must
    not, or every thermometer in the house appears here showing a battery."""
    result = _run_node(f"""
{FILTER_JS}
const thermometer = {{ readings: [
  {{ id: 't1', name: 'Fridge Temperature', device_class: 'temperature', state: '4.1' }},
  {{ id: 't2', name: 'Fridge Battery', device_class: 'battery', state: '80' }}
] }};
const motionSensor = {{ readings: {COMBINED} }};
console.log(JSON.stringify({{
  thermometerInMotion: groupHasViewContent(thermometer, 'motion'),
  sensorInMotion: groupHasViewContent(motionSensor, 'motion'),
  thermometerInEnvironment: groupHasViewContent(thermometer, 'environment'),
}}));
""", tmp_path)

    assert result["thermometerInMotion"] is False
    assert result["sensorInMotion"] is True
    assert result["thermometerInEnvironment"] is True


def test_occupancy_motion_and_moving_all_count_as_motion(tmp_path: Path) -> None:
    """Your sensors disagree about which device_class to use -- the Zigbee units
    report `occupancy`, the two Tuya ones report both `motion` and `occupancy`.
    Folding them into one capability is what lets a sensor added later be picked
    up with no configuration."""
    result = _run_node("""
""" + FILTER_JS + """
const classes = ['occupancy', 'motion', 'moving'];
console.log(JSON.stringify(classes.map((dc) =>
  sensorCapabilityKey({ id: dc, name: dc, device_class: dc, state: 'off' }))));
""", tmp_path)

    assert result == ["motion", "motion", "motion"]


def test_motion_is_seeded_as_a_reading_filter_not_a_device_kind() -> None:
    from src.python.web_app import (
        DEFAULT_DEVICE_GROUPS,
        DEVICE_GROUP_KINDS,
        DEVICE_GROUP_READING_FILTERS,
    )

    motion = next(g for g in DEFAULT_DEVICE_GROUPS if g["id"] == "motion")

    assert motion["readingFilter"] == "motion"
    assert "motion" in DEVICE_GROUP_READING_FILTERS
    # No new device kind: it selects the same sensor devices the other reading
    # filters do, so nothing needed reclassifying and there is nothing to migrate.
    assert motion["kinds"] == ["sensor"]
    assert "motion" not in DEVICE_GROUP_KINDS
    # Builtin because it needs the sensor-card renderer; the generic
    # dynamic-group panel renders devices and knows nothing about reading filters.
    assert motion["builtin"] is True


def test_the_motion_panel_exists_and_the_view_is_registered() -> None:
    """A seeded group with no panel navigates to a blank screen."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    app = APP_JS.read_text(encoding="utf-8")

    assert 'data-view-panel="motion"' in html
    assert 'id="motionGrid"' in html
    assert '"motion"' in app.split("const BUILTIN_TILE_VIEWS")[1].split(";")[0]
    assert '"motion"' in app.split("let DEVICE_GROUP_VIEWS")[1].split(";")[0]


# ─────────────────────────── the motion log ───────────────────────────

def _change(entity_id: str, old: str, new: str, device_class: str = "occupancy",
            name: str = "Hall motion") -> dict:
    return {
        "entity_id": entity_id,
        "old_state": {"state": old},
        "new_state": {"state": new, "attributes": {"device_class": device_class,
                                                   "friendly_name": name}},
    }


def test_only_real_transitions_are_logged() -> None:
    """Home Assistant re-emits state_changed whenever an attribute moves.

    These sensors report battery and illuminance on the same entity, so logging
    every event would bury the handful that matter under hundreds saying nothing
    happened.
    """
    from src.python.web_app import motion_event_from_state_change

    last_on: dict[str, float] = {}
    seen = motion_event_from_state_change(_change("binary_sensor.hall", "off", "on"), last_on)
    assert seen is not None and seen["state"] == "on"

    # Same state, new attributes: not a transition.
    assert motion_event_from_state_change(_change("binary_sensor.hall", "on", "on"), last_on) is None
    # Not a motion sensor.
    assert motion_event_from_state_change(
        _change("binary_sensor.door", "off", "on", device_class="door"), last_on) is None
    # Not a binary_sensor at all.
    assert motion_event_from_state_change(
        _change("sensor.hall_temp", "20", "21", device_class="occupancy"), last_on) is None
    # unavailable is not a detection.
    assert motion_event_from_state_change(
        _change("binary_sensor.hall", "on", "unavailable"), last_on) is None


def test_clearing_records_how_long_motion_lasted() -> None:
    """"Cleared" on its own loses the part worth knowing."""
    from src.python.web_app import motion_event_from_state_change

    last_on: dict[str, float] = {}
    started = motion_event_from_state_change(_change("binary_sensor.hall", "off", "on"), last_on)
    assert "duration_s" not in started

    ended = motion_event_from_state_change(_change("binary_sensor.hall", "on", "off"), last_on)
    assert ended["state"] == "off"
    assert ended["duration_s"] >= 0
    # The pending start is consumed, so a second clear cannot invent a duration
    # from a detection that was already closed.
    again = motion_event_from_state_change(_change("binary_sensor.hall", "on", "off"), last_on)
    assert "duration_s" not in again


def test_the_log_reads_newest_first_and_survives_a_torn_line(tmp_path: Path) -> None:
    """A hard kill mid-append leaves a partial final line. One unreadable entry
    must not cost the whole log."""
    from src.python.web_app import read_motion_log

    log = tmp_path / "motion_log.jsonl"
    log.write_text(
        '{"ts": 1, "entity_id": "a", "state": "on"}\n'
        '{"ts": 2, "entity_id": "b", "state": "on"}\n'
        '{"ts": 3, "entity_id": "c", "sta\n',
        encoding="utf-8")

    events = read_motion_log(log, limit=10)
    assert [e["entity_id"] for e in events] == ["b", "a"]

    assert read_motion_log(tmp_path / "absent.jsonl") == []


def test_old_entries_are_pruned_and_recent_ones_kept() -> None:
    from src.python.web_app import MOTION_LOG_MAX_DAYS, _motion_log_prune

    now = 1_000_000.0
    old = now - (MOTION_LOG_MAX_DAYS + 1) * 86400
    lines = [
        '{"ts": %f, "entity_id": "ancient"}' % old,
        '{"ts": %f, "entity_id": "recent"}' % (now - 3600),
        "not json at all",
    ]
    kept = _motion_log_prune(lines, now)
    assert len(kept) == 1
    assert "recent" in kept[0]


def test_the_recorder_does_not_ride_the_browser_event_stream() -> None:
    """A log that only records while someone has the page open is not a log.

    /api/events/stream is per-connection and coalesces bursts at 0.4s, which is
    right for waking a page and wrong for recording history, so the recorder
    holds its own subscription.
    """
    source = (PROJECT_ROOT / "src" / "python" / "web_app.py").read_text(encoding="utf-8")
    recorder = source.split("async def _motion_log_recorder")[1].split("\ndef ")[0]

    assert "subscribe_events" in recorder, "the recorder has no subscription of its own"
    assert "_home_assistant_event_stream" not in recorder
    # It must outlive any single failure, or one Home Assistant restart ends the log.
    assert "while True" in recorder
    assert "backoff" in recorder


def test_the_orphan_tool_disables_rather_than_deletes_and_spares_live_devices() -> None:
    """Moving sensors between radios leaves the old integration's entries behind.

    Two properties make this safe to point at a live house: it refuses any
    device that still reports, judging on state rather than on how dead the name
    looks; and it disables rather than deletes, which is both the only thing
    Home Assistant 2026.6 offers over the WebSocket API and the reversible
    option. A disabled device's entities leave the state machine, so they
    disappear from /api/states and everything built on it.
    """
    source = (PROJECT_ROOT / "scripts" / "disable-orphan-ha-devices.py").read_text(encoding="utf-8")

    assert 'DEAD_STATES = {None, "unavailable", "unknown"}' in source
    assert "REFUSING" in source, "no guard against disabling a device that still reports"
    assert '"disabled_by": "user"' in source
    # Deleting a registry entry takes its history with it and cannot be undone
    # from the UI.
    assert "remove_config_entry_from_device" not in source.split('"""')[2]
    # Nothing changes without an explicit flag and an explicit device name.
    assert "--apply" in source
    assert 'ap.error("give device names, or --list to see the candidates")' in source
