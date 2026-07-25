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
