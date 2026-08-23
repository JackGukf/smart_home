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


def test_settings_chevron_cannot_be_hijacked_by_the_sidebar_handler() -> None:
    """The Devices chevron is gone with its children, so the handler no longer
    guards against it. The Settings chevron still exists, and is only safe
    because #systemSettingsToggle carries no data-view — give it one and every
    click on it would start navigating."""
    html = INDEX_HTML.read_text(encoding="utf-8")

    at = html.index('id="systemSettingsToggle"')
    entry = html[html.rindex("<li", 0, at):html.index("</li>", at)]
    assert "settings-chevron" in entry
    assert "data-view=" not in entry


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


def test_manage_devices_rule_member_ignores_overrides(tmp_path: Path) -> None:
    """renderManageDevicesList must resolve data-rule-member against an EMPTY
    overrides map, so the attribute reflects the group's kind rule alone --
    independent of any override the user already set. That value is read back
    by toggleManageDevice as ruleSaysMember and decides which deviation gets
    stored on the next toggle; resolving it against the real overrides instead
    would silently invert membership for any device already overridden in."""
    script = f"""
{RESOLVE_JS}
const list = {{ innerHTML: "" }};
globalThis.document = {{
  querySelector: (sel) => (sel === "#manageDevicesList" ? list : null),
}};
collectHomeInventory = () => ([
  {{ key: 'dev:1', kind: 'light', name: 'Kitchen Light' }},
  {{ key: 'dev:2', kind: 'plug', name: 'Office Plug' }},
]);
globalThis.latestDeviceGroups = [
  {{ id: 'lights', name: 'Lights', icon: 'bulb', color: 'amber', kinds: ['light'] }},
];
// dev:2 is a plug -- it fails the group's kind rule -- and is only a member
// because of an explicit include override, not because the rule says so.
globalThis.latestDeviceGroupOverrides = {{ 'dev:2': {{ include: ['lights'], exclude: [] }} }};
globalThis.manageDevicesGroupId = 'lights';
eval(pick('escapeHtml') + constOf('AREA_KIND_ICONS') + pick('findDeviceGroup') + pick('renderManageDevicesList'));
renderManageDevicesList();
const rows = [...list.innerHTML.matchAll(/data-manage-key="([^"]+)"[\\s\\S]*?data-rule-member="(\\d)"/g)]
  .map((m) => ({{ key: m[1], ruleMember: m[2] }}));
console.log(JSON.stringify(rows));
"""
    result = _run_node(script, tmp_path)
    by_key = {row["key"]: row["ruleMember"] for row in result}

    assert by_key["dev:1"] == "1"  # member because its kind matches the rule
    assert by_key["dev:2"] == "0"  # member only via override -- rule says no


def test_toggle_manage_device_reverts_checkbox_on_failed_save(tmp_path: Path) -> None:
    """The browser flips checkbox.checked natively before the delegated change
    handler ever runs. If the PUT to /api/device-groups/overrides rejects, a
    failed save must not leave that native flip in place -- the checkbox has to
    go back to what it was before the user touched it, and the failure must
    reach the user (not just the console)."""
    script = """
globalThis.latestDeviceGroupOverrides = {};
globalThis.manageDevicesGroupId = 'lights';
globalThis.requestJson = async () => { throw new Error('boom'); };
globalThis.loadDeviceGroups = async () => { throw new Error('must not run when the save failed'); };
globalThis.renderManageDevicesList = () => { throw new Error('must not run when the save failed'); };
globalThis.loadDevices = () => Promise.resolve();
const logCalls = [];
globalThis.logActivity = (text, type) => { logCalls.push({ text, type }); };
const consoleErrors = [];
globalThis.console = {
  log: (...args) => process.stdout.write(args.join(' ') + '\\n'),
  error: (e) => consoleErrors.push(String(e && e.message || e)),
};

eval(pick('mergedOverrideFor') + 'async ' + pick('toggleManageDevice'));

// The checkbox was unchecked; the user just ticked it, so the browser has
// already flipped .checked to true before this handler runs.
const checkbox = { dataset: { manageKey: 'dev:1', ruleMember: '0' }, checked: true };

toggleManageDevice(checkbox)
  .catch((error) => { consoleErrors.push('unhandled: ' + error.message); })
  .then(() => {
    console.log(JSON.stringify({ checked: checkbox.checked, logCalls, consoleErrors }));
  });
"""
    result = _run_node(script, tmp_path)

    assert result["checked"] is False, "checkbox must be reverted to its pre-toggle state on failure"
    assert len(result["logCalls"]) == 1, "the failure must be surfaced to the user, not just logged to console"


