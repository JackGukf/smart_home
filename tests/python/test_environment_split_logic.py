import shutil
import subprocess
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"

HARNESS = """
// process.argv[0] is the node binary, argv[1] is this harness script's own
// path, and argv[2] is the first CLI argument (the app.js path) -- see
// https://nodejs.org/api/process.html#processargv.
const src = require('fs').readFileSync(process.argv[2], 'utf8');
// Pull out just the pure helpers; app.js touches document at load time.
const pick = (name) => {
  const at = src.indexOf(`function ${name}`);
  if (at < 0) throw new Error(`missing ${name}`);
  let depth = 0, i = src.indexOf('{', at);
  const start = at;
  for (; i < src.length; i++) {
    if (src[i] === '{') depth++;
    else if (src[i] === '}') { depth--; if (depth === 0) return src.slice(start, i + 1); }
  }
  throw new Error(`unbalanced ${name}`);
};
const consts = src.match(/const ENVIRONMENT_CAPABILITIES[^;]+;/)[0];
// Safe: evaluates only trusted first-party source extracted from this repo's
// own app.js (no external/user input), as a deliberate substitute for a JS
// test toolchain the project intentionally does not have.
eval(consts + pick('sensorCapabilityKey') + pick('filterReadingsForView'));

const readings = [
  { name: 'Hub Temperature', device_class: 'temperature', category: 'tuya_temperature', state: 21 },
  { name: 'Hub Humidity',    device_class: 'humidity',    category: 'tuya_humidity',    state: 48 },
  { name: 'Hub Smoke',       device_class: 'smoke',       category: 'smoke',            state: 'off' },
  { name: 'Hub Battery',     device_class: 'battery',     category: 'battery',          state: 88 },
];

const env = filterReadingsForView(readings, 'environment').map((r) => r.name);
const sen = filterReadingsForView(readings, 'sensors').map((r) => r.name);
console.log(JSON.stringify({ env, sen }));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_four_in_one_splits_across_both_views(tmp_path: Path) -> None:
    harness = tmp_path / "harness.js"
    harness.write_text(HARNESS, encoding="utf-8")

    out = subprocess.run(
        ["node", str(harness), str(APP_JS)],
        capture_output=True, text=True, check=True,
    ).stdout

    import json
    result = json.loads(out)

    assert result["env"] == ["Hub Temperature", "Hub Humidity", "Hub Battery"]
    assert result["sen"] == ["Hub Smoke", "Hub Battery"]


# groupHasViewContent depends on expandSensorReadings, which in turn depends
# on sensorBaseName / directSensorValue / syntheticSensorReading, plus the
# KNOWN_SENSOR_CAPABILITIES const. Pull all of it out the same way the
# harness above pulls out sensorCapabilityKey/filterReadingsForView.
GROUP_HARNESS = """
const src = require('fs').readFileSync(process.argv[2], 'utf8');
const pick = (name) => {
  const at = src.indexOf(`function ${name}`);
  if (at < 0) throw new Error(`missing ${name}`);
  let depth = 0, i = src.indexOf('{', at);
  const start = at;
  for (; i < src.length; i++) {
    if (src[i] === '{') depth++;
    else if (src[i] === '}') { depth--; if (depth === 0) return src.slice(start, i + 1); }
  }
  throw new Error(`unbalanced ${name}`);
};
const pickConst = (name) => {
  const m = src.match(new RegExp(`const ${name}[^;]+;`));
  if (!m) throw new Error(`missing const ${name}`);
  return m[0];
};
// Safe: evaluates only trusted first-party source extracted from this repo's
// own app.js (no external/user input), as a deliberate substitute for a JS
// test toolchain the project intentionally does not have.
eval(
  pickConst('ENVIRONMENT_CAPABILITIES') +
  pickConst('KNOWN_SENSOR_CAPABILITIES') +
  pickConst('SENSOR_SUFFIXES') +
  pick('sensorCapabilityKey') +
  pick('filterReadingsForView') +
  pick('sensorBaseName') +
  pick('directSensorValue') +
  pick('syntheticSensorReading') +
  pick('expandSensorReadings') +
  pick('groupHasViewContent')
);

const results = {};

