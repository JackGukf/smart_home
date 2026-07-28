# Device Groups UI Implementation Plan (Cycle 2 of 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make device groups real — panels render membership instead of type filters, and the user can create, edit, delete groups and move any device between them.

**Architecture:** Cycle 1 built `resolveDeviceGroupMembers` but nothing calls it. This cycle wires it into every panel, adds a synthetic `auto:unassigned` bucket so deletion can never make a device invisible, and adds two modals. The mixed-device renderer is extracted from `renderAreaDetail` and shared rather than copied, so Areas and device groups cannot drift.

**Tech Stack:** Vanilla JS (no build step), FastAPI, pytest, Node for the existing JS test harness.

**Spec:** `docs/superpowers/specs/2026-07-26-device-groups-ui-design.md`

## Global Constraints

- **No visible change when there are no overrides.** With an empty overrides map, every panel must render exactly the device set it renders today. This is the regression gate for the whole cycle.
- No build step: `app.js`, `index.html`, `styles.css` served as-is. No frameworks, no bundler, no package.json, no new runtime dependencies. A JS syntax error ships straight to users — always run `node --check`.
- Icons come from the already-loaded Tabler webfont (`<i class="ti ti-*">`).
- Group ids are exactly `lights`, `plugs`, `ambient`, `humidifier` (singular), `environment`, `tuya` (the Sensors view), `climate`. Never rename `tuya`.
- Colour allowlist: `accent`, `amber`, `cyan`, `green`, `indigo`, `orange`, `pink`, `purple`, `red`, `slate`, `teal`. Icon pattern `^[a-z0-9-]{1,32}$`.
- `auto:unassigned` is synthetic: never persisted, never editable, never deletable, and rejected by the API as a group id.
- Every device-supplied string interpolated into HTML goes through `escapeHtml`. Colour reaches the DOM only via `style.setProperty` with a value from the allowlist table; icon only via `classList.add` after the pattern check.
- Python 3; `pyproject.toml` sets `pythonpath = ["."]`; run `python3 -m pytest` from the project root.
- Pre-existing unrelated failures: **4 failed, 7 errors** (matter_bridge C++ WIP in the tree, a docker-permissions test, a tplink test). Do not attempt to fix these.
- A post-commit hook auto-deploys to the Pi and bumps `BUILD_COUNT` / `build_info.json` / `index.html` cache-bust values. Never include those three in a commit; never revert them.

## File Structure

| File | Responsibility in this cycle |
|---|---|
| `src/python/web_static/app.js` | Shared generic renderer; `resolveDeviceGroups`; membership-driven panels; nav de-staleing; both modals; dynamic panels |
| `src/python/web_static/index.html` | Manage Devices + group modal markup; Manage/Edit buttons in the seven panel headers |
| `src/python/web_static/styles.css` | Modal row styles, colour swatch picker |
| `src/python/web_app.py` | Drop the built-in delete 409; reject `auto:unassigned` as a create id |
| `tests/python/test_device_groups_ui.py` | New — generic renderer, unassigned bucket, membership panels, modals |
| `tests/python/test_device_groups_api.py` | Extend — deletion and reserved-id changes |

---

### Task 1: Extract the shared generic mixed-device renderer

`renderAreaDetail` builds one subsection per device kind. Device groups need exactly the same thing. Extract it so the two cannot drift, changing Areas' behaviour not at all.

**Files:**
- Modify: `src/python/web_static/app.js` (`renderAreaDetail`, and a new function above it)
- Test: `tests/python/test_device_groups_ui.py` (create)

**Interfaces:**
- Consumes: `areaThermoCardHtml`, `ambientLightCard`, `humidifierCard`, `renderSensorDeviceCard`, `cameraCardHtml`, `environmentSensorCard`, `renderDeviceGroup` — all existing.
- Produces:
  - `genericGroupSectionsHtml(devices)` — takes an array of inventory entries `{key, kind, name, room, data}`, returns an HTML string of `.area-subsection` blocks, one per kind present, empty string when none.
  - `hydrateGenericGroupBody(bodyEl, devices)` — called after the HTML is inserted; populates the switch grid, which cannot be built as a string.

- [ ] **Step 1: Write the failing test**

Create `tests/python/test_device_groups_ui.py`:

```python
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
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m pytest tests/python/test_device_groups_ui.py -v`
Expected: FAIL — `missing function genericGroupSectionsHtml`.

- [ ] **Step 3: Add the shared renderer**

In `src/python/web_static/app.js`, immediately **before** `function renderAreaDetail`:

```js
/* ── Shared mixed-device renderer ──
   Used by both the Areas detail view and device group panels. Extracted rather
   than copied so the two cannot drift apart as kinds are added. Takes inventory
   entries ({key, kind, name, room, data}); returns subsection HTML. The switch
   grid cannot be built as a string, so hydrateGenericGroupBody finishes it. */
function genericGroupSectionsHtml(devices) {
  const of = (kind) => devices.filter((d) => d.kind === kind).map((d) => d.data);
  const switches    = devices.filter((d) => d.kind === "light" || d.kind === "plug").map((d) => d.data);
  const sensors     = of("sensor");
  const cameras     = of("camera");
  const thermostats = of("thermostat");
  const ambient     = of("ambient");
  const humidifiers = of("humidifier");
  const environment = of("environment");

  const sections = [];
  if (switches.length) {
    sections.push(`
      <div class="area-subsection">
        <div class="area-subsection-title"><i class="ti ti-bulb"></i> Lights &amp; Plugs</div>
        <div class="device-grid" id="areaSwitchGrid"></div>
      </div>`);
  }
  if (thermostats.length) {
    sections.push(`
      <div class="area-subsection">
        <div class="area-subsection-title"><i class="ti ti-temperature"></i> Climate</div>
        <div class="area-thermo-row">${thermostats.map(areaThermoCardHtml).join("")}</div>
      </div>`);
  }
  if (sensors.length) {
    sections.push(`
      <div class="area-subsection">
        <div class="area-subsection-title"><i class="ti ti-radar-2"></i> Sensors</div>
        <div class="device-grid">${sensors.map((g) => renderSensorDeviceCard(g, "sensors")).join("")}</div>
      </div>`);
  }
  if (cameras.length) {
    sections.push(`
      <div class="area-subsection">
        <div class="area-subsection-title"><i class="ti ti-video"></i> Cameras</div>
        <div class="camera-grid">${cameras.map((camera) => cameraCardHtml(camera)).join("")}</div>
      </div>`);
  }
  if (ambient.length) {
    sections.push(`
      <div class="area-subsection">
        <div class="area-subsection-title"><i class="ti ti-lamp-2"></i> Ambient Lights</div>
        <div class="ambient-grid">${ambient.map(ambientLightCard).join("")}</div>
      </div>`);
  }
  if (humidifiers.length) {
    sections.push(`
      <div class="area-subsection">
        <div class="area-subsection-title"><i class="ti ti-droplet"></i> Humidifiers</div>
        <div class="ambient-grid">${humidifiers.map(humidifierCard).join("")}</div>
      </div>`);
  }
  if (environment.length) {
    sections.push(`
      <div class="area-subsection">
        <div class="area-subsection-title"><i class="ti ti-temperature-celsius"></i> Environment</div>
        <div class="device-grid">${environment.map(environmentSensorCard).join("")}</div>
      </div>`);
  }
  return sections.join("");
}

function hydrateGenericGroupBody(bodyEl, devices) {
  const switches = devices.filter((d) => d.kind === "light" || d.kind === "plug").map((d) => d.data);
  const switchGrid = bodyEl?.querySelector("#areaSwitchGrid");
  if (switchGrid) renderDeviceGroup(switchGrid, switches, "No switches.");
}
```

