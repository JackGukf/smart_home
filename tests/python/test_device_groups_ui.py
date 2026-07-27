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


def _find_all_ui(haystack: str, needle: str) -> list[int]:
    offsets, at = [], haystack.find(needle)
    while at != -1:
        offsets.append(at)
        at = haystack.find(needle, at + 1)
    return offsets


def _balanced_block_ui(source: str, start: int) -> str:
    """The statement at start, extended to its matching close brace, so an
    assertion cannot pass on a neighbouring block's contents."""
    depth = 0
    for i in range(source.index("{", start), len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[start:i + 1]
    raise AssertionError("unbalanced braces")



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


RESOLVE_JS = """
globalThis.latestSwitchDevices = [];
globalThis.latestMatterDevices = [];
globalThis.latestTuyaDevices = [];
globalThis.latestCameras = [];
globalThis.latestThermostats = [];
globalThis.latestAmbientLights = [];
globalThis.latestHumidifiers = [];
globalThis.latestEnvironmentSensors = [];
eval(pick('isTuyaCamera') + pick('sensorBaseName') + pick('areaSlug')
   + pick('groupSensorDevices') + pick('isAlertDetected') + pick('cameraIdFor')
   + pick('tuyaCameraCard') + pick('collectHomeInventory')
   + pick('resolveDeviceGroupMembers') + constOf('UNASSIGNED_GROUP_ID')
   + pick('resolveDeviceGroups'));
// Stub the inventory directly so the test controls the device set exactly.
collectHomeInventory = () => ([
  { key: 'dev:1', kind: 'light', name: 'Hall light' },
  { key: 'thermo:1', kind: 'thermostat', name: 'Upstairs' },
]);
"""


def test_unassigned_is_absent_when_every_device_has_a_group(tmp_path: Path) -> None:
    script = f"""
{RESOLVE_JS}
globalThis.latestDeviceGroups = [
  {{ id: 'lights', name: 'Lights', icon: 'bulb', color: 'amber', kinds: ['light'] }},
  {{ id: 'climate', name: 'Climate', icon: 'temperature', color: 'orange', kinds: ['thermostat'] }},
];
globalThis.latestDeviceGroupOverrides = {{}};
console.log(JSON.stringify(resolveDeviceGroups().map((g) => ({{ id: g.id, keys: g.devices.map((d) => d.key) }}))));
"""
    result = _run_node(script, tmp_path)

    assert [g["id"] for g in result] == ["lights", "climate"]
    assert result[0]["keys"] == ["dev:1"]


def test_unassigned_collects_orphans_and_sorts_last(tmp_path: Path) -> None:
    """Built-in groups are deletable, so a device must never become invisible."""
    script = f"""
{RESOLVE_JS}
globalThis.latestDeviceGroups = [
  {{ id: 'lights', name: 'Lights', icon: 'bulb', color: 'amber', kinds: ['light'] }},
];
globalThis.latestDeviceGroupOverrides = {{}};
console.log(JSON.stringify(resolveDeviceGroups().map((g) => ({{ id: g.id, keys: g.devices.map((d) => d.key) }}))));
"""
    result = _run_node(script, tmp_path)

    assert [g["id"] for g in result] == ["lights", "auto:unassigned"]
    assert result[-1]["keys"] == ["thermo:1"]


def test_a_device_in_two_groups_is_not_unassigned(tmp_path: Path) -> None:
    script = f"""
{RESOLVE_JS}
globalThis.latestDeviceGroups = [
  {{ id: 'lights', name: 'Lights', icon: 'bulb', color: 'amber', kinds: ['light'] }},
  {{ id: 'spare', name: 'Spare', icon: 'bulb', color: 'teal', kinds: ['light'] }},
  {{ id: 'climate', name: 'Climate', icon: 'temperature', color: 'orange', kinds: ['thermostat'] }},
];
globalThis.latestDeviceGroupOverrides = {{}};
const out = resolveDeviceGroups();
console.log(JSON.stringify({{
  ids: out.map((g) => g.id),
  lights: out[0].devices.map((d) => d.key),
  spare: out[1].devices.map((d) => d.key),
}}));
"""
    result = _run_node(script, tmp_path)

    assert "auto:unassigned" not in result["ids"]
    assert result["lights"] == ["dev:1"]
    assert result["spare"] == ["dev:1"]


def test_load_stores_the_overrides_map(tmp_path: Path) -> None:
    """Cycle 1 stored only groups; resolution needs the overrides too."""
    javascript = APP_JS.read_text(encoding="utf-8")

    assert "latestDeviceGroupOverrides" in javascript
    at = javascript.index("async function loadDeviceGroups")
    depth, body = 0, None
    for j in range(javascript.index("{", at), len(javascript)):
        if javascript[j] == "{":
            depth += 1
        elif javascript[j] == "}":
            depth -= 1
            if depth == 0:
                body = javascript[at:j + 1]
                break

    assert "latestDeviceGroupOverrides" in body


def test_group_member_data_filters_by_kind(tmp_path: Path) -> None:
    script = f"""
{RESOLVE_JS}
globalThis.latestDeviceGroups = [
  {{ id: 'lights', name: 'Lights', icon: 'bulb', color: 'amber', kinds: ['light'] }},
];
globalThis.latestDeviceGroupOverrides = {{ 'thermo:1': {{ include: ['lights'], exclude: [] }} }};
eval(pick('findDeviceGroup') + pick('groupMemberData'));
console.log(JSON.stringify({{
  native: groupMemberData('lights', ['light', 'plug']).length,
  foreign: groupMemberData('lights', ['thermostat']).length,
}}));
"""
    result = _run_node(script, tmp_path)

    assert result["native"] == 1
    assert result["foreign"] == 1


def test_panels_read_membership_not_type_filters(tmp_path: Path) -> None:
    """The whole point of this cycle: an override must reach the panels."""
    javascript = APP_JS.read_text(encoding="utf-8")

    for fn in ["renderDevices", "renderAmbientLights", "renderHumidifiers",
               "renderTuyaDevices", "renderThermostats"]:
        # Anchor on the opening paren: "renderDevices" is also a prefix of
        # "renderDevicesOverview", and an unanchored search finds that first.
        at = javascript.index(f"function {fn}(")
        depth, body = 0, None
        for j in range(javascript.index("{", at), len(javascript)):
            if javascript[j] == "{":
                depth += 1
            elif javascript[j] == "}":
                depth -= 1
                if depth == 0:
                    body = javascript[at:j + 1]
                    break
        assert "groupMemberData" in body, f"{fn} still selects devices by type"


def test_global_stats_still_come_from_the_full_device_list(tmp_path: Path) -> None:
    """deviceCount and onCount describe every switch, not the Lights group.
    Sourcing them from membership would make the Status view wrong."""
    javascript = APP_JS.read_text(encoding="utf-8")
    # Anchor on the opening paren: "renderDevices" is also a prefix of
    # "renderDevicesOverview", and an unanchored search finds that first.
    at = javascript.index("function renderDevices(")
    depth, body = 0, None
    for j in range(javascript.index("{", at), len(javascript)):
        if javascript[j] == "{":
            depth += 1
        elif javascript[j] == "}":
            depth -= 1
            if depth == 0:
                body = javascript[at:j + 1]
                break

    stats = body[body.index("deviceCount.textContent"):body.index("cameraTabCount.textContent")]
    assert "groupMemberData" not in stats


def _function_body(javascript: str, name: str) -> str:
    """Brace-match a top-level function's body, anchored on the opening paren
    so a prefix match (e.g. renderDevices vs renderDevicesOverview) can't win."""
    at = javascript.index(f"function {name}(")
    depth, body = 0, None
    for j in range(javascript.index("{", at), len(javascript)):
        if javascript[j] == "{":
            depth += 1
        elif javascript[j] == "}":
            depth -= 1
            if depth == 0:
                body = javascript[at:j + 1]
                break
    assert body is not None, f"unbalanced braces for function {name}"
    return body


def test_foreign_kinds_render_even_when_native_list_is_empty() -> None:
    """A group's bespoke renderer must never early-return before
    renderForeignKinds runs, or a device a user moved into that group
    vanishes silently whenever the group has no native devices of its own.

    Regression coverage for renderAmbientLights, renderHumidifiers,
    renderTuyaDevices, renderThermostats, and renderEnvironmentSensors, each
    of which used to `return;` out of its empty-native-list branch before
    reaching its renderForeignKinds() call.
    """
    javascript = APP_JS.read_text(encoding="utf-8")

    for fn in ["renderAmbientLights", "renderHumidifiers", "renderTuyaDevices",
               "renderThermostats", "renderEnvironmentSensors"]:
        body = _function_body(javascript, fn)
        foreign_at = body.index("renderForeignKinds(")
        preamble = body[:foreign_at]
        # Ignore the `if (!x) return;` DOM-missing guards near the top of
        # each function (e.g. `if (!ambientGrid) return;`) — those aren't the
        # bug under test. What must not exist is a `return;` that follows an
        # empty-native-list `.innerHTML =` assignment, i.e. the empty-state
        # branch. So assert no bare `return;` appears anywhere after the
        # first `.innerHTML =` assignment and before renderForeignKinds().
        first_innerhtml = preamble.index(".innerHTML")
        after_innerhtml = preamble[first_innerhtml:]
        assert "return;" not in after_innerhtml, (
            f"{fn} still returns before its renderForeignKinds() call, "
            "so foreign devices in an otherwise-empty group would vanish"
        )


def test_render_devices_has_no_early_return_before_foreign_kinds() -> None:
    """Companion check to the fix above: renderDevices has no empty-native-
    list branch at all, so its two renderForeignKinds() calls already run
    unconditionally at the end of the function. Pin that shape so nobody
    "fixes" it redundantly later.

    (renderThermostats and renderEnvironmentSensors had the identical
    early-return defect and are now covered by
    test_foreign_kinds_render_even_when_native_list_is_empty above.)"""
    javascript = APP_JS.read_text(encoding="utf-8")

    body = _function_body(javascript, "renderDevices")
    assert body.rstrip().endswith(
        'renderForeignKinds("plugs", ["plug"], "#plugGrid");\n}'
    )


# ── "not configured" vs "not in this group" ──
#
# Moving a device out of its native group used to make the panel claim
# nothing of that kind was configured at all -- false whenever the device
# exists but simply lives in a different group (or no group). Each of the
# five panels below must tell those two situations apart: an empty full list
# keeps the original copy, a non-empty full list with an empty group gets a
# new "not in this group" message.


def test_render_ambient_lights_distinguishes_empty_group_from_nothing_configured(tmp_path: Path) -> None:
    script = f"""
{RESOLVE_JS}
globalThis.ambientGrid = {{ innerHTML: "" }};
globalThis.ambientCount = {{ textContent: "" }};
globalThis.renderForeignKinds = () => {{}};
eval(pick('findDeviceGroup') + pick('groupMemberData') + pick('renderAmbientLights'));

const results = {{}};

// Nothing of this kind exists anywhere.
collectHomeInventory = () => ([]);
globalThis.latestDeviceGroups = [
  {{ id: 'ambient', name: 'Ambient', icon: 'lamp-2', color: 'amber', kinds: ['ambient'] }},
];
globalThis.latestDeviceGroupOverrides = {{}};
renderAmbientLights({{ lights: [] }});
results.nothingConfigured = ambientGrid.innerHTML;

// One light exists, but the user moved it out of the Ambient group.
resolveDeviceGroups.cache = null;
collectHomeInventory = () => ([
  {{ key: 'ambient:1', kind: 'ambient', name: 'Lamp', room: 'Den', data: {{ id: '1', name: 'Lamp' }} }},
]);
globalThis.latestDeviceGroupOverrides = {{ 'ambient:1': {{ include: [], exclude: ['ambient'] }} }};
renderAmbientLights({{ lights: [{{ id: '1', name: 'Lamp' }}] }});
results.excludedFromGroup = ambientGrid.innerHTML;

console.log(JSON.stringify(results));
"""
    result = _run_node(script, tmp_path)

    assert "No ambient lights configured yet" in result["nothingConfigured"]
    assert "No devices in this group" in result["excludedFromGroup"]
    assert "No ambient lights configured yet" not in result["excludedFromGroup"]


def test_render_humidifiers_distinguishes_empty_group_from_nothing_configured(tmp_path: Path) -> None:
    script = f"""
{RESOLVE_JS}
const humidifierGridEl = {{ innerHTML: "" }};
const humidifierCountEl = {{ textContent: "" }};
globalThis.document = {{
  querySelector: (sel) => {{
    if (sel === "#humidifierGrid") return humidifierGridEl;
    if (sel === "#humidifierCount") return humidifierCountEl;
    return null;
  }},
}};
globalThis.renderForeignKinds = () => {{}};
eval(pick('findDeviceGroup') + pick('groupMemberData') + pick('renderHumidifiers'));

const results = {{}};

// Nothing of this kind exists anywhere.
collectHomeInventory = () => ([]);
globalThis.latestDeviceGroups = [
  {{ id: 'humidifier', name: 'Humidifiers', icon: 'droplet', color: 'cyan', kinds: ['humidifier'] }},
];
globalThis.latestDeviceGroupOverrides = {{}};
renderHumidifiers({{ humidifiers: [] }});
results.nothingConfigured = humidifierGridEl.innerHTML;

// One humidifier exists, but the user moved it out of the group.
resolveDeviceGroups.cache = null;
collectHomeInventory = () => ([
  {{ key: 'humidifier:1', kind: 'humidifier', name: 'Bedroom Humidifier', room: 'Bedroom',
     data: {{ id: '1', name: 'Bedroom Humidifier' }} }},
]);
globalThis.latestDeviceGroupOverrides = {{ 'humidifier:1': {{ include: [], exclude: ['humidifier'] }} }};
renderHumidifiers({{ humidifiers: [{{ id: '1', name: 'Bedroom Humidifier' }}] }});
results.excludedFromGroup = humidifierGridEl.innerHTML;

console.log(JSON.stringify(results));
"""
    result = _run_node(script, tmp_path)

    assert "No humidifiers configured yet" in result["nothingConfigured"]
    assert "No devices in this group" in result["excludedFromGroup"]
    assert "No humidifiers configured yet" not in result["excludedFromGroup"]


def test_render_tuya_devices_distinguishes_empty_group_from_nothing_configured(tmp_path: Path) -> None:
    script = f"""
{RESOLVE_JS}
globalThis.tuyaGrid = {{ innerHTML: "" }};
globalThis.tuyaCount = {{ textContent: "" }};
globalThis.renderForeignKinds = () => {{}};
globalThis.sensorGroupCount = () => 0;
eval(pick('findDeviceGroup') + pick('groupMemberData') + pick('renderTuyaDevices'));

const results = {{}};

// Nothing of this kind exists anywhere.
collectHomeInventory = () => ([]);
globalThis.latestDeviceGroups = [
  {{ id: 'tuya', name: 'Sensors', icon: 'antenna', color: 'teal', kinds: ['sensor'] }},
];
globalThis.latestDeviceGroupOverrides = {{}};
renderTuyaDevices([]);
results.nothingConfigured = tuyaGrid.innerHTML;

// A Tuya sensor exists on the network, but not as a member of this group.
resolveDeviceGroups.cache = null;
renderTuyaDevices([
  {{ id: 's1', name: 'Living Room Temperature', category: 'tuya_temperature', device_class: 'temperature' }},
]);
results.excludedFromGroup = tuyaGrid.innerHTML;

console.log(JSON.stringify(results));
"""
    result = _run_node(script, tmp_path)

    assert "No Tuya devices found from Home Assistant yet" in result["nothingConfigured"]
    assert "No devices in this group" in result["excludedFromGroup"]
    assert "No Tuya devices found from Home Assistant yet" not in result["excludedFromGroup"]


def test_render_environment_sensors_distinguishes_empty_group_from_nothing_configured(tmp_path: Path) -> None:
    """sensorGroupCount() is pre-existing, unchanged code (it already backs the
    Environment overview tile) -- stub it directly so this test isolates the
    new fullTotal branch the fix adds, rather than re-deriving the whole
    expandSensorReadings/groupHasViewContent capability chain."""
    script = f"""
{RESOLVE_JS}
const environmentGridEl = {{ innerHTML: "" }};
const environmentCountEl = {{ textContent: "" }};
globalThis.document = {{
  querySelector: (sel) => {{
    if (sel === "#environmentGrid") return environmentGridEl;
    if (sel === "#environmentCount") return environmentCountEl;
    return null;
  }},
}};
globalThis.renderForeignKinds = () => {{}};
let sensorGroupCountValue = 0;
globalThis.sensorGroupCount = () => sensorGroupCountValue;
eval(pick('findDeviceGroup') + pick('groupMemberData') + pick('renderEnvironmentSensors'));

const results = {{}};

// Nothing of this kind exists anywhere.
collectHomeInventory = () => ([]);
globalThis.latestDeviceGroups = [
  {{ id: 'environment', name: 'Environment', icon: 'temperature-celsius', color: 'cyan',
     kinds: ['sensor', 'environment'] }},
];
globalThis.latestDeviceGroupOverrides = {{}};
globalThis.latestEnvironmentSensors = [];
sensorGroupCountValue = 0;
renderEnvironmentSensors();
results.nothingConfigured = environmentGridEl.innerHTML;

// A temperature/humidity device exists, just excluded from this group.
resolveDeviceGroups.cache = null;
sensorGroupCountValue = 1;
renderEnvironmentSensors();
results.excludedFromGroup = environmentGridEl.innerHTML;

console.log(JSON.stringify(results));
"""
    result = _run_node(script, tmp_path)

    assert "No temperature or humidity sensors reporting yet" in result["nothingConfigured"]
    assert "No devices in this group" in result["excludedFromGroup"]
    assert "No temperature or humidity sensors reporting yet" not in result["excludedFromGroup"]


def test_render_thermostats_distinguishes_empty_group_from_nothing_configured(tmp_path: Path) -> None:
    """Direct regression test for the reported bug: with one Ecobee thermostat
    on the network moved out of the Climate group, the panel must not claim
    nothing is configured. thermostatCount and indoorTemp were already correct
    per the reviewer's report -- pin that they stay correct after the fix."""
    script = f"""
{RESOLVE_JS}
globalThis.thermostatGrid = {{ innerHTML: "" }};
globalThis.thermostatCount = {{ textContent: "" }};
globalThis.indoorTemp = {{ textContent: "" }};
globalThis.renderForeignKinds = () => {{}};
eval(pick('escapeHtml') + pick('findDeviceGroup') + pick('groupMemberData') + pick('renderThermostats'));

const results = {{}};

// Nothing of this kind exists anywhere.
collectHomeInventory = () => ([]);
globalThis.latestDeviceGroups = [
  {{ id: 'climate', name: 'Climate', icon: 'temperature', color: 'orange', kinds: ['thermostat'] }},
];
globalThis.latestDeviceGroupOverrides = {{}};
renderThermostats({{ thermostats: [] }});
results.nothingConfigured = thermostatGrid.innerHTML;

// One Ecobee thermostat exists, but the user moved it out of Climate.
resolveDeviceGroups.cache = null;
collectHomeInventory = () => ([
  {{ key: 'thermo:1', kind: 'thermostat', name: 'Hallway', room: '',
     data: {{ id: '1', name: 'Hallway', temperature: 70, temperature_unit: 'F' }} }},
]);
globalThis.latestDeviceGroupOverrides = {{ 'thermo:1': {{ include: [], exclude: ['climate'] }} }};
renderThermostats({{ thermostats: [{{ id: '1', name: 'Hallway', temperature: 70, temperature_unit: 'F' }}] }});
results.excludedFromGroup = thermostatGrid.innerHTML;
results.thermostatCount = thermostatCount.textContent;
results.indoorTemp = indoorTemp.textContent;

console.log(JSON.stringify(results));
"""
    result = _run_node(script, tmp_path)

    assert "No Ecobee thermostats configured yet" in result["nothingConfigured"]
    assert "No devices in this group" in result["excludedFromGroup"]
    assert "No Ecobee thermostats configured yet" not in result["excludedFromGroup"]
    # The reviewer confirmed these counters already counted the moved-out
    # thermostat correctly -- this is a copy bug only, not a data bug.
    assert result["thermostatCount"] == "1"
    assert result["indoorTemp"] == "70°F"


def test_rail_buttons_are_queried_fresh_not_snapshotted() -> None:
    """A snapshot taken at module load cannot see nav items added later, which
    silently breaks active-class toggling and the startup-view dropdown."""
    javascript = APP_JS.read_text(encoding="utf-8")

    assert "function railButtonEls" in javascript
    assert "const railButtons = Array.from" not in javascript
    assert "railButtons.forEach" not in javascript


def test_sidebar_clicks_are_delegated_not_per_item() -> None:
    """One delegated listener cannot double-register or miss a created item."""
    javascript = APP_JS.read_text(encoding="utf-8")
    at = javascript.index("function syncDeviceGroupNav")
    depth, body = 0, None
    for j in range(javascript.index("{", at), len(javascript)):
        if javascript[j] == "{":
            depth += 1
        elif javascript[j] == "}":
            depth -= 1
            if depth == 0:
                body = javascript[at:j + 1]
                break

    assert "addEventListener" not in body, "sync must attach no listeners of its own"


def test_delegated_sidebar_handler_ignores_the_chevron() -> None:
    """Clicking the Devices chevron collapses the group without navigating. The
    old per-item listeners never saw chevron clicks; a document-level one does."""
    javascript = APP_JS.read_text(encoding="utf-8")
    handlers = [
        _balanced_block_ui(javascript, at)
        for at in _find_all_ui(javascript, 'document.addEventListener("click"')
    ]
    sidebar = [h for h in handlers if ".room-item[data-view]" in h]

    assert len(sidebar) == 1
    assert "settings-chevron" in sidebar[0]


def test_override_merge_preserves_other_groups(tmp_path: Path) -> None:
    """PUT /overrides replaces a device's entire entry, so toggling one group
    must resend the device's entries for every other group. Getting this wrong
    silently wipes an unrelated override."""
    script = """
eval(pick('mergedOverrideFor'));
globalThis.latestDeviceGroupOverrides = {
  'sensor:hub': { include: ['climate'], exclude: ['environment'] },
};
// The device is not auto-collected by 'lights', so ticking it adds an include.
const next = mergedOverrideFor('sensor:hub', 'lights', true, false);
console.log(JSON.stringify(next));
"""
    result = _run_node(script, tmp_path)

    assert sorted(result["include"]) == ["climate", "lights"]
    assert result["exclude"] == ["environment"]


def test_toggle_transitions_write_only_deviations(tmp_path: Path) -> None:
    """Rule-member + wants member -> cleared. Rule-member + wants out -> exclude.
    Not-rule-member + wants in -> include. Not-rule + wants out -> cleared."""
    script = """
eval(pick('mergedOverrideFor'));
globalThis.latestDeviceGroupOverrides = {};
console.log(JSON.stringify({
  ruleInWantsIn:  mergedOverrideFor('dev:1', 'lights', true,  true),
  ruleInWantsOut: mergedOverrideFor('dev:1', 'lights', false, true),
  ruleOutWantsIn: mergedOverrideFor('dev:1', 'lights', true,  false),
  ruleOutWantsOut:mergedOverrideFor('dev:1', 'lights', false, false),
}));
"""
    result = _run_node(script, tmp_path)

    assert result["ruleInWantsIn"] == {"include": [], "exclude": []}
    assert result["ruleInWantsOut"] == {"include": [], "exclude": ["lights"]}
    assert result["ruleOutWantsIn"] == {"include": ["lights"], "exclude": []}
    assert result["ruleOutWantsOut"] == {"include": [], "exclude": []}


def test_manage_modal_markup_exists() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="manageDevicesModal"' in html
    assert 'id="manageDevicesList"' in html
    for view in ["lights", "plugs", "ambient", "humidifier", "environment", "tuya", "climate"]:
        start = html.index(f'data-view-panel="{view}"')
        end = html.index("data-view-panel=", start + 10) if "data-view-panel=" in html[start + 10:] else len(html)
        assert "data-manage-group" in html[start:end], f"{view} panel has no Manage Devices button"