// (a) _tuya_card()-shaped device: no device_class, a generic category, and a
// combined `values` DPS map carrying temperature + humidity. The raw
// reading's capability key falls back to id/name (unrecognised); only the
// readings expandSensorReadings synthesises from `values` should give it a
// home, and only in Environment.
const tuyaCombined = {
  id: 'tuya-living-room',
  name: 'Living Room Sensor',
  category: 'tuya_sensor',
  values: { temp_current: 21.5, humidity: 47 },
};
results.tuyaCombined = {
  environment: groupHasViewContent({ name: 'Living Room Sensor', readings: [tuyaCombined] }, 'environment'),
  sensors: groupHasViewContent({ name: 'Living Room Sensor', readings: [tuyaCombined] }, 'sensors'),
};

// (b) Battery-only device: must not conjure a card into either view.
const batteryOnly = {
  id: 'batt-hallway',
  name: 'Hallway Battery',
  device_class: 'battery',
  category: 'battery',
  state: 88,
};
results.batteryOnly = {
  environment: groupHasViewContent({ name: 'Hallway Sensor', readings: [batteryOnly] }, 'environment'),
  sensors: groupHasViewContent({ name: 'Hallway Sensor', readings: [batteryOnly] }, 'sensors'),
};

// (c) Battery + temperature: Environment only (battery rides along as
// context but must not itself grant a Sensors card).
const battery = {
  id: 'batt-bedroom',
  name: 'Bedroom Battery',
  device_class: 'battery',
  category: 'battery',
  state: 91,
};
const temperature = {
  id: 'temp-bedroom',
  name: 'Bedroom Temperature',
  device_class: 'temperature',
  category: 'tuya_temperature',
  state: 22,
};
results.batteryPlusTemperature = {
  environment: groupHasViewContent({ name: 'Bedroom Sensor', readings: [battery, temperature] }, 'environment'),
  sensors: groupHasViewContent({ name: 'Bedroom Sensor', readings: [battery, temperature] }, 'sensors'),
};

// (d) Unrecognised-only capability (the fallback/regression guard): no
// device_class, a category that matches none of the known kinds, and no
// `values` entries expandSensorReadings could synthesise anything from.
// This must still surface in Sensors -- never Environment -- so it doesn't
// vanish from the dashboard entirely.
const unknownDevice = {
  id: 'widget-garage',
  name: 'Garage Widget',
  category: 'tuya_unknown_widget',
  values: { raw_state: 'x' },
};
results.unknownOnly = {
  environment: groupHasViewContent({ name: 'Garage Widget', readings: [unknownDevice] }, 'environment'),
  sensors: groupHasViewContent({ name: 'Garage Widget', readings: [unknownDevice] }, 'sensors'),
};

console.log(JSON.stringify(results));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_group_has_view_content_handles_unclassified_tuya_readings(tmp_path: Path) -> None:
    harness = tmp_path / "harness_group.js"
    harness.write_text(GROUP_HARNESS, encoding="utf-8")

    out = subprocess.run(
        ["node", str(harness), str(APP_JS)],
        capture_output=True, text=True, check=True,
    ).stdout

    import json
    result = json.loads(out)

    # (a) Combined Tuya reading with no device_class: qualifies for
    # Environment (via the synthesised temperature/humidity readings) and
    # must NOT qualify for Sensors just because the raw reading's key is
    # unrecognised.
    assert result["tuyaCombined"] == {"environment": True, "sensors": False}
    # (b) Battery-only device: qualifies for neither view.
    assert result["batteryOnly"] == {"environment": False, "sensors": False}
    # (c) Battery + temperature: Environment only.
    assert result["batteryPlusTemperature"] == {"environment": True, "sensors": False}
    # (d) Unrecognised-only capability: the fallback rule keeps it visible in
    # Sensors (never Environment) so it doesn't vanish from the dashboard.
    assert result["unknownOnly"] == {"environment": False, "sensors": True}