def test_group_modal_markup_and_pickers() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="groupModal"' in html
    assert 'id="groupNameInput"' in html
    assert 'id="groupIconPicker"' in html
    assert 'id="groupColorPicker"' in html
    assert 'id="groupDelete"' in html


def test_colour_swatches_come_from_the_shared_allowlist(tmp_path: Path) -> None:
    """The picker must render from GROUP_COLOR_VARS so it cannot drift from the
    allowlist the API validates against."""
    javascript = APP_JS.read_text(encoding="utf-8")
    at = javascript.index("function renderGroupColorPicker")
    depth, body = 0, None
    for j in range(javascript.index("{", at), len(javascript)):
        if javascript[j] == "{":
            depth += 1
        elif javascript[j] == "}":
            depth -= 1
            if depth == 0:
                body = javascript[at:j + 1]
                break

    assert "GROUP_COLOR_VARS" in body


# ── Group create/edit modal: openGroupModal / submitGroupModal ──
#
# One modal, one save button, and a module-level `groupModalEditingId` decide
# whether Save means "create" or "edit". Nothing exercised these three
# functions before: a mutation that makes submitGroupModal always POST (an
# edit silently creates a duplicate group instead of updating the original)
# passed all 53 pre-existing tests. The scripts below stub `requestJson` to
# capture the method/URL/body actually sent, and drive the real
# openGroupModal/submitGroupModal functions extracted from app.js -- not a
# reimplementation of their logic.
#
# submitGroupModal and deleteGroupFromModal are declared `async function` in
# app.js; pick() matches on the literal text "function <name>" so the
# extracted snippet is missing its `async` keyword (see the working
# `'async ' + pick('toggleManageDevice')` precedent above) -- each use below
# re-prepends it so `await` inside is legal.

GROUP_MODAL_JS = """
globalThis.latestDeviceGroups = [
  { id: 'lights', name: 'Lights', icon: 'bulb', color: 'amber', kinds: ['light'] },
];
globalThis.latestDeviceGroupOverrides = {};

// Minimal DOM stub for every element openGroupModal/submitGroupModal touch.
// The icon/colour picker elements need a no-op querySelectorAll because
// renderGroupColorPicker calls .forEach() on its result.
const groupModalEls = {
  '#groupModalTitle': { textContent: '' },
  '#groupNameInput': { value: '' },
  '#groupSave': { textContent: '' },
  '#groupDelete': { hidden: false },
  '#groupModalError': { hidden: false },
  '#groupModalErrorText': { textContent: '' },
  '#groupModal': { hidden: true },
  '#groupIconPicker': { innerHTML: '', querySelectorAll: () => [] },
  '#groupColorPicker': { innerHTML: '', querySelectorAll: () => [] },
};
globalThis.document = { querySelector: (sel) => groupModalEls[sel] || null };

eval(pick('escapeHtml') + pick('findDeviceGroup') + constOf('DEVICE_GROUP_ICON_CHOICES')
   + constOf('GROUP_COLOR_VARS') + pick('renderGroupIconPicker') + pick('renderGroupColorPicker')
   + pick('closeGroupModal') + pick('showGroupModalError') + pick('apiErrorDetail')
   + pick('openGroupModal') + 'async ' + pick('submitGroupModal'));
"""


def test_submit_group_modal_edit_sends_patch_to_the_editing_id(tmp_path: Path) -> None:
    """With groupModalEditingId set (via a real openGroupModal('lights') call,
    not a hand-set global), Save must PATCH /api/device-groups/lights -- not
    POST a new group. This is the exact defect the reviewer introduced: making
    submitGroupModal always POST turns an edit into a silent duplicate."""
    script = f"""
{RESOLVE_JS}
{GROUP_MODAL_JS}
const calls = [];
globalThis.requestJson = async (url, options) => {{
  calls.push({{ url, method: options.method, body: options.body }});
  return {{}};
}};
globalThis.loadDeviceGroups = async () => {{}};
globalThis.loadDevices = () => Promise.resolve();

openGroupModal('lights');
submitGroupModal().then(() => {{
  console.log(JSON.stringify({{ calls }}));
}});
"""
    result = _run_node(script, tmp_path)

    assert len(result["calls"]) == 1
    assert result["calls"][0]["method"] == "PATCH"
    assert result["calls"][0]["url"] == "/api/device-groups/lights"