- [ ] **Step 4: Make `renderAreaDetail` delegate**

In `renderAreaDetail`, delete the per-kind `const` filters and the whole `sections` construction, and replace everything from `const switches = ...` through the final `if (switchGrid) renderDeviceGroup(...)` with:

```js
  body.innerHTML = genericGroupSectionsHtml(area.devices);
  hydrateGenericGroupBody(body, area.devices);
```

Leave everything above that point — the icon, name, meta, delete-button and manage-button handling, and the empty-state early return — exactly as it is.

- [ ] **Step 5: Run tests and the syntax check**

Run: `node --check src/python/web_static/app.js`
Expected: no output, exit 0.

Run: `python3 -m pytest tests/python/test_device_groups_ui.py tests/python/test_device_groups_logic.py -v`
Expected: all pass. `test_render_area_detail_shows_environment_sensor` in the logic file exercises `renderAreaDetail` end to end and must still pass — that is the proof the extraction preserved Areas' behaviour.

- [ ] **Step 6: Commit**

```bash
git add src/python/web_static/app.js tests/python/test_device_groups_ui.py
git commit -m "refactor: extract the shared mixed-device renderer from renderAreaDetail"
```

---

### Task 2: Resolved groups and the implicit Unassigned bucket

**Files:**
- Modify: `src/python/web_static/app.js` (`loadDeviceGroups`, and new functions after `resolveDeviceGroupMembers`)
- Modify: `src/python/web_app.py` (create route — reject the reserved id)
- Test: `tests/python/test_device_groups_ui.py`, `tests/python/test_device_groups_api.py`

**Interfaces:**
- Consumes: `resolveDeviceGroupMembers(group, inventory, overrides)`, `collectHomeInventory()`, `latestDeviceGroups`.
- Produces:
  - `latestDeviceGroupOverrides` — module-level object, populated by `loadDeviceGroups`
  - `UNASSIGNED_GROUP_ID = "auto:unassigned"`
  - `resolveDeviceGroups()` — returns `[{...group, devices: [...inventory entries]}]`, with the synthetic Unassigned group appended last when and only when it has members
  - `findDeviceGroup(groupId)` — returns a resolved group or `undefined`

- [ ] **Step 1: Write the failing tests**

Append to `tests/python/test_device_groups_ui.py`:

```python
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
```

Append to `tests/python/test_device_groups_api.py`:

```python
def test_reserved_unassigned_id_is_rejected(tmp_path: Path) -> None:
    """auto:unassigned is synthetic; a real group must never shadow it."""
    client = _client(tmp_path)

    # "Auto Unassigned" slugs to "auto-unassigned", which is fine and distinct.
    assert client.post("/api/device-groups", json={"name": "Auto Unassigned"}).status_code == 200
    # The reserved id itself cannot be produced by the slugger, so guard the
    # explicit form the client could otherwise reach through the overrides API.
    assert client.put(
        "/api/device-groups/overrides",
        json={"device_key": "dev:1", "include": ["auto:unassigned"]},
    ).status_code == 404
```

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m pytest tests/python/test_device_groups_ui.py -v -k unassigned or load_stores`
Expected: FAIL — `missing const UNASSIGNED_GROUP_ID`.

- [ ] **Step 3: Store the overrides on load**

In `loadDeviceGroups`, add the overrides assignment. The function currently reads:

```js
async function loadDeviceGroups() {
  const payload = await requestJson("/api/device-groups");
  latestDeviceGroups = payload.groups || [];
```

Add immediately after that third line:

```js
  latestDeviceGroupOverrides = payload.overrides || {};
```

And declare it beside `latestDeviceGroups`:

```js
let latestDeviceGroupOverrides = {};
```

- [ ] **Step 4: Add the resolver and the synthetic bucket**

Immediately after `resolveDeviceGroupMembers`:

```js
/* Devices belonging to no group at all land here, so deleting a group can never
   make a device invisible. Mirrors the Areas feature's auto:unassigned bucket:
   synthetic, never persisted, shown only when non-empty, always sorted last. */
const UNASSIGNED_GROUP_ID = "auto:unassigned";

function resolveDeviceGroups() {
  const inventory = collectHomeInventory();
  const overrides = latestDeviceGroupOverrides || {};
  const groups = (latestDeviceGroups || []).map((group) => ({
    ...group,
    devices: resolveDeviceGroupMembers(group, inventory, overrides),
  }));

  const claimed = new Set();
  groups.forEach((group) => group.devices.forEach((device) => claimed.add(device.key)));
  const orphans = inventory.filter((item) => !claimed.has(item.key));
  if (orphans.length) {
    groups.push({
      id: UNASSIGNED_GROUP_ID,
      name: "Unassigned",
      icon: "help-hexagon",
      color: "slate",
      kinds: [],
      chrome: [],
      readingFilter: null,
      builtin: false,
      synthetic: true,
      devices: orphans,
    });
  }
  return groups;
}

function findDeviceGroup(groupId) {
  return resolveDeviceGroups().find((group) => group.id === groupId);
}
```

- [ ] **Step 5: Reject the reserved id server-side**

In `src/python/web_app.py`, inside the `device_groups_create` route, immediately after `group_id, name = _validated_name(body.name, doc)`:

```python
        if group_id == "auto:unassigned":
            raise HTTPException(status_code=400, detail="That group id is reserved")
```

The overrides route already 404s on an unknown group id, which covers
`auto:unassigned` because it is never in the document.

- [ ] **Step 6: Run tests and the syntax check**

Run: `node --check src/python/web_static/app.js`
Run: `python3 -m pytest tests/python/test_device_groups_ui.py tests/python/test_device_groups_api.py -v`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add src/python/web_static/app.js src/python/web_app.py tests/python/test_device_groups_ui.py tests/python/test_device_groups_api.py
git commit -m "feat: resolve device groups with an implicit Unassigned bucket"
```

---

### Task 3: Panels render membership

This is the task that activates the engine. It must change **which** devices each panel receives without changing **how** they are rendered.

**Files:**
- Modify: `src/python/web_static/app.js` — `renderDevices`, `renderAmbientLights`, `renderHumidifiers`, `renderTuyaDevices`, `renderEnvironmentSensors`, `renderThermostats`
- Test: `tests/python/test_device_groups_ui.py`

**Interfaces:**
- Consumes: `resolveDeviceGroups()`, `findDeviceGroup(id)`, `genericGroupSectionsHtml`, `hydrateGenericGroupBody`.
- Produces: `groupMemberData(groupId, kinds)` — the `data` objects of a group's members restricted to the given kinds; and `renderForeignKinds(groupId, nativeKinds, containerId)` — appends a generic section for members outside `nativeKinds`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/python/test_device_groups_ui.py`:

```python
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
        at = javascript.index(f"function {fn}")
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
    at = javascript.index("function renderDevices")
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
```

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m pytest tests/python/test_device_groups_ui.py -v -k member_data or membership_not_type`
Expected: FAIL — `missing function groupMemberData`.

- [ ] **Step 3: Add the two helpers**

Immediately after `findDeviceGroup`:

```js
/* The underlying device objects for a group's members, restricted to kinds the
   caller's renderer understands. Returns [] for an unknown group, so a deleted
   group degrades to an empty panel rather than throwing. */
function groupMemberData(groupId, kinds) {
  const wanted = new Set(kinds);
  const group = findDeviceGroup(groupId);
  if (!group) return [];
  return group.devices.filter((d) => wanted.has(d.kind)).map((d) => d.data);
}

/* Any device the user moved into a group whose bespoke renderer cannot display
   it. Rendered generically below the native content so nothing silently
   vanishes and no bespoke renderer is handed a shape it was not written for. */
function renderForeignKinds(groupId, nativeKinds, containerId) {
  const container = document.querySelector(containerId);
  if (!container) return;
  const existing = container.parentElement?.querySelector(".device-group-foreign");
  if (existing) existing.remove();

  const group = findDeviceGroup(groupId);
  if (!group) return;
  const native = new Set(nativeKinds);
  const foreign = group.devices.filter((d) => !native.has(d.kind));
  if (!foreign.length) return;

  const wrap = document.createElement("div");
  wrap.className = "device-group-foreign";
  wrap.innerHTML = genericGroupSectionsHtml(foreign);
  container.parentElement.appendChild(wrap);
  hydrateGenericGroupBody(wrap, foreign);
}
```

- [ ] **Step 4: Switch the switch panels to membership**

In `renderDevices`, the two device lists currently read:

```js
  const lightDevices = [...devices.filter((d) => d.category === "light_switch"), ...matterLights];
  const plugDevices  = [...devices.filter((d) => d.category === "smart_plug"),   ...matterPlugs];
```

Replace with:

```js
  const lightDevices = groupMemberData("lights", ["light"]);
  const plugDevices  = groupMemberData("plugs", ["plug"]);
```

Leave `deviceCount`, `onCount` and `cameraTabCount` sourced exactly as they are —
they describe every switch on the network, not one group's membership, and the
Status view would be wrong otherwise. `matterLights` and `matterPlugs` become
unused; delete those two lines.

At the end of `renderDevices`, after the existing grid rendering, add:

```js
  renderForeignKinds("lights", ["light"], "#lightGrid");
  renderForeignKinds("plugs", ["plug"], "#plugGrid");
```

- [ ] **Step 5: Switch the four remaining panels**

`renderAmbientLights` — replace `const lights = payload?.lights || [];` with:

```js
  latestAmbientLights = payload?.lights || [];
  const lights = groupMemberData("ambient", ["ambient"]);
```

and delete the now-duplicated `latestAmbientLights = lights;` line below it. Add at the end of the function:

```js
  renderForeignKinds("ambient", ["ambient"], "#ambientGrid");
```

`renderHumidifiers` — replace `const humidifiers = payload.humidifiers || [];` with:

```js
  latestHumidifiers = payload.humidifiers || [];
  const humidifiers = groupMemberData("humidifier", ["humidifier"]);
```

delete the duplicated `latestHumidifiers = humidifiers;`, and add at the end:

```js
  renderForeignKinds("humidifier", ["humidifier"], "#humidifierGrid");
```

`renderThermostats` — after `const thermostats = payload?.thermostats || [];` add:

```js
  latestThermostats = thermostats;
  const groupThermostats = groupMemberData("climate", ["thermostat"]);
```

and use `groupThermostats` for the grid rendering only. The `indoorTemp` stat and
`thermostatCount` keep using `thermostats`, for the same reason as the switch
stats. Add at the end:

```js
  renderForeignKinds("climate", ["thermostat"], "#thermostatGrid");
```

`renderTuyaDevices` — replace `const visibleDevices = devices.filter((d) => !isTuyaCamera(d));` with:

```js
  latestTuyaDevices = devices;
  const visibleDevices = groupMemberData("tuya", ["sensor"]).filter((d) => !isTuyaCamera(d));
```

Add at the end:

```js
  renderForeignKinds("tuya", ["sensor"], "#tuyaGrid");
```

`renderEnvironmentSensors` — replace the two source lines
(`const visible = latestTuyaDevices.filter(...)` and the `groups` line) with:

```js
  const visible = groupMemberData("environment", ["sensor"]).filter((d) => !isTuyaCamera(d));
  const groups = groupSensorDevices(visible).filter((g) => groupHasViewContent(g, "environment"));
```

and add at the end:

```js
  renderForeignKinds("environment", ["sensor", "environment"], "#environmentGrid");
```

**Important:** `groupMemberData("tuya", ["sensor"])` and
`groupMemberData("environment", ["sensor"])` return the grouped-sensor `data`
objects that `collectHomeInventory` produced, which are `{name, readings}`
groups — not raw entities. `renderTuyaDevices` currently takes raw entities and
calls `groupSensorDevices` itself. Keep that call working by passing the raw
entity list through: for the Sensors panel, resolve membership over the grouped
inventory and then flatten back to entities with
`.flatMap((g) => g.readings)` before the existing `groupSensorDevices` call.

- [ ] **Step 6: Add the foreign-section style**

In `src/python/web_static/styles.css`, after the `.area-subsection` rules:

```css
.device-group-foreign { margin-top: 18px; }
```

- [ ] **Step 7: Run the tests**

Run: `node --check src/python/web_static/app.js`
Run: `python3 -m pytest tests/python/ -q`
Expected: `4 failed, N passed, 7 errors` — the same 4 and 7. **Every dashboard test must still pass**, because with no overrides membership equals the old type filter. Any other failure means the swap was not behaviour-preserving; fix it rather than adjusting the test.

- [ ] **Step 8: Commit**

```bash
git add src/python/web_static/app.js src/python/web_static/styles.css tests/python/test_device_groups_ui.py
git commit -m "feat: render device group panels from membership rather than type"
```

---

### Task 4: Remove the railButtons staleness class

**Files:**
- Modify: `src/python/web_static/app.js` (`railButtons` at `:136`, `activateView`, the click registration, `getDefaultView`, `initDefaultView`, `syncDeviceGroupNav`)
- Test: `tests/python/test_device_groups_ui.py`

**Interfaces:**
- Produces: `railButtonEls()` — returns a fresh `Array` of `.room-item[data-view]` elements. `railButtons` is removed entirely.

- [ ] **Step 1: Write the failing tests**

Append to `tests/python/test_device_groups_ui.py`:

```python
def test_rail_buttons_are_queried_fresh_not_snapshotted() -> None:
    """A snapshot taken at module load cannot see nav items added later, which
    silently breaks active-class toggling and the startup-view dropdown."""
    javascript = APP_JS.read_text(encoding="utf-8")

    assert "function railButtonEls" in javascript
    assert "const railButtons = Array.from" not in javascript
    assert "railButtons.forEach" not in javascript


def test_sidebar_clicks_are_delegated_not_per_item() -> None:
    """One delegated listener cannot double-register or miss a new item."""
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
```

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m pytest tests/python/test_device_groups_ui.py -v -k rail or delegated`
Expected: FAIL — `function railButtonEls` not found.

- [ ] **Step 3: Replace the snapshot**

Replace line 136:

```js
const railButtons = Array.from(document.querySelectorAll(".room-item[data-view]"));
```

with:

```js
/* Queried fresh rather than snapshotted: groups can be created at runtime, and a
   module-load snapshot would silently miss their nav items. */
function railButtonEls() {
  return Array.from(document.querySelectorAll(".room-item[data-view]"));
}
```

- [ ] **Step 4: Update every consumer**

In `activateView`, replace `railButtons.forEach((btn) => {` with `railButtonEls().forEach((btn) => {`.

In `getDefaultView`, replace `railButtons.some((btn) => btn.dataset.view === saved)` with `railButtonEls().some((btn) => btn.dataset.view === saved)`.

In `initDefaultView`, replace `railButtons.map((btn) => {` with `railButtonEls().map((btn) => {`.

Replace the whole sidebar click registration block:

```js
/* Sidebar navigation */
railButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    arrivedFromDevices = false;
    activateView(btn.dataset.view);
  });
});
```

with a single delegated listener:

```js
/* Sidebar navigation — delegated, so nav items added at runtime work without
   registration and no item can be bound twice. */
document.addEventListener("click", (event) => {
  const item = event.target.closest(".room-item[data-view]");
  if (!item) return;
  if (event.target.closest(".settings-chevron")) return;
  arrivedFromDevices = false;
  activateView(item.dataset.view);
});
```

The chevron guard preserves the existing behaviour where clicking the Devices
chevron collapses the group without changing the active view.

- [ ] **Step 5: Remove the listener from `syncDeviceGroupNav`**

Delete this block from the item-creation branch:

```js
      item.addEventListener("click", () => {
        arrivedFromDevices = false;
        activateView(entry.id);
      });
```

The delegated listener now covers created items.

- [ ] **Step 6: Run the tests**

Run: `node --check src/python/web_static/app.js`
Run: `python3 -m pytest tests/python/ -q`
Expected: `4 failed, N passed, 7 errors` — the same 4 and 7. In particular `test_sidebar_click_clears_the_flag` in `test_devices_view_polish.py` asserts the old `railButtons.forEach` block; it will fail. Update that test to assert the delegated handler clears `arrivedFromDevices`, keeping the same intent.

- [ ] **Step 7: Commit**

```bash
git add src/python/web_static/app.js tests/python/test_device_groups_ui.py tests/python/test_devices_view_polish.py
git commit -m "refactor: query rail buttons fresh and delegate sidebar clicks"
```

---

### Task 5: Manage Devices modal

**Files:**
- Modify: `src/python/web_static/index.html` (new modal; Manage button in the seven panel headers)
- Modify: `src/python/web_static/app.js` (open/render/toggle)
- Modify: `src/python/web_static/styles.css` (row styles)
- Test: `tests/python/test_device_groups_ui.py`

**Interfaces:**
- Consumes: `resolveDeviceGroups()`, `findDeviceGroup`, `collectHomeInventory()`, `resolveDeviceGroupMembers`, `AREA_KIND_ICONS`, `latestDeviceGroupOverrides`.
- Produces:
  - `openManageDevicesModal(groupId)`, `renderManageDevicesList()`
  - `mergedOverrideFor(deviceKey, groupId, shouldBeMember)` — returns `{include, exclude}` for the whole device, preserving every other group's entries

- [ ] **Step 1: Write the failing tests**

Append to `tests/python/test_device_groups_ui.py`:

```python
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
```

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m pytest tests/python/test_device_groups_ui.py -v -k override_merge or toggle_transitions or manage_modal`
Expected: FAIL — `missing function mergedOverrideFor`.

- [ ] **Step 3: Add the modal markup**

In `src/python/web_static/index.html`, immediately after the closing `</div>` of `#assignModal`:

```html
<!-- ── MANAGE DEVICES (device group) MODAL ── -->
<div class="modal-overlay" id="manageDevicesModal" hidden aria-modal="true" role="dialog" aria-labelledby="manageDevicesTitle">
  <div class="modal-card assign-modal-card">
    <div class="modal-header">
      <span class="modal-title" id="manageDevicesTitle">Manage Devices</span>
      <button class="modal-close" id="closeManageDevices" type="button" aria-label="Close">
        <i class="ti ti-x"></i>
      </button>
    </div>
    <p class="assign-modal-hint">Tick a device to include it in this group. Devices matched by the group's rule are ticked automatically; your changes are stored as exceptions.</p>
    <div class="assign-device-list" id="manageDevicesList"></div>
    <div class="modal-actions">
      <button class="btn-primary" id="manageDevicesDone" type="button">Done</button>
    </div>
  </div>
</div>
```

- [ ] **Step 4: Add the Manage button to all seven panel headers**

Each of the seven device panels already has a `.section-actions` wrapper containing the back button. Add this as the wrapper's **second** child, immediately after the back button, in every one of `lights`, `plugs`, `ambient`, `humidifier`, `environment`, `tuya`, `climate` — substituting the group id for `GROUP_ID`:

```html
          <button class="command" type="button" data-manage-group="GROUP_ID">
            <i class="ti ti-list-check" aria-hidden="true"></i> Manage
          </button>
```

So the Lights panel gets `data-manage-group="lights"`, Sensors gets
`data-manage-group="tuya"` (the id, not the label), and so on.

- [ ] **Step 5: Add the merge helper and the modal logic**

In `app.js`, after `renderForeignKinds`:

```js
/* PUT /api/device-groups/overrides replaces a device's whole entry, so a toggle
   must resend that device's entries for every other group. Only deviations from
   the group's kind rule are stored, so changing a rule later still flows through
   to devices the user never touched. */
function mergedOverrideFor(deviceKey, groupId, shouldBeMember, ruleSaysMember) {
  const current = (latestDeviceGroupOverrides || {})[deviceKey] || {};
  const include = (current.include || []).filter((id) => id !== groupId);
  const exclude = (current.exclude || []).filter((id) => id !== groupId);

  if (shouldBeMember && !ruleSaysMember) include.push(groupId);
  if (!shouldBeMember && ruleSaysMember) exclude.push(groupId);

  return { include, exclude };
}

let manageDevicesGroupId = null;

function openManageDevicesModal(groupId) {
  const group = findDeviceGroup(groupId);
  if (!group) return;
  manageDevicesGroupId = groupId;
  const title = document.querySelector("#manageDevicesTitle");
  if (title) title.textContent = `Manage Devices — ${group.name}`;
  renderManageDevicesList();
  const modal = document.querySelector("#manageDevicesModal");
  if (modal) modal.hidden = false;
}

function renderManageDevicesList() {
  const list = document.querySelector("#manageDevicesList");
  const group = findDeviceGroup(manageDevicesGroupId);
  if (!list || !group) return;

  const inventory = collectHomeInventory().sort((a, b) =>
    a.kind === b.kind ? a.name.localeCompare(b.name) : a.kind.localeCompare(b.kind)
  );
  const memberKeys = new Set(group.devices.map((d) => d.key));
  const ruleKeys = new Set(
    resolveDeviceGroupMembers({ ...group, kinds: group.kinds }, inventory, {}).map((d) => d.key)
  );

  list.innerHTML = inventory.map((item) => {
    const isMember = memberKeys.has(item.key);
    const byRule = ruleKeys.has(item.key);
    const why = isMember ? (byRule ? "by rule" : "added") : (byRule ? "removed" : "");
    return `
      <div class="assign-device-row">
        <span class="assign-device-icon"><i class="ti ${AREA_KIND_ICONS[item.kind] || "ti-cpu"}"></i></span>
        <span class="assign-device-name">${escapeHtml(item.name)}</span>
        <span class="manage-device-why">${escapeHtml(why)}</span>
        <input class="manage-device-check" type="checkbox"
               data-manage-key="${escapeHtml(item.key)}"
               data-rule-member="${byRule ? "1" : "0"}"
               ${isMember ? "checked" : ""}
               aria-label="Include ${escapeHtml(item.name)} in this group">
      </div>`;
  }).join("");
}

async function toggleManageDevice(checkbox) {
  const deviceKey = checkbox.dataset.manageKey;
  const ruleSaysMember = checkbox.dataset.ruleMember === "1";
  const body = mergedOverrideFor(deviceKey, manageDevicesGroupId, checkbox.checked, ruleSaysMember);
  await requestJson("/api/device-groups/overrides", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ device_key: deviceKey, include: body.include, exclude: body.exclude }),
  });
  await loadDeviceGroups();
  renderManageDevicesList();
  loadDevices().catch((error) => console.error(error));
}
```

- [ ] **Step 6: Wire the events**

Add near the other top-level listeners:

```js
document.addEventListener("click", (event) => {
  const open = event.target.closest("[data-manage-group]");
  if (open) {
    openManageDevicesModal(open.dataset.manageGroup);
    return;
  }
  if (event.target.closest("#closeManageDevices") || event.target.closest("#manageDevicesDone")) {
    const modal = document.querySelector("#manageDevicesModal");
    if (modal) modal.hidden = true;
  }
});

document.addEventListener("change", (event) => {
  const checkbox = event.target.closest(".manage-device-check");
  if (checkbox) toggleManageDevice(checkbox).catch((error) => console.error(error));
});
```

- [ ] **Step 7: Add the row styles**

In `styles.css`, after the `.assign-device-row` rules:

```css
.manage-device-why {
  font-size: 11px;
  color: var(--muted);
  margin-left: auto;
  margin-right: 10px;
}

.manage-device-check { width: 16px; height: 16px; cursor: pointer; }
```

- [ ] **Step 8: Run the tests**

Run: `node --check src/python/web_static/app.js`
Run: `python3 -m pytest tests/python/ -q`
Expected: `4 failed, N passed, 7 errors` — the same 4 and 7.

- [ ] **Step 9: Commit**

```bash
git add src/python/web_static/ tests/python/test_device_groups_ui.py
git commit -m "feat: add the Manage Devices modal for device group membership"
```

---

### Task 6: New Group, Edit and Delete

**Files:**
- Modify: `src/python/web_static/index.html` (group modal; New Group tile in the Devices overview; Edit button in panel headers)
- Modify: `src/python/web_static/app.js` (modal logic; overview tile)
- Modify: `src/python/web_static/styles.css` (colour swatches)
- Modify: `src/python/web_app.py` (drop the built-in delete 409)
- Test: `tests/python/test_device_groups_ui.py`, `tests/python/test_device_groups_api.py`

**Interfaces:**
- Consumes: `GROUP_COLOR_VARS` (Cycle 1), `findDeviceGroup`, `loadDeviceGroups`.
- Produces: `DEVICE_GROUP_ICON_CHOICES`, `openGroupModal(groupId | null)`, `submitGroupModal()`, `deleteGroupFromModal()`

- [ ] **Step 1: Write the failing tests**

Append to `tests/python/test_device_groups_ui.py`:

```python
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
```

Append to `tests/python/test_device_groups_api.py`:

```python
def test_builtin_groups_are_now_deletable(tmp_path: Path) -> None:
    """Cycle 2 makes built-ins deletable; the synthetic Unassigned bucket is
    what stops their devices becoming invisible."""
    client = _client(tmp_path)

    assert client.delete("/api/device-groups/lights").status_code == 200
    remaining = [g["id"] for g in client.get("/api/device-groups").json()["groups"]]
    assert "lights" not in remaining


def test_deleting_a_group_cleans_up_its_overrides(tmp_path: Path) -> None:
    client = _client(tmp_path)
    client.put("/api/device-groups/overrides",
               json={"device_key": "dev:1", "include": ["lights"], "exclude": ["climate"]})

    client.delete("/api/device-groups/lights")

    overrides = client.get("/api/device-groups").json()["overrides"]
    assert overrides["dev:1"] == {"include": [], "exclude": ["climate"]}
```

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m pytest tests/python/test_device_groups_ui.py tests/python/test_device_groups_api.py -v -k group_modal or colour_swatches or deletable`
Expected: FAIL — `id="groupModal"` absent; the delete returns 409.

- [ ] **Step 3: Drop the built-in delete guard**

In `src/python/web_app.py`, in `device_groups_delete`, delete this block:

```python
        if group["builtin"]:
            raise HTTPException(
                status_code=409,
                detail="Built-in groups cannot be deleted; their device kinds would have no home.",
            )
```

`group` is then only used for the existence check, which `_find_group` already
performs, so change `group = _find_group(doc, group_id)` to `_find_group(doc, group_id)`.

- [ ] **Step 4: Add the modal markup**

In `index.html`, after `#manageDevicesModal`:

```html
<!-- ── DEVICE GROUP MODAL (create / edit) ── -->
<div class="modal-overlay" id="groupModal" hidden aria-modal="true" role="dialog" aria-labelledby="groupModalTitle">
  <div class="modal-card">
    <div class="modal-header">
      <span class="modal-title" id="groupModalTitle">New Group</span>
      <button class="modal-close" id="closeGroupModal" type="button" aria-label="Close">
        <i class="ti ti-x"></i>
      </button>
    </div>
    <label class="modal-label">
      Name
      <input class="modal-input" id="groupNameInput" type="text" placeholder="Movie Night" maxlength="40" autocomplete="off">
    </label>
    <div class="modal-label">
      Icon
      <div class="area-icon-picker" id="groupIconPicker"></div>
    </div>
    <div class="modal-label">
      Colour
      <div class="group-color-picker" id="groupColorPicker"></div>
    </div>
    <div class="modal-error" id="groupModalError" hidden><span id="groupModalErrorText"></span></div>
    <div class="modal-actions">
      <button class="btn-danger" id="groupDelete" type="button" hidden>Delete</button>
      <button class="btn-secondary" id="groupCancel" type="button">Cancel</button>
      <button class="btn-primary" id="groupSave" type="button">Create Group</button>
    </div>
  </div>
</div>
```

Add an Edit button to each of the seven panel headers, as the third child of
`.section-actions`, substituting the group id:

```html
          <button class="command" type="button" data-edit-group="GROUP_ID">
            <i class="ti ti-pencil" aria-hidden="true"></i> Edit
          </button>
```

Add a New Group tile to the Devices overview panel, immediately after the grid div:

```html
      <button class="device-group-add" id="deviceGroupAdd" type="button">
        <i class="ti ti-plus" aria-hidden="true"></i> New Group
      </button>
```

- [ ] **Step 5: Add the modal logic**

In `app.js`, after `toggleManageDevice`:

```js
const DEVICE_GROUP_ICON_CHOICES = [
  "bulb", "plug", "lamp-2", "droplet", "temperature-celsius", "radar-2",
  "temperature", "device-desktop", "movie", "coffee", "moon", "sun-high",
  "shield-lock", "music", "wifi", "home",
];

let groupModalEditingId = null;
let groupModalIcon = "device-desktop";
let groupModalColor = "slate";

function renderGroupIconPicker() {
  const picker = document.querySelector("#groupIconPicker");
  if (!picker) return;
  picker.innerHTML = DEVICE_GROUP_ICON_CHOICES.map((icon) => `
    <button class="area-icon-option${icon === groupModalIcon ? " selected" : ""}"
            type="button" data-group-icon="${escapeHtml(icon)}">
      <i class="ti ti-${escapeHtml(icon)}"></i>
    </button>`).join("");
}

function renderGroupColorPicker() {
  const picker = document.querySelector("#groupColorPicker");
  if (!picker) return;
  // Rendered from GROUP_COLOR_VARS so the picker cannot offer a colour the API
  // would reject, and cannot drift from the allowlist.
  picker.innerHTML = Object.keys(GROUP_COLOR_VARS).map((name) => `
    <button class="group-color-option${name === groupModalColor ? " selected" : ""}"
            type="button" data-group-color="${escapeHtml(name)}" aria-label="${escapeHtml(name)}"></button>`
  ).join("");
  picker.querySelectorAll("[data-group-color]").forEach((el) => {
    el.style.setProperty("background", GROUP_COLOR_VARS[el.dataset.groupColor]);
  });
}

function openGroupModal(groupId) {
  const group = groupId ? findDeviceGroup(groupId) : null;
  groupModalEditingId = group ? group.id : null;
  groupModalIcon = group ? group.icon : "device-desktop";
  groupModalColor = group ? group.color : "slate";

  const title = document.querySelector("#groupModalTitle");
  if (title) title.textContent = group ? `Edit ${group.name}` : "New Group";
  const input = document.querySelector("#groupNameInput");
  if (input) input.value = group ? group.name : "";
  const save = document.querySelector("#groupSave");
  if (save) save.textContent = group ? "Save" : "Create Group";
  const del = document.querySelector("#groupDelete");
  if (del) del.hidden = !group;
  const error = document.querySelector("#groupModalError");
  if (error) error.hidden = true;

  renderGroupIconPicker();
  renderGroupColorPicker();
  const modal = document.querySelector("#groupModal");
  if (modal) modal.hidden = false;
}

function closeGroupModal() {
  const modal = document.querySelector("#groupModal");
  if (modal) modal.hidden = true;
}

function showGroupModalError(message) {
  const box = document.querySelector("#groupModalError");
  const text = document.querySelector("#groupModalErrorText");
  if (text) text.textContent = message;
  if (box) box.hidden = false;
}

async function submitGroupModal() {
  const name = (document.querySelector("#groupNameInput")?.value || "").trim();
  const payload = { name, icon: groupModalIcon, color: groupModalColor };
  try {
    if (groupModalEditingId) {
      await requestJson(`/api/device-groups/${encodeURIComponent(groupModalEditingId)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    } else {
      await requestJson("/api/device-groups", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    }
  } catch (error) {
    showGroupModalError(apiErrorDetail(error));
    return;
  }
  closeGroupModal();
  await loadDeviceGroups();
  loadDevices().catch((err) => console.error(err));
}