# distinctDeviceCount() is the parent Devices badge -- it must count the same
# universe the child badges/tiles draw from. Whole-branch review found it
# silently dropped latestEnvironmentSensors (the Govee H5140 this branch
# adds) and latestMatterDevices, and double-counted Tuya cameras (which have
# their own top-level view, outside the Devices group). Pull the function out
# with its two dependencies (isTuyaCamera, sensorBaseName -- which itself
# needs the SENSOR_SUFFIXES const) and stub the module-level `latest*` arrays
# it closes over as globals, the same way the harness above stubs consts.
DISTINCT_COUNT_HARNESS = """
const src = require('fs').readFileSync(process.argv[2], 'utf8');
const pick = (name) => {
  const at = src.indexOf(`function ${name}`);
  if (at < 0) throw new Error(`missing ${name}`);
  let depth = 0, i = src.indexOf('{', at);
  const start = at;
  for (; i < src.length; i++) {
    if (src[i] === '{') depth++;
    else if (src[i] === '}') { depth--; if (depth === 0) return src.slice(start, i + 1); }
  }
  throw new Error(`unbalanced ${name}`);
};
const pickConst = (name) => {
  const m = src.match(new RegExp(`const ${name}[^;]+;`));
  if (!m) throw new Error(`missing const ${name}`);
  return m[0];
};

// Stub the module-level state distinctDeviceCount reads, before defining it
// in the same eval() call so both share one lexical scope.
let latestSwitchDevices = [];
let latestMatterDevices = [];
let latestAmbientLights = [];
let latestHumidifiers = [];
let latestThermostats = [];
let latestEnvironmentSensors = [];
let latestTuyaDevices = [];

// Safe: evaluates only trusted first-party source extracted from this repo's
// own app.js (no external/user input), as a deliberate substitute for a JS
// test toolchain the project intentionally does not have.
eval(
  pickConst('SENSOR_SUFFIXES') +
  pick('isTuyaCamera') +
  pick('sensorBaseName') +
  pick('distinctDeviceCount')
);

const results = {};

// Baseline: one ordinary device in each non-Tuya category, plus one Tuya
// sensor reported as separate temperature/humidity readings that collapse
// to a single physical device via sensorBaseName.
latestSwitchDevices = [{ id: 'sw1', name: 'Kitchen Light', category: 'light_switch' }];
latestAmbientLights = [{ id: 'amb1', name: 'Ambient Lamp' }];
latestHumidifiers   = [{ id: 'hum1', name: 'Humidifier' }];
latestThermostats   = [{ id: 'th1', name: 'Thermostat' }];
latestTuyaDevices = [
  { id: 'tuya-temp', name: 'Living Room Temperature', category: 'tuya_temperature', device_class: 'temperature' },
  { id: 'tuya-hum',  name: 'Living Room Humidity',    category: 'tuya_humidity',    device_class: 'humidity' },
];
results.baseline = distinctDeviceCount();

// Add the Govee H5140-style environment sensor -- must be counted.
latestEnvironmentSensors = [
  { id: 'govee-h5140', name: 'Bedroom Thermo-Hygrometer', temperature: 21.4 },
];
results.withEnvironmentSensor = distinctDeviceCount();

// Add a Matter device -- must be counted (mirrors renderDevices() merging
// Matter into the sidebar badges).
latestMatterDevices = [
  { id: 'matter-1', name: 'Matter Hallway Light', category: 'light_switch' },
];
results.withMatterDevice = distinctDeviceCount();

// Add a Tuya camera -- must NOT be counted; cameras have their own
// top-level view outside the Devices group.
latestTuyaDevices = [
  ...latestTuyaDevices,
  { id: 'tuya-cam', name: 'Front Door Camera', category: 'tuya_camera' },
];
results.withTuyaCamera = distinctDeviceCount();

console.log(JSON.stringify(results));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_distinct_device_count_covers_the_right_universe(tmp_path: Path) -> None:
    harness = tmp_path / "harness_distinct_count.js"
    harness.write_text(DISTINCT_COUNT_HARNESS, encoding="utf-8")

    out = subprocess.run(
        ["node", str(harness), str(APP_JS)],
        capture_output=True, text=True, check=True,
    ).stdout

    import json
    result = json.loads(out)

    # Baseline: switch(1) + ambient(1) + humidifier(1) + thermostat(1) +
    # one deduplicated Tuya group ("Living Room") + the Zigbee coordinator = 6.
    # The coordinator is always counted: it is a device we own, and it reaches
    # the dashboard as bridge health rather than on any of the device lists.
    assert result["baseline"] == 6
    # The Govee environment sensor must be counted.
    assert result["withEnvironmentSensor"] == result["baseline"] + 1
    # The Matter device must be counted.
    assert result["withMatterDevice"] == result["withEnvironmentSensor"] + 1
    # The Tuya camera must NOT be counted -- the total is unchanged.
    assert result["withTuyaCamera"] == result["withMatterDevice"]