def test_submit_group_modal_create_sends_post_with_no_group_id(tmp_path: Path) -> None:
    """With groupModalEditingId cleared (via a real openGroupModal(null)),
    Save must POST to the bare collection endpoint, never a per-id URL."""
    script = f"""
{RESOLVE_JS}
{GROUP_MODAL_JS}
const calls = [];
globalThis.requestJson = async (url, options) => {{
  calls.push({{ url, method: options.method, body: options.body }});
  return {{}};
}};
globalThis.loadDeviceGroups = async () => {{}};
globalThis.loadDevices = () => Promise.resolve();

openGroupModal(null);
groupModalEls['#groupNameInput'].value = 'New Group';
submitGroupModal().then(() => {{
  console.log(JSON.stringify({{ calls }}));
}});
"""
    result = _run_node(script, tmp_path)

    assert len(result["calls"]) == 1
    assert result["calls"][0]["method"] == "POST"
    assert result["calls"][0]["url"] == "/api/device-groups"
    assert "/api/device-groups/" not in result["calls"][0]["url"]


def test_submit_group_modal_body_carries_name_icon_and_colour(tmp_path: Path) -> None:
    """The PATCH/POST body must reflect the modal's live state: the typed
    name, and whichever icon/colour the user has picked (not the group's
    original values, and not empty placeholders)."""
    script = f"""
{RESOLVE_JS}
{GROUP_MODAL_JS}
const calls = [];
globalThis.requestJson = async (url, options) => {{
  calls.push({{ url, method: options.method, body: JSON.parse(options.body) }});
  return {{}};
}};
globalThis.loadDeviceGroups = async () => {{}};
globalThis.loadDevices = () => Promise.resolve();

openGroupModal('lights');
groupModalEls['#groupNameInput'].value = 'Living Room Lights';
groupModalIcon = 'sun-high';
groupModalColor = 'teal';
submitGroupModal().then(() => {{
  console.log(JSON.stringify({{ body: calls[0].body }}));
}});
"""
    result = _run_node(script, tmp_path)

    assert result["body"] == {
        "name": "Living Room Lights",
        "icon": "sun-high",
        "color": "teal",
    }


def test_open_group_modal_edit_then_create_fully_resets_state(tmp_path: Path) -> None:
    """openGroupModal('lights') then openGroupModal(null) must leave no trace
    of the edit: groupModalEditingId cleared, save label and Delete visibility
    back to create defaults, and the name/icon/colour reset. A leaked editing
    id is exactly what turns a subsequent create into a silent overwrite."""
    script = f"""
{RESOLVE_JS}
{GROUP_MODAL_JS}
openGroupModal('lights');
const afterEdit = {{
  editingId: groupModalEditingId,
  saveLabel: groupModalEls['#groupSave'].textContent,
  deleteHidden: groupModalEls['#groupDelete'].hidden,
  nameValue: groupModalEls['#groupNameInput'].value,
  icon: groupModalIcon,
  color: groupModalColor,
}};

openGroupModal(null);
const afterCreate = {{
  editingId: groupModalEditingId,
  title: groupModalEls['#groupModalTitle'].textContent,
  saveLabel: groupModalEls['#groupSave'].textContent,
  deleteHidden: groupModalEls['#groupDelete'].hidden,
  nameValue: groupModalEls['#groupNameInput'].value,
  icon: groupModalIcon,
  color: groupModalColor,
}};

console.log(JSON.stringify({{ afterEdit, afterCreate }}));
"""
    result = _run_node(script, tmp_path)

    assert result["afterEdit"]["editingId"] == "lights"
    assert result["afterEdit"]["saveLabel"] == "Save"
    assert result["afterEdit"]["deleteHidden"] is False

    after_create = result["afterCreate"]
    assert after_create["editingId"] is None
    assert after_create["title"] == "New Group"
    assert after_create["saveLabel"] == "Create Group"
    assert after_create["deleteHidden"] is True
    assert after_create["nameValue"] == ""
    assert after_create["icon"] == "device-desktop"
    assert after_create["color"] == "slate"