async function deleteGroupFromModal() {
  if (!groupModalEditingId) return;
  const group = findDeviceGroup(groupModalEditingId);
  if (!window.confirm(`Delete the "${group ? group.name : groupModalEditingId}" group? Its devices move to Unassigned.`)) return;
  try {
    await requestJson(`/api/device-groups/${encodeURIComponent(groupModalEditingId)}`, { method: "DELETE" });
  } catch (error) {
    showGroupModalError(apiErrorDetail(error));
    return;
  }
  closeGroupModal();
  await loadDeviceGroups();
  activateView("devices");
  loadDevices().catch((err) => console.error(err));
}
```

- [ ] **Step 6: Wire the events**

```js
document.addEventListener("click", (event) => {
  if (event.target.closest("#deviceGroupAdd")) { openGroupModal(null); return; }
  const edit = event.target.closest("[data-edit-group]");
  if (edit) { openGroupModal(edit.dataset.editGroup); return; }
  if (event.target.closest("#closeGroupModal") || event.target.closest("#groupCancel")) { closeGroupModal(); return; }
  if (event.target.closest("#groupSave")) { submitGroupModal().catch(console.error); return; }
  if (event.target.closest("#groupDelete")) { deleteGroupFromModal().catch(console.error); return; }

  const icon = event.target.closest("[data-group-icon]");
  if (icon) { groupModalIcon = icon.dataset.groupIcon; renderGroupIconPicker(); return; }
  const color = event.target.closest("[data-group-color]");
  if (color) { groupModalColor = color.dataset.groupColor; renderGroupColorPicker(); }
});
```

- [ ] **Step 7: Add the swatch styles**

**`.btn-danger` does not exist in `styles.css`** — only `.btn-primary` and
`.btn-secondary` do. The Delete button needs it, so add it here, mirroring
`.btn-secondary` (`styles.css:3278`) and differing only in colour:

```css
.btn-danger {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border: 1px solid var(--red);
  border-radius: var(--radius-sm);
  background: none;
  color: var(--red);
  cursor: pointer;
  margin-right: auto;
}

