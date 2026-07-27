"""Node-harness tests for the device groups UI.

The repo has no JS toolchain and adding one is out of scope, so these extract
the functions under test from app.js and run them under node.
"""

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


def _run_node(script: str, tmp_path: Path) -> dict:
    harness = tmp_path / "harness.js"
    harness.write_text(HARNESS_PRELUDE + script, encoding="utf-8")
    out = subprocess.run(
        ["node", str(harness), str(APP_JS)], capture_output=True, text=True, check=True
    )
    return json.loads(out.stdout)


pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def test_generic_sections_render_one_block_per_kind(tmp_path: Path) -> None:
    """One subsection per kind present, and nothing for kinds that are absent."""
    script = """
eval(pick('escapeHtml') + pick('environmentSensorCard') + pick('genericGroupSectionsHtml'));
const devices = [
  { key: 'env:g', kind: 'environment', name: 'Govee',
    data: { name: 'Govee', room: 'Bedroom', model: 'H5140', online: true, temperature: 21, humidity: 44 } },
];
const html = genericGroupSectionsHtml(devices);
console.log(JSON.stringify({
  hasSubsection: html.includes('area-subsection'),
  hasEnvironment: html.includes('Environment'),
  hasGovee: html.includes('Govee'),
  hasCameras: html.includes('Cameras'),
}));
"""
    result = _run_node(script, tmp_path)

    assert result["hasSubsection"] is True
    assert result["hasEnvironment"] is True
    assert result["hasGovee"] is True
    assert result["hasCameras"] is False


def test_generic_sections_are_empty_for_no_devices(tmp_path: Path) -> None:
    script = """
eval(pick('escapeHtml') + pick('genericGroupSectionsHtml'));
console.log(JSON.stringify({ html: genericGroupSectionsHtml([]) }));
"""
    assert _run_node(script, tmp_path)["html"] == ""


def test_render_area_detail_delegates_to_the_shared_renderer(tmp_path: Path) -> None:
    """Areas and device groups must share one implementation, not two copies."""
    javascript = APP_JS.read_text(encoding="utf-8")
    at = javascript.index("function renderAreaDetail")
    depth, body = 0, None
    for j in range(javascript.index("{", at), len(javascript)):
        if javascript[j] == "{":
            depth += 1
        elif javascript[j] == "}":
            depth -= 1
            if depth == 0:
                body = javascript[at:j + 1]
                break

    assert "genericGroupSectionsHtml" in body
    # The per-kind subsection strings must live in the shared function only.
    assert "area-subsection-title" not in body