def test_submit_group_modal_failed_save_shows_error_and_keeps_modal_open(tmp_path: Path) -> None:
    """A rejected save must surface the error in the modal's own error box and
    must NOT close the modal or refresh the group list -- the user's typed
    name/icon/colour would otherwise vanish along with the modal, and a
    refresh here would be indistinguishable from success."""
    script = f"""
{RESOLVE_JS}
{GROUP_MODAL_JS}
globalThis.requestJson = async () => {{ throw new Error('boom'); }};
globalThis.loadDeviceGroups = async () => {{ throw new Error('must not run when save failed'); }};
globalThis.loadDevices = () => {{ throw new Error('must not run when save failed'); }};

openGroupModal(null);
groupModalEls['#groupNameInput'].value = 'New Group';

submitGroupModal()
  .catch((error) => {{ throw new Error('save rejection must not propagate: ' + error.message); }})
  .then(() => {{
    console.log(JSON.stringify({{
      modalHidden: groupModalEls['#groupModal'].hidden,
      errorHidden: groupModalEls['#groupModalError'].hidden,
      errorText: groupModalEls['#groupModalErrorText'].textContent,
    }}));
  }});
"""
    result = _run_node(script, tmp_path)

    assert result["modalHidden"] is False, "a failed save must not close the modal"
    assert result["errorHidden"] is False, "the error box must be shown"
    assert result["errorText"] == "boom"


def test_dynamic_panel_helpers_exist_and_avoid_markup_strings() -> None:
    javascript = APP_JS.read_text(encoding="utf-8")

    assert "function ensureDeviceGroupPanel" in javascript
    assert "function renderDynamicGroupPanel" in javascript
    at = javascript.index("function ensureDeviceGroupPanel")
    depth, body = 0, None
    for j in range(javascript.index("{", at), len(javascript)):
        if javascript[j] == "{":
            depth += 1
        elif javascript[j] == "}":
            depth -= 1
            if depth == 0:
                body = javascript[at:j + 1]
                break

    # The group name is user-supplied via the API and must never be interpolated
    # into markup; it is set with textContent.
    assert "textContent" in body
    assert "createElement" in body


def test_view_panels_are_queried_fresh_not_snapshotted() -> None:
    """Panels are created at runtime for user-made groups. A module-load
    snapshot would never see them, so activateView's .active toggle would skip
    the new panel — it would render its content but never become visible. Same
    staleness class as railButtons, one line below it."""
    javascript = APP_JS.read_text(encoding="utf-8")

    assert "function viewPanelEls" in javascript
    assert "const viewPanels" not in javascript
    assert "viewPanels.forEach" not in javascript


def test_activate_view_toggles_a_runtime_created_panel(tmp_path: Path) -> None:
    """Behavioural proof: a panel added after module load still gets .active."""
    script = """
const panels = [];
function makePanel(view) {
  const el = { dataset: { viewPanel: view }, classList: {
    _on: new Set(),
    toggle(c, on) { on ? this._on.add(c) : this._on.delete(c); },
    contains(c) { return this._on.has(c); },
  } };
  panels.push(el);
  return el;
}
makePanel('devices');
globalThis.document = {
  querySelectorAll: (sel) => sel.includes('view-panel') ? panels : [],
  querySelector: () => null,
  body: { classList: { toggle() {} } },
};
eval(pick('viewPanelEls'));

// A group panel created AFTER the module-load snapshot would have been taken.
makePanel('movie-night');
const seen = viewPanelEls().map((p) => p.dataset.viewPanel);
viewPanelEls().forEach((p) => p.classList.toggle('active', p.dataset.viewPanel === 'movie-night'));
console.log(JSON.stringify({
  seen,
  runtimePanelActive: panels[1].classList.contains('active'),
  staticPanelActive: panels[0].classList.contains('active'),
}));
"""
    result = _run_node(script, tmp_path)

    assert result["seen"] == ["devices", "movie-night"]
    assert result["runtimePanelActive"] is True
    assert result["staticPanelActive"] is False


# ── Final whole-branch review fixes ──
#
# Fix 1: a custom group can never be the startup view, and never appears in the
#        startup dropdown, because initDefaultView built the dropdown and called
#        activateView(getDefaultView()) synchronously while loadDeviceGroups()
#        -- the only thing that adds a custom group's <li> to the nav -- was
#        fired and forgotten as the IIFE's last statement.
# Fix 2: the Devices overview grid never showed custom groups or Unassigned.
# Fix 3: a dynamic (custom/Unassigned) panel went stale while open, because it
#        only re-rendered when activateView navigated to it, not on the 60s
#        loadDevices() poll the seven built-in panels use.


