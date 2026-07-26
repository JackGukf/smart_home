"""Node-harness tests for the JS device-group logic.

The repo has no JS toolchain and adding one is out of scope, so these extract
the functions under test from app.js and run them under node. String-grep
assertions cannot catch a wrong rule; these can.
"""

import json
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
"""


def _run_node(script: str, tmp_path: Path) -> dict:
    harness = tmp_path / "harness.js"
    harness.write_text(HARNESS_PRELUDE + script, encoding="utf-8")
    out = subprocess.run(
        ["node", str(harness), str(APP_JS)], capture_output=True, text=True, check=True
    )
    return json.loads(out.stdout)


pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def test_environment_sensors_reach_the_shared_inventory(tmp_path: Path) -> None:
    """Without this kind the Environment group cannot collect the H5140 by rule."""
    script = """
globalThis.latestSwitchDevices = [];
globalThis.latestMatterDevices = [];
globalThis.latestTuyaDevices = [];
globalThis.latestCameras = [];
globalThis.latestThermostats = [];
globalThis.latestAmbientLights = [];
globalThis.latestHumidifiers = [];
globalThis.latestEnvironmentSensors = [
  { name: 'Govee Thermo-Hygrometer', room: 'Bedroom', temperature: 21.5, humidity: 44 }
];
eval(pick('isTuyaCamera') + pick('sensorBaseName') + pick('areaSlug')
   + pick('groupSensorDevices') + pick('isAlertDetected') + pick('cameraIdFor')
   + pick('tuyaCameraCard') + pick('collectHomeInventory'));
const inv = collectHomeInventory();
console.log(JSON.stringify(inv.map((i) => ({ key: i.key, kind: i.kind, name: i.name }))));
"""
    inventory = _run_node(script, tmp_path)

    assert inventory == [
        {"key": "env:govee-thermo-hygrometer", "kind": "environment", "name": "Govee Thermo-Hygrometer"}
    ]


def test_area_kind_icons_has_environment_entry(tmp_path: Path) -> None:
    """Without this entry, environment rows in the assign modal fall back to a
    generic ti-cpu icon instead of matching the Environment sidebar icon."""
    script = """
const at = src.indexOf('const AREA_KIND_ICONS');
if (at < 0) throw new Error('missing AREA_KIND_ICONS');
const braceStart = src.indexOf('{', at);
let depth = 0, i = braceStart;
for (; i < src.length; i++) {
  if (src[i] === '{') depth++;
  else if (src[i] === '}') { depth--; if (depth === 0) break; }
}
// Eval the object literal as an expression (not a `const` statement) so the
// binding doesn't stay trapped inside eval's own lexical scope.
const icons = eval('(' + src.slice(braceStart, i + 1) + ')');
console.log(JSON.stringify({ environment: icons.environment }));
"""
    result = _run_node(script, tmp_path)
    assert result["environment"] == "ti-temperature-celsius"


def test_render_area_detail_shows_environment_sensor(tmp_path: Path) -> None:
    """Before the fix, an area holding only an environment-kind device rendered
    zero subsections: the device was counted in the header but never drawn.
    This drives the real renderAreaDetail() over a minimal DOM stub and checks
    the sensor actually lands in the output, reusing environmentSensorCard."""
    script = """
function makeEl() {
  return { innerHTML: '', textContent: '', hidden: false, querySelector: () => null };
}
const bodyEl = makeEl();
globalThis.document = {
  querySelector: (sel) => (sel === '#areaDetailBody' ? bodyEl : makeEl()),
};

eval(pick('escapeHtml') + pick('environmentSensorCard') + pick('renderAreaDetail'));

const area = {
  icon: 'home',
  name: 'Bedroom',
  custom: false,
  devices: [
    {
      kind: 'environment',
      data: { name: 'Govee Thermo-Hygrometer', room: 'Bedroom', model: 'H5140', online: true, temperature: 21.5, humidity: 44 },
    },
  ],
};

renderAreaDetail(area);
console.log(JSON.stringify({ html: bodyEl.innerHTML }));
"""
    result = _run_node(script, tmp_path)
    html = result["html"]
    assert "area-subsection" in html
    assert "Environment" in html
    assert "device-grid" in html
    assert "Govee Thermo-Hygrometer" in html
    # sdc-card / sdc-gauges-row only come from environmentSensorCard's own
    # markup, proving the bucket is rendered via that shared function and
    # not a bespoke renderer.
    assert "sdc-card" in html
    assert "sdc-gauges-row" in html