.btn-danger:hover { background: var(--card-2); }

.group-color-picker { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 6px; }

.group-color-option {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  border: 2px solid transparent;
  cursor: pointer;
  padding: 0;
}

.group-color-option.selected { border-color: var(--text); }

.device-group-add {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: 16px;
  padding: 10px 16px;
  background: var(--card);
  border: 1px dashed var(--border-hover);
  border-radius: var(--radius-sm);
  color: var(--muted);
  cursor: pointer;
  font-size: 13px;
}

.device-group-add:hover { background: var(--card-2); color: var(--text); }
```

- [ ] **Step 8: Run the tests**

Run: `node --check src/python/web_static/app.js`
Run: `python3 -m pytest tests/python/ -q`
Expected: `4 failed, N passed, 7 errors` — the same 4 and 7. Note the Cycle 1 test `test_delete_refuses_builtin_but_allows_user_groups` in `test_device_groups_api.py` asserts the old 409; update it to assert 200 for a built-in, keeping the user-group and 404 halves.

- [ ] **Step 9: Commit**

```bash
git add src/python/web_static/ src/python/web_app.py tests/python/
git commit -m "feat: add group create, edit and delete, and allow deleting built-ins"
```

---

### Task 7: Dynamic panels for groups without static markup

**Files:**
- Modify: `src/python/web_static/app.js` (`syncDeviceGroupNav` companion; `activateView`)
- Test: `tests/python/test_device_groups_ui.py`

**Interfaces:**
- Consumes: `resolveDeviceGroups()`, `genericGroupSectionsHtml`, `hydrateGenericGroupBody`, `UNASSIGNED_GROUP_ID`.
- Produces: `ensureDeviceGroupPanel(group)` — creates the panel element if absent and returns it; `renderDynamicGroupPanel(groupId)`.

- [ ] **Step 1: Write the failing test**

Append to `tests/python/test_device_groups_ui.py`:

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest tests/python/test_device_groups_ui.py -v -k dynamic_panel`
Expected: FAIL — `function ensureDeviceGroupPanel` not found.