def test_saved_custom_group_default_view_resolves_once_nav_synced(tmp_path: Path) -> None:
    """Regression test for Fix 1. Before the fix, initDefaultView built the
    dropdown and activated getDefaultView() synchronously -- before
    loadDeviceGroups() (fired-and-forgotten) had ever added the custom group's
    <li> to the nav -- so a saved default_view naming that group always fell
    back to "home", and the dropdown never listed it either. The fix must
    still activate something immediately (so the dashboard is not blank while
    the fetch is in flight), then correct course once the nav is synced."""
    script = """
globalThis.Node = { TEXT_NODE: 3 };
const roomItems = [
  { dataset: { view: "home" }, childNodes: [{ nodeType: 3, textContent: "Home" }] },
  { dataset: { view: "lights" }, childNodes: [{ nodeType: 3, textContent: "Lights" }] },
];
const selectEl = { innerHTML: "", value: "", options: [], selectedIndex: 0, addEventListener() {} };
globalThis.document = {
  querySelector: (sel) => (sel === "#defaultViewSelect" ? selectEl : null),
  querySelectorAll: (sel) => (sel === ".room-item[data-view]" ? roomItems : []),
};
const store = { default_view: "movie-night" };
globalThis.localStorage = {
  getItem: (k) => (k in store ? store[k] : null),
  setItem: (k, v) => { store[k] = String(v); },
};
const activateViewCalls = [];
globalThis.activateView = (view) => { activateViewCalls.push(view); };
globalThis.loadAmbientLights = async () => {};
globalThis.loadHumidifiers = async () => {};
globalThis.loadEnvironmentSensors = async () => {};
let loadDeviceGroupsResolve;
globalThis.loadDeviceGroups = () => new Promise((resolve) => { loadDeviceGroupsResolve = resolve; });

eval(constOf('DEFAULT_VIEW_KEY') + pick('railButtonEls') + pick('escapeHtml')
   + pick('getDefaultView') + pick('populateDefaultViewSelect') + pick('initDefaultView'));

async function run() {
  initDefaultView();
  const initialActivation = [...activateViewCalls];
  const initialSelectHtml = selectEl.innerHTML;

  // Simulate loadDeviceGroups()'s effect: syncDeviceGroupNav has now added
  // the custom group's <li> to the nav.
  roomItems.push({ dataset: { view: "movie-night" }, childNodes: [{ nodeType: 3, textContent: "Movie Night" }] });
  loadDeviceGroupsResolve();
  await Promise.resolve(); await Promise.resolve(); await Promise.resolve();

  console.log(JSON.stringify({
    initialActivation,
    initialSelectHtml,
    activateViewCalls,
    finalSelectHtml: selectEl.innerHTML,
    resolvedDefault: getDefaultView(),
  }));
}
run();
"""
    result = _run_node(script, tmp_path)

    assert result["initialActivation"] == ["home"], (
        "must activate something immediately so the dashboard is not blank while groups load"
    )
    assert 'value="movie-night"' not in result["initialSelectHtml"]
    assert result["activateViewCalls"] == ["home", "movie-night"], (
        "the saved custom-group view must be activated once the nav is synced, "
        "and home must not be re-activated a second time"
    )
    assert 'value="movie-night"' in result["finalSelectHtml"], (
        "the startup dropdown must be rebuilt to include the custom group"
    )
    assert result["resolvedDefault"] == "movie-night"


