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

eval(pick('escapeHtml') + pick('environmentSensorCard') + pick('genericGroupSectionsHtml')
   + pick('hydrateGenericGroupBody') + pick('renderAreaDetail'));

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


GROUPS_JS = """
const groups = [
  { id: 'lights', name: 'Lights', icon: 'bulb', color: 'amber', kinds: ['light'] },
  { id: 'climate', name: 'Climate', icon: 'temperature', color: 'orange', kinds: ['thermostat'] },
  { id: 'environment', name: 'Environment', icon: 'temperature-celsius', color: 'teal',
    kinds: ['sensor', 'environment'], readingFilter: 'environment' },
  { id: 'tuya', name: 'Sensors', icon: 'radar-2', color: 'indigo',
    kinds: ['sensor'], readingFilter: 'sensors' },
];
const inventory = [
  { key: 'dev:1', kind: 'light', name: 'Hall light' },
  { key: 'thermo:1', kind: 'thermostat', name: 'Upstairs' },
  { key: 'sensor:hub', kind: 'sensor', name: 'Hub' },
  { key: 'env:govee', kind: 'environment', name: 'Govee' },
];
const members = (id, overrides) => resolveDeviceGroupMembers(
  groups.find((g) => g.id === id), inventory, overrides || {}
).map((m) => m.key);
"""


def test_type_rule_collects_matching_devices(tmp_path: Path) -> None:
    script = f"""
eval(pick('resolveDeviceGroupMembers'));
{GROUPS_JS}
console.log(JSON.stringify({{
  lights: members('lights'),
  climate: members('climate'),
}}));
"""
    result = _run_node(script, tmp_path)

    assert result["lights"] == ["dev:1"]
    assert result["climate"] == ["thermo:1"]


def test_a_sensor_appears_in_both_split_groups(tmp_path: Path) -> None:
    """Environment and Sensors are two views of one device's readings, not two
    competing homes. Environment also collects the standalone Govee sensor."""
    script = f"""
eval(pick('resolveDeviceGroupMembers'));
{GROUPS_JS}
console.log(JSON.stringify({{
  environment: members('environment'),
  sensors: members('tuya'),
}}));
"""
    result = _run_node(script, tmp_path)

    assert result["environment"] == ["sensor:hub", "env:govee"]
    assert result["sensors"] == ["sensor:hub"]


def test_exclude_override_removes_an_auto_collected_device(tmp_path: Path) -> None:
    script = f"""
eval(pick('resolveDeviceGroupMembers'));
{GROUPS_JS}
const ov = {{ 'dev:1': {{ include: [], exclude: ['lights'] }} }};
console.log(JSON.stringify({{ lights: members('lights', ov) }}));
"""
    assert _run_node(script, tmp_path)["lights"] == []


def test_include_override_adds_a_device_its_kind_does_not_match(tmp_path: Path) -> None:
    script = f"""
eval(pick('resolveDeviceGroupMembers'));
{GROUPS_JS}
const ov = {{ 'thermo:1': {{ include: ['lights'], exclude: [] }} }};
console.log(JSON.stringify({{ lights: members('lights', ov) }}));
"""
    assert _run_node(script, tmp_path)["lights"] == ["dev:1", "thermo:1"]


def test_exclude_wins_when_a_device_is_both_included_and_excluded(tmp_path: Path) -> None:
    """Pins the tie-break for a device whose override names the same group in
    both lists. Exclude winning is the safer default, but without this test
    someone could invert the two checks and every other test would still pass.
    """
    script = f"""
eval(pick('resolveDeviceGroupMembers'));
{GROUPS_JS}
// dev:1 is auto-collected by the lights kind rule AND force-included, yet the
// exclude must still take precedence.
const ov = {{ 'dev:1': {{ include: ['lights'], exclude: ['lights'] }} }};
console.log(JSON.stringify({{ lights: members('lights', ov) }}));
"""
    assert _run_node(script, tmp_path)["lights"] == []


def test_overrides_for_unknown_devices_and_groups_are_harmless(tmp_path: Path) -> None:
    script = f"""
eval(pick('resolveDeviceGroupMembers'));
{GROUPS_JS}
const ov = {{
  'dev:never-seen': {{ include: ['lights'], exclude: [] }},
  'dev:1': {{ include: ['deleted-group'], exclude: [] }},
}};
console.log(JSON.stringify({{ lights: members('lights', ov) }}));
"""
    assert _run_node(script, tmp_path)["lights"] == ["dev:1"]


def test_nav_plan_preserves_order_and_maps_colours(tmp_path: Path) -> None:
    script = f"""
eval(src.slice(src.indexOf('const GROUP_COLOR_VARS'), src.indexOf('function deviceGroupNavPlan')) + pick('deviceGroupNavPlan') + 'const x=0;');
{GROUPS_JS}
console.log(JSON.stringify(deviceGroupNavPlan(groups)));
"""
    plan = _run_node(script, tmp_path)

    assert [p["id"] for p in plan] == ["lights", "climate", "environment", "tuya"]
    assert plan[0]["color"] == "var(--amber)"


def test_nav_plan_neutralises_an_unknown_colour(tmp_path: Path) -> None:
    """The colour reaches a CSS custom property, so an unexpected value must
    resolve to a known variable rather than being passed through."""
    script = """
eval(src.slice(src.indexOf('const GROUP_COLOR_VARS'), src.indexOf('function deviceGroupNavPlan')) + pick('deviceGroupNavPlan') + 'const x=0;');
const groups = [{ id: 'x', name: 'X', icon: 'bulb', color: 'red; background:url(y)', kinds: [] }];
console.log(JSON.stringify(deviceGroupNavPlan(groups)));
"""
    plan = _run_node(script, tmp_path)

    assert plan[0]["color"] == "var(--slate)"


def test_device_group_views_is_derived_not_hardcoded(tmp_path: Path) -> None:
    javascript = APP_JS.read_text(encoding="utf-8")

    assert "let DEVICE_GROUP_VIEWS" in javascript, "must be reassignable once groups load"
    assert 'requestJson("/api/device-groups")' in javascript
    assert "function syncDeviceGroupNav" in javascript


def test_nav_sync_uses_the_dom_api_not_markup_strings(tmp_path: Path) -> None:
    """color and icon originate in a hand-editable JSON file and reach a CSS
    custom property and a class attribute. Neither may be interpolated into
    markup."""
    javascript = APP_JS.read_text(encoding="utf-8")
    at = javascript.index("function syncDeviceGroupNav")
    depth, i, body = 0, javascript.index("{", at), None
    for j in range(i, len(javascript)):
        if javascript[j] == "{":
            depth += 1
        elif javascript[j] == "}":
            depth -= 1
            if depth == 0:
                body = javascript[at:j + 1]
                break

    assert "setProperty(\"--group-color\"" in body
    assert "classList.add" in body
    assert "innerHTML" not in body, "nav sync must not build markup strings"