- [ ] **Step 3: Add the panel builder**

After `renderDynamicGroupPanel`'s intended location — that is, after `renderForeignKinds` in `app.js`:

```js
/* A group with no static panel (any user-created group, and Unassigned) gets one
   built on demand. The name is user-supplied via the API, so it is set with
   textContent rather than interpolated into markup. */
function ensureDeviceGroupPanel(group) {
  const existing = document.querySelector(`[data-view-panel="${CSS.escape(group.id)}"]`);
  if (existing) return existing;

  const host = document.querySelector('[data-view-panel="devices"]')?.parentElement;
  if (!host) return null;

  const panel = document.createElement("div");
  panel.className = "view-panel";
  panel.dataset.viewPanel = group.id;

  const header = document.createElement("div");
  header.className = "section-header";
  const title = document.createElement("span");
  title.className = "section-title";
  title.textContent = group.name;
  header.appendChild(title);

  const actions = document.createElement("div");
  actions.className = "section-actions";

  const back = document.createElement("button");
  back.className = "command device-back-btn";
  back.type = "button";
  back.setAttribute("data-back-to-devices", "");
  back.hidden = true;
  back.innerHTML = '<i class="ti ti-arrow-left" aria-hidden="true"></i> Devices';
  actions.appendChild(back);

  if (group.id !== UNASSIGNED_GROUP_ID) {
    const manage = document.createElement("button");
    manage.className = "command";
    manage.type = "button";
    manage.dataset.manageGroup = group.id;
    manage.innerHTML = '<i class="ti ti-list-check" aria-hidden="true"></i> Manage';
    actions.appendChild(manage);

    const edit = document.createElement("button");
    edit.className = "command";
    edit.type = "button";
    edit.dataset.editGroup = group.id;
    edit.innerHTML = '<i class="ti ti-pencil" aria-hidden="true"></i> Edit';
    actions.appendChild(edit);
  }

  header.appendChild(actions);
  panel.appendChild(header);

  const body = document.createElement("div");
  body.className = "device-group-body";
  panel.appendChild(body);

  host.appendChild(panel);
  return panel;
}

function renderDynamicGroupPanel(groupId) {
  const group = findDeviceGroup(groupId);
  if (!group) return;
  const panel = ensureDeviceGroupPanel(group);
  const body = panel?.querySelector(".device-group-body");
  if (!body) return;
  if (!group.devices.length) {
    body.innerHTML = '<div class="empty">No devices in this group yet. Use Manage to add some.</div>';
    return;
  }
  body.innerHTML = genericGroupSectionsHtml(group.devices);
  hydrateGenericGroupBody(body, group.devices);
}
```