def test_device_group_tile_data_includes_dynamic_groups_and_keeps_builtins(tmp_path: Path) -> None:
    """Regression test for Fix 2. The overview grid must gain a tile for every
    group resolveDeviceGroups() returns -- a user-created group and the
    synthetic auto:unassigned bucket -- while the seven built-in tiles keep
    their exact existing label/icon/count/summary."""
    script = f"""
{RESOLVE_JS}
globalThis.latestDeviceGroups = [
  {{ id: 'lights', name: 'Lights', icon: 'bulb', color: 'amber', kinds: ['light'], builtin: true }},
  {{ id: 'climate', name: 'Climate', icon: 'temperature', color: 'orange', kinds: ['thermostat'], builtin: true }},
  {{ id: 'movie-night', name: 'Movie Night', icon: 'device-tv', color: 'purple', kinds: [], builtin: false }},
];
globalThis.latestDeviceGroupOverrides = {{}};
collectHomeInventory = () => ([
  {{ key: 'dev:1', kind: 'light', name: 'Hall light' }},
  {{ key: 'thermo:1', kind: 'thermostat', name: 'Upstairs' }},
  {{ key: 'plug:1', kind: 'plug', name: 'Spare plug' }},
]);
globalThis.latestSwitchDevices = [
  {{ host: 'h1', category: 'light_switch', name: 'Hall light', is_on: true, online: true }},
];
globalThis.latestMatterDevices = [];
globalThis.latestAmbientLights = [];
globalThis.latestHumidifiers = [];
globalThis.latestThermostats = [{{ id: 't1', name: 'Upstairs', online: true }}];
globalThis.latestEnvironmentSensors = [];
globalThis.sensorGroupCount = () => 0;
globalThis.sensorsTileGroups = () => [];
globalThis.environmentSummary = () => 'No readings';

eval(constOf('GROUP_COLOR_VARS') + constOf('GROUP_ICON_PATTERN') + constOf('BUILTIN_TILE_VIEWS')
   + pick('dynamicGroupTileData') + pick('deviceGroupTileData'));

const tiles = deviceGroupTileData();
console.log(JSON.stringify({{
  views: tiles.map((t) => t.view),
  lights: tiles.find((t) => t.view === 'lights'),
  plugs: tiles.find((t) => t.view === 'plugs'),
  movie: tiles.find((t) => t.view === 'movie-night'),
  unassigned: tiles.find((t) => t.view === 'auto:unassigned'),
}}));
"""
    result = _run_node(script, tmp_path)

    assert result["views"][:7] == [
        "lights", "plugs", "ambient", "humidifier", "environment", "tuya", "climate",
    ]
    assert "movie-night" in result["views"]
    assert "auto:unassigned" in result["views"]

    # The seven built-ins must keep their exact existing shape.
    assert result["lights"] == {
        "view": "lights", "label": "Lights", "icon": "ti-bulb", "count": 1, "summary": "1 of 1 on",
    }
    assert result["plugs"] == {
        "view": "plugs", "label": "Plugs", "icon": "ti-plug", "count": 0, "summary": "0 of 0 on",
    }

    movie = result["movie"]
    assert movie["label"] == "Movie Night"
    assert movie["icon"] == "ti-device-tv"
    assert movie["count"] == 0
    assert movie["summary"] == "0 devices"
    assert movie["color"] == "var(--purple)"

    unassigned = result["unassigned"]
    assert unassigned["label"] == "Unassigned"
    assert unassigned["count"] == 1
    assert unassigned["summary"] == "1 device"
    assert unassigned["color"] == "var(--slate)"


def test_active_dynamic_panel_refreshes_on_the_poll_path(tmp_path: Path) -> None:
    """Regression test for Fix 3. The seven built-in panels already refresh on
    every loadDevices() poll via their bespoke renderers; a dynamic group panel
    has none, so it must be re-rendered explicitly -- but only when it is the
    one currently on screen, and never when a built-in panel is active."""
    script = f"""
{RESOLVE_JS}
globalThis.latestDeviceGroups = [
  {{ id: 'lights', name: 'Lights', icon: 'bulb', color: 'amber', kinds: ['light'], builtin: true }},
  {{ id: 'movie-night', name: 'Movie Night', icon: 'device-tv', color: 'purple', kinds: [], builtin: false }},
];
globalThis.latestDeviceGroupOverrides = {{}};
collectHomeInventory = () => ([]);

function makePanel(view, active) {{
  return {{ dataset: {{ viewPanel: view }}, classList: {{
    _on: new Set(active ? ['active'] : []),
    contains(c) {{ return this._on.has(c); }},
  }} }};
}}
const panels = [makePanel('lights', true), makePanel('movie-night', false)];
globalThis.document = {{ querySelectorAll: (sel) => (sel.includes('view-panel') ? panels : []) }};

const renderCalls = [];
globalThis.renderDynamicGroupPanel = (id) => {{ renderCalls.push(id); }};

eval(pick('viewPanelEls') + pick('findDeviceGroup') + pick('refreshActiveDynamicGroupPanel'));

// Case 1: the built-in Lights panel is active -- must not render anything.
refreshActiveDynamicGroupPanel();
const afterBuiltinActive = [...renderCalls];

// Case 2: the custom Movie Night panel is active -- must render exactly it.
panels[0].classList._on.delete('active');
panels[1].classList._on.add('active');
resolveDeviceGroups.cache = null;
refreshActiveDynamicGroupPanel();

console.log(JSON.stringify({{ afterBuiltinActive, afterDynamicActive: renderCalls }}));
"""
    result = _run_node(script, tmp_path)

    assert result["afterBuiltinActive"] == [], "a built-in panel being active must not trigger a re-render"
    assert result["afterDynamicActive"] == ["movie-night"], (
        "the active dynamic panel must be re-rendered, and only that one"
    )


