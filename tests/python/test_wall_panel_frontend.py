"""The dashboard obeys a show_view frame only for the decided views.

Runs the real function from app.js under node, the way the other front-end tests
here do.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"

HARNESS = """
// With `node -e`, the script's own arguments start at argv[1]; take the last two.
const [appPath, casesJson] = process.argv.slice(-2);
const src = require('fs').readFileSync(appPath, 'utf8');
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
const viewsAt = src.indexOf('const WALL_PANEL_VIEWS');
eval(src.slice(viewsAt, src.indexOf(';', viewsAt) + 1).replace('const ', 'globalThis.'));
eval(pick('wallPanelView'));
const cases = JSON.parse(casesJson);
console.log(JSON.stringify(cases.map((c) => wallPanelView(c))));
"""


def _run(cases: list) -> list:
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    out = subprocess.run(["node", "-e", HARNESS, str(APP_JS), json.dumps(cases)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def test_the_decided_views_are_obeyed() -> None:
    views = ["home", "cameras", "alarm", "devices", "climate", "status"]
    assert _run([json.dumps({"view": v}) for v in views]) == views


def test_anything_else_is_ignored() -> None:
    cases = [json.dumps({"view": "zigbee"}), json.dumps({"view": "theme"}), json.dumps({}),
             "not json", "", None, json.dumps({"view": "CAMERAS"})]
    assert _run(cases) == [None, None, None, None, None, None, "cameras"]