- [ ] **Step 4: Create panels during nav sync and render on activate**

At the end of `syncDeviceGroupNav`, before its closing brace, add:

```js
  // Groups with no static markup need a panel to navigate into.
  resolveDeviceGroups().forEach((group) => {
    if (!document.querySelector(`[data-view-panel="${CSS.escape(group.id)}"]`)) {
      ensureDeviceGroupPanel(group);
    }
  });
```

In `activateView`, inside the existing `if (DEVICE_GROUP_VIEWS.includes(viewName))` block, add:

```js
    if (!document.querySelector(`[data-view-panel="${CSS.escape(viewName)}"] .device-grid, [data-view-panel="${CSS.escape(viewName)}"] .ambient-grid`)) {
      renderDynamicGroupPanel(viewName);
    }
```

This renders only panels that have no static grid of their own, leaving the seven
built-in panels to their bespoke renderers.

- [ ] **Step 5: Include Unassigned in the nav**

`syncDeviceGroupNav` currently plans from `latestDeviceGroups`. Change its plan
source to include the synthetic bucket:

```js
  deviceGroupNavPlan(resolveDeviceGroups()).forEach((entry) => {
```

Because `resolveDeviceGroups` appends Unassigned only when non-empty, the nav
item appears and disappears with its contents.

- [ ] **Step 6: Run the tests**