def test_activate_view_opens_the_synthetic_unassigned_panel(tmp_path: Path) -> None:
    """Clicking the Unassigned tile must show its devices and the back button.

    Regression: DEVICE_GROUP_VIEWS is built from the *persisted* groups, so the
    synthetic auto:unassigned bucket was never in it. activateView took the
    else branch — hiding the back button and never rendering the panel — and the
    panel itself could be missing entirely, because syncDeviceGroupNav() creates
    panels from loadDeviceGroups(), which can run before any devices load.
    """
    script = """
eval(pick('activateView'));

// Minimal DOM: only the devices panel exists, as when syncDeviceGroupNav() ran
// against an empty inventory and so never built an Unassigned panel.
const panels = [{ dataset: { viewPanel: 'devices' }, classList: { toggle(c, on) { this.on = on; } } }];
let createdPanelFor = null;
let backVisible = null;
let renderedPanel = null;

const railButtonEls = () => [];
const viewPanelEls = () => panels;
const DEVICE_GROUP_VIEWS = ['lights', 'plugs'];   // persisted groups only
const arrivedFromDevices = true;
const unassigned = { id: 'auto:unassigned', name: 'Unassigned', builtin: false,
                     synthetic: true, devices: [{ key: 'k', kind: 'switch' }] };
const findDeviceGroup = (id) => (id === 'auto:unassigned' ? unassigned : undefined);
const ensureDeviceGroupPanel = (g) => {
  createdPanelFor = g.id;
  panels.push({ dataset: { viewPanel: g.id }, classList: { toggle(c, on) { this.on = on; } } });
};
const setDevicesBackVisible = (v) => { backVisible = v; };
const renderDynamicGroupPanel = (v) => { renderedPanel = v; };
const renderDevicesOverview = () => {};
const loadAmbientLights = () => ({ catch() {} });
const loadHumidifiers = () => ({ catch() {} });
const loadEnvironmentSensors = () => ({ catch() {} });
const requestJson = () => ({ then() { return { catch() {} }; } });
const CSS = { escape: (s) => s };
const document = {
  body: { classList: { toggle() {} } },
  querySelector: () => null,
};

activateView('auto:unassigned');

console.log(JSON.stringify({
  createdPanelFor,
  backVisible,
  renderedPanel,
  activePanel: panels.find((p) => p.classList.on)?.dataset.viewPanel ?? null,
}));
"""
    result = _run_node(script, tmp_path)

    assert result["createdPanelFor"] == "auto:unassigned"
    assert result["backVisible"] is True, "back button must stay reachable"
    assert result["renderedPanel"] == "auto:unassigned", "panel contents must render"
    assert result["activePanel"] == "auto:unassigned", "panel must be created before the toggle"


def test_activate_view_hides_back_button_outside_device_groups(tmp_path: Path) -> None:
    """The synthetic-group fix must not arm the back button on ordinary views."""
    script = """
eval(pick('activateView'));
let backVisible = null;
const panels = [{ dataset: { viewPanel: 'cameras' }, classList: { toggle() {} } }];
const railButtonEls = () => [];
const viewPanelEls = () => panels;
const DEVICE_GROUP_VIEWS = ['lights'];
const arrivedFromDevices = true;
const findDeviceGroup = () => undefined;
const ensureDeviceGroupPanel = () => { throw new Error('must not build a panel'); };
const setDevicesBackVisible = (v) => { backVisible = v; };
const renderDynamicGroupPanel = () => {};
const renderDevicesOverview = () => {};
const CSS = { escape: (s) => s };
const document = { body: { classList: { toggle() {} } }, querySelector: () => null };

activateView('cameras');
console.log(JSON.stringify({ backVisible }));
"""
    assert _run_node(script, tmp_path)["backVisible"] is False
