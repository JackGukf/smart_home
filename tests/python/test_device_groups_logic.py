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