Run: `node --check src/python/web_static/app.js`
Run: `python3 -m pytest tests/python/ -q`
Expected: `4 failed, N passed, 7 errors` — the same 4 and 7.

- [ ] **Step 7: Commit**

```bash
git add src/python/web_static/app.js tests/python/test_device_groups_ui.py
git commit -m "feat: build panels on demand for groups without static markup"
```

---

## Self-Review

**Spec coverage:**

| Spec section | Task |
|---|---|
| Part 1 — panels render membership | 3 |
| Part 1 — foreign kinds in a generic section | 3 (`renderForeignKinds`) |
| Part 2 — implicit Unassigned bucket, hidden when empty, sorted last | 2, and 7 for its nav item |
| Part 2 — reserved id rejected | 2 |
| Part 3 — Manage Devices, membership reasons, toggle table | 5 |
| Part 3 — the override merge requirement | 5 (`mergedOverrideFor`, dedicated test) |
| Part 3 — sensor-split devices now manageable | 5 — Environment and Sensors are independent checkboxes |
| Part 4 — group modal, icon and colour pickers, delete | 6 |
| Part 4 — generic renderer extracted and shared | 1 |
| Part 4 — dynamic panels | 7 |
| Part 5 — built-ins deletable | 6 |
| Part 6 — railButtons staleness removed | 4 |

No spec requirement is unassigned.

**Placeholder scan:** no TBD/TODO. Every code step carries complete code, including all seven repeated button insertions described with their exact substitution.

**Type consistency:** `genericGroupSectionsHtml(devices)` / `hydrateGenericGroupBody(bodyEl, devices)` are defined in Task 1 and consumed in Tasks 3 and 7. `resolveDeviceGroups()` / `findDeviceGroup(id)` / `UNASSIGNED_GROUP_ID` are defined in Task 2 and consumed in Tasks 3, 5, 6 and 7. `groupMemberData(groupId, kinds)` and `renderForeignKinds(groupId, nativeKinds, containerId)` are defined in Task 3. `mergedOverrideFor(deviceKey, groupId, shouldBeMember, ruleSaysMember)` takes four arguments in both its definition and its tests. `latestDeviceGroupOverrides` is declared in Task 2 and read in Tasks 2 and 5.

**Three risks worth naming for the executor:**

1. **Task 3 is the behaviour-preserving swap and carries the most risk.** The sensor panels are the subtlest: `collectHomeInventory` produces *grouped* sensor objects, while `renderTuyaDevices` expects raw entities and groups them itself. Task 3 Step 5 spells out the flatten-back, but this is the place to be most careful, and the full suite passing is the gate.

2. **Two Cycle 1 tests must be updated, not deleted.** `test_sidebar_click_clears_the_flag` (Task 4) asserts the `railButtons.forEach` block that Task 4 removes; `test_delete_refuses_builtin_but_allows_user_groups` (Task 6) asserts the 409 that Task 6 removes. Both are called out in their tasks with the intent to preserve.

3. **Global stats must not become group-scoped.** `deviceCount`, `onCount` and `indoorTemp` describe the whole home, not a group. Task 3 has a dedicated test asserting `groupMemberData` does not appear in the stats block of `renderDevices`.
