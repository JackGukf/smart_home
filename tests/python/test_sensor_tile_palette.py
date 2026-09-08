"""The Sensors grid is allowed two colours, and no more.

Every sensor type used to carry its own hue - orange, cyan, amber, purple,
indigo, teal, red, slate, green across fourteen types - so a wall of tiles read
as a colour chart and nothing stood out because everything did. The type is
carried by the icon and the label, which say it exactly; colour is spent only
on urgency.

This renders a grid of real sensor shapes and counts what actually reaches the
DOM, because a rule about colour cannot be checked by grepping for one.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"

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
  const m = src.match(new RegExp(`const ${name}[\\\\s\\\\S]*?^};`, 'm'));
  if (!m) throw new Error(`missing const ${name}`);
  return m[0];
};
"""

# One of everything this house actually reports, so the grid under test is the
# grid on the wall: temperature, humidity, illuminance, occupancy, door,
# moisture, smoke, tamper and battery.
DEVICES = """
const groups = [
  { name: 'Kitchen Multi', readings: [
      { id: 'a1', name: 'Kitchen Multi Temperature', category: 'tuya_temperature',
        device_class: 'temperature', state: '21.4', online: true },
      { id: 'a2', name: 'Kitchen Multi Humidity', category: 'tuya_humidity',
        device_class: 'humidity', state: '48', online: true },
      { id: 'a3', name: 'Kitchen Multi Occupancy', category: 'tuya_occupancy',
        device_class: 'occupancy', state: 'off', online: true },
      { id: 'a4', name: 'Kitchen Multi Battery', category: 'tuya_battery',
        device_class: 'battery', state: '95', online: true } ] },
  { name: 'Front Door', readings: [
      { id: 'b1', name: 'Front Door Contact', category: 'tuya_door',
        device_class: 'door', state: 'off', online: true },
      { id: 'b2', name: 'Front Door Battery', category: 'tuya_battery',
        device_class: 'battery', state: '12', online: true } ] },
  { name: 'Landing Light Level', readings: [
      { id: 'c1', name: 'Landing Illuminance', category: 'tuya_illuminance',
        device_class: 'illuminance', state: '120', online: true } ] },
  { name: 'Water Sensor', readings: [
      { id: 'd1', name: 'Water Sensor Moisture', category: 'tuya_moisture',
        device_class: 'moisture', state: 'off', online: true } ] },
  { name: 'Fire Alarm', readings: [
      { id: 'e1', name: 'Fire Alarm Smoke', category: 'tuya_smoke',
        device_class: 'smoke', state: 'off', online: true } ] },
  { name: 'Shed Tamper', readings: [
      { id: 'f1', name: 'Shed Tamper', category: 'tuya_tamper',
        device_class: 'tamper', state: 'off', online: true } ] },
];
"""

RENDER = """
globalThis.escapeHtml = (v) => String(v ?? '');
globalThis.primaryTuyaState = (d) => String(d.state ?? '');
globalThis.filterReadingsForView = (readings) => readings;
globalThis.expandSensorReadings = (readings) => readings;
globalThis.countUniqueSensorCapabilities = (readings) => readings.length;
globalThis.sensorDeviceSubtitle = () => 'sensor';
globalThis.readingMetricNumber = (d) => Number(d.state);
eval(constOf('SENSOR_TYPE_META') + pick('sensorTypeMeta') + pick('sensorTileHue')
   + pick('batteryMeta') + pick('sensorTileIcon') + pick('sensorTileFacet')
   + pick('isAlertDetected') + pick('isSensorIncident')
   + pick('renderSensorDeviceCard'));
"""


def _run_node(script: str, tmp_path: Path) -> dict:
    harness = tmp_path / "harness.js"
    harness.write_text(HARNESS_PRELUDE + script, encoding="utf-8")
    out = subprocess.run(
        ["node", str(harness), str(APP_JS)], capture_output=True, text=True, check=True
    )
    return json.loads(out.stdout)


pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def _colours(html: str) -> set[str]:
    """Every colour the markup asks for, however it was spelled."""
    found = set(re.findall(r"--tint:\s*([^;\"]+)", html))
    found |= set(re.findall(r"color:\s*([^;\"]+)", html))
    return {c.strip() for c in found if c.strip()}


def test_a_calm_sensor_grid_uses_exactly_one_colour(tmp_path: Path) -> None:
    script = RENDER + DEVICES + """
console.log(JSON.stringify({
  html: groups.map((g) => renderSensorDeviceCard(g, 'sensors')).join('')
}));
"""
    html = _run_node(script, tmp_path)["html"]

    # Nothing is tripped, so nothing is red - but the low battery on the front
    # door is exactly the case colour is reserved for.
    assert _colours(html) <= {"var(--t-accent)", "var(--red)"}


def test_a_tripped_sensor_is_the_only_thing_that_turns_red(tmp_path: Path) -> None:
    script = RENDER + DEVICES + """
const tripped = JSON.parse(JSON.stringify(groups));
tripped.find((g) => g.name === 'Water Sensor').readings[0].state = 'on';
console.log(JSON.stringify({
  calm: renderSensorDeviceCard(groups.find((g) => g.name === 'Water Sensor'), 'sensors'),
  alert: renderSensorDeviceCard(tripped.find((g) => g.name === 'Water Sensor'), 'sensors'),
}));
"""
    result = _run_node(script, tmp_path)

    assert "var(--tint:" not in result["calm"]
    assert "--tint:var(--t-accent)" in result["calm"].replace(" ", "")
    assert "--tint:var(--red)" in result["alert"].replace(" ", "")


def test_no_sensor_type_carries_a_colour_of_its_own(tmp_path: Path) -> None:
    """The regression this guards: adding a hue back to one type reopens the
    door to nine of them."""
    # Standalone: a const declared inside eval() does not leak to this scope,
    # so the table is evaluated and handed back as an expression.
    script = """
const table = eval(constOf('SENSOR_TYPE_META') + '; SENSOR_TYPE_META');
console.log(JSON.stringify({
  keys: Object.keys(table),
  withHue: Object.entries(table).filter(([, meta]) => 'hue' in meta).map(([key]) => key),
}));
"""
    meta = _run_node(script, tmp_path)

    assert meta["withHue"] == []
    assert "temperature" in meta["keys"]


def test_the_whole_palette_is_two_entries(tmp_path: Path) -> None:
    script = RENDER + """
console.log(JSON.stringify({ calm: sensorTileHue(false), alert: sensorTileHue(true) }));
"""
    palette = _run_node(script, tmp_path)

    assert palette == {"calm": "var(--t-accent)", "alert": "var(--red)"}
