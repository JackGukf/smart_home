# Devices Group + Environment + Govee H5140 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse the six device views under a new Devices sidebar group, split temperature/humidity readings out of Sensors into a new Environment view, and connect a Govee H5140 thermo-hygrometer to it.

**Architecture:** Frontend-only for Parts 1-2 — the Devices overview renders from arrays already in memory and reuses the existing document-level `[data-goto-view]` handler, so no new endpoints or fetches. The Environment split is one pure filter function applied to sensor readings before the existing card renderer, so both views share one card implementation. The H5140 adds a config section and one read-only endpoint built on `_govee_thermometer_reading()`, which already parses Govee thermo-hygrometer capabilities.

**Tech Stack:** Vanilla JS (no framework, no build step), FastAPI, PyYAML, pytest, Tabler Icons (`ti ti-*`).

**Spec:** `docs/superpowers/specs/2026-07-24-devices-group-environment-design.md`

## Global Constraints

- Python 3, `pythonpath = ["."]` from `pyproject.toml` — tests import `src.python.*`.
- Never commit real device IDs, API keys, or credentials. Real config is `configs/devices.local.yaml` (git-ignored); only `configs/devices.example.yaml` is committed, using `replace_me` placeholders.
- The Govee API key comes from the `GOVEE_API_KEY` environment variable, never from config files.
- Config sections must tolerate being `null` or absent — the fix pattern established in commit `d11e07e`.
- No build step: `app.js`, `index.html` and `styles.css` are served as-is. No frameworks, no bundler, no new runtime dependencies.
- Icons come from the already-loaded Tabler set (`<i class="ti ti-*">`). Do not add icon libraries.
- All seven device views keep their existing `data-view` values: `lights`, `plugs`, `ambient`, `humidifier`, `tuya`, `climate`, plus new `environment`.
- Run `python3 -m pytest` from the project root.

---

### Task 1: Repair the pre-existing dashboard-layout test failures

`test_ambient_view_is_hidden_but_backend_is_preserved` has been failing since commit `efeda71` re-added the Ambient view without updating it. `test_status_view_is_last_view_item` parses `<li class="room-item"` as a literal string, which stops matching once an `<li>` has a second class — later tasks add `device-group-item` to seven items, which would silently shrink what the test checks. Fix both before touching the markup.

**Files:**
- Modify: `tests/python/test_dashboard_layout.py:30-54`

**Interfaces:**
- Consumes: nothing.
- Produces: a green `test_dashboard_layout.py` that later tasks can rely on, and a `_sidebar_view_order(html)` helper that tolerates multi-class `<li>` items.

- [ ] **Step 1: Confirm the failure exists before changing anything**

Run: `python3 -m pytest tests/python/test_dashboard_layout.py -q`
Expected: `1 failed, 3 passed` — the failure is `test_ambient_view_is_hidden_but_backend_is_preserved`, asserting `'data-view="ambient"' not in html`.

- [ ] **Step 2: Replace both tests**

Replace lines 30-54 of `tests/python/test_dashboard_layout.py` (from `def test_status_view_is_last_view_item` to end of file) with:

```python
import re


def _sidebar_view_order(html: str) -> list[str]:
    """Views in the sidebar's Views section, in source order.

    Tolerates <li> items carrying extra classes (e.g. device-group-item);
    a literal '<li class="room-item"' match would silently skip them.
    """
    views_start = html.index('<div class="sidebar-section">Views</div>')
    # Discovery is its own section between Views and System; scan only the Views <ul>.
    discovery_start = html.index('<div class="sidebar-section">Discovery</div>')
    views_markup = html[views_start:discovery_start]
    return re.findall(r'<li[^>]*\bclass="[^"]*\broom-item\b[^"]*"[^>]*\bdata-view="([^"]+)"', views_markup)


def test_status_view_is_last_view_item() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert _sidebar_view_order(html)[-1] == "status"


def test_sidebar_view_order_helper_sees_multi_class_items() -> None:
    """Guards the helper itself: a second class must not hide an item."""
    markup = (
        '<div class="sidebar-section">Views</div>'
        '<li class="room-item" data-view="home">Home</li>'
        '<li class="room-item device-group-item" data-view="lights">Lights</li>'
        '<div class="sidebar-section">Discovery</div>'
    )

    assert _sidebar_view_order(markup) == ["home", "lights"]


def test_ambient_view_is_present_and_backend_is_preserved() -> None:
    """Ambient was hidden once, then restored in efeda71. Both halves must hold."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    backend = WEB_APP.read_text(encoding="utf-8")

    assert 'data-view="ambient"' in html
    assert 'data-view-panel="ambient"' in html
    assert 'id="ambientGrid"' in html
    assert '@app.get("/api/ambient-lights")' in backend
```

Note the `import re` belongs at the top of the file with the existing `from pathlib import Path`; move it there rather than leaving it mid-file.

- [ ] **Step 3: Run the tests**

Run: `python3 -m pytest tests/python/test_dashboard_layout.py -q`
Expected: `5 passed`.

- [ ] **Step 4: Commit**

```bash
git add tests/python/test_dashboard_layout.py
git commit -m "test: repair stale ambient assertion and harden sidebar view-order parse"
```

---

### Task 2: Devices sidebar group and overview panel

Adds the Devices parent, indents the six existing children, adds the overview panel, and wires collapse/persist. Environment is added in Task 3; this task ships six children.

**Files:**
- Modify: `src/python/web_static/index.html:43-101` (sidebar), and insert a new panel before the Home panel at `:289`
- Modify: `src/python/web_static/styles.css` (near `:330` for indentation, near `:377` for icon colour, inside the `max-width: 900px` block at `:2202`)
- Modify: `src/python/web_static/app.js` (new render + collapse functions; `activateView` at `:4306`)
- Test: `tests/python/test_dashboard_devices_group.py` (create)

**Interfaces:**
- Consumes: `_sidebar_view_order(html)` from Task 1 (for tests).
- Produces:
  - CSS class `device-group-item` on each child `<li>`.
  - `#devicesGroupToggle` — the parent `<li>`, `data-view="devices"`.
  - `#deviceGroupCount` — the badge element.
  - `renderDevicesOverview()` — no args, no return; repaints `#devicesOverviewGrid`.
  - `setDevicesGroupOpen(open: boolean)` — toggles child visibility and persists.
  - `localStorage` key `devices_group_open_v1`.
  - Panel `data-view-panel="devices"`, tile grid `#devicesOverviewGrid`.

- [ ] **Step 1: Write the failing test**

Create `tests/python/test_dashboard_devices_group.py`:

```python
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML = PROJECT_ROOT / "src" / "python" / "web_static" / "index.html"
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"
STYLES_CSS = PROJECT_ROOT / "src" / "python" / "web_static" / "styles.css"

DEVICE_CHILD_VIEWS = ["lights", "plugs", "ambient", "humidifier", "tuya", "climate"]


def test_devices_parent_exists_with_badge_and_chevron() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="devicesGroupToggle"' in html
    assert 'data-view="devices"' in html
    assert 'id="deviceGroupCount"' in html
    assert "settings-chevron" in html[html.index('id="devicesGroupToggle"'):][:400]


def test_device_children_are_marked_and_sit_under_devices() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    views_start = html.index('<div class="sidebar-section">Views</div>')
    discovery_start = html.index('<div class="sidebar-section">Discovery</div>')
    views = html[views_start:discovery_start]

    devices_at = views.index('data-view="devices"')
    ha_at = views.index('data-view="homeassistant"')

    for view in DEVICE_CHILD_VIEWS:
        at = views.index(f'data-view="{view}"')
        assert devices_at < at < ha_at, f"{view} must sit between Devices and Home Asst"

    children = re.findall(r'<li[^>]*\bdevice-group-item\b[^>]*\bdata-view="([^"]+)"', views)
    assert children == DEVICE_CHILD_VIEWS


def test_top_level_views_are_untouched() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    views_start = html.index('<div class="sidebar-section">Views</div>')
    discovery_start = html.index('<div class="sidebar-section">Discovery</div>')
    views = html[views_start:discovery_start]

    for view in ["home", "cameras", "homeassistant", "alarm", "status"]:
        item = re.search(rf'<li[^>]*\bdata-view="{view}"', views)
        assert item is not None
        assert "device-group-item" not in item.group(0)


def test_devices_overview_panel_has_a_tile_per_child() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'data-view-panel="devices"' in html
    assert 'id="devicesOverviewGrid"' in html


def test_overview_tiles_reuse_the_existing_goto_view_handler() -> None:
    javascript = APP_JS.read_text(encoding="utf-8")

    assert "renderDevicesOverview" in javascript
    # Tiles must navigate via the existing document-level handler, not a new one.
    assert "data-goto-view" in javascript
    for view in DEVICE_CHILD_VIEWS:
        assert f'"{view}"' in javascript


def test_group_state_is_persisted() -> None:
    javascript = APP_JS.read_text(encoding="utf-8")

    assert "devices_group_open_v1" in javascript
    assert "setDevicesGroupOpen" in javascript


def test_mobile_rail_flattens_the_group() -> None:
    css = STYLES_CSS.read_text(encoding="utf-8")

    assert ".device-group-item" in css
    assert "#devicesGroupToggle { display: none; }" in css
    # The un-hide rule must come after .room-item[hidden] to win at equal specificity.
    assert css.index(".device-group-item[hidden]") > css.index(".room-item[hidden]")
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `python3 -m pytest tests/python/test_dashboard_devices_group.py -q`
Expected: 7 failures, first being `ValueError: substring not found` on `id="devicesGroupToggle"`.

- [ ] **Step 3: Add the parent and mark the children in `index.html`**

In `src/python/web_static/index.html`, insert directly after the Cameras `</li>` (currently line 53) and before the Lights `<li>`:

```html
      <li class="room-item" id="devicesGroupToggle" data-view="devices">
        <span class="room-icon"><i class="ti ti-devices"></i></span>
        Devices
        <span class="room-badge" id="deviceGroupCount">–</span>
        <i class="ti ti-chevron-right settings-chevron" aria-hidden="true"></i>
      </li>
```

Then add `device-group-item` to each of the six children. Change each opening tag as follows (leave the inner markup of each `<li>` exactly as it is):

```
<li class="room-item" data-view="lights">      -> <li class="room-item device-group-item" data-view="lights">
<li class="room-item" data-view="plugs">       -> <li class="room-item device-group-item" data-view="plugs">
<li class="room-item" data-view="ambient">     -> <li class="room-item device-group-item" data-view="ambient">
<li class="room-item" data-view="humidifier">  -> <li class="room-item device-group-item" data-view="humidifier">
<li class="room-item" data-view="tuya">        -> <li class="room-item device-group-item" data-view="tuya">
<li class="room-item" data-view="climate">     -> <li class="room-item device-group-item" data-view="climate">
```

- [ ] **Step 4: Add the overview panel to `index.html`**

Insert immediately before `<!-- ── HOME (AREAS) VIEW ── -->` (currently line 288):

```html
    <!-- ── DEVICES OVERVIEW VIEW ── -->
    <div class="view-panel" data-view-panel="devices">
      <div class="section-header">
        <span class="section-title">Devices</span>
        <span class="section-meta">All device groups</span>
      </div>
      <div class="devices-overview-grid" id="devicesOverviewGrid"></div>
    </div>
```

- [ ] **Step 5: Add the CSS**

In `src/python/web_static/styles.css`, immediately after `.system-settings-item { padding-left: 24px; }` (line 330):

```css
.device-group-item { padding-left: 24px; }

#devicesGroupToggle.open .settings-chevron { transform: rotate(90deg); }
```

After the per-view icon colour block (line 382, after the `cameras` rule):

```css
.room-item[data-view="devices"]     .room-icon { color: var(--accent); }
```

After `.sidebar-footer` (line 410), the overview tile styles:

```css
/* ── Devices overview tiles ── */
.devices-overview-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 14px;
}

.device-group-tile {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 18px;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
}

.device-group-tile:hover {
  background: var(--card-2);
  border-color: var(--border-hover);
}

.device-group-tile-head {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--muted);
  font-size: 13px;
  font-weight: 500;
}

.device-group-tile-count {
  font-family: var(--mono);
  font-size: 26px;
  color: var(--text);
}

.device-group-tile-summary {
  font-size: 11px;
  color: var(--muted);
}
```

Inside the existing `@media (max-width: 900px)` block (which starts at line 2202), just before its closing brace after `.thermo-presets { flex-wrap: wrap; }`:

```css
  /* Rail has no room for indentation or chevrons: flatten the Devices group. */
  #devicesGroupToggle { display: none; }
  .device-group-item[hidden] { display: flex; }
  .devices-overview-grid { grid-template-columns: repeat(2, 1fr); }
```

The `.device-group-item[hidden]` rule sits later in the file than `.room-item[hidden]` (line 318), so it wins at equal specificity.

- [ ] **Step 6: Add the JavaScript**

In `src/python/web_static/app.js`, add after the `initSidebarCollapsibles` IIFE (which ends at line 244):

```js
/* ── Devices sidebar group ── */
const DEVICES_GROUP_KEY = "devices_group_open_v1";
const DEVICE_GROUP_VIEWS = ["lights", "plugs", "ambient", "humidifier", "tuya", "climate"];

function isDevicesGroupOpen() {
  try {
    return localStorage.getItem(DEVICES_GROUP_KEY) !== "0";
  } catch {
    return true;
  }
}

function setDevicesGroupOpen(open) {
  const toggle = document.querySelector("#devicesGroupToggle");
  toggle?.classList.toggle("open", open);
  document.querySelectorAll(".device-group-item").forEach((item) => {
    item.hidden = !open;
  });
  try { localStorage.setItem(DEVICES_GROUP_KEY, open ? "1" : "0"); } catch {}
}

(function initDevicesGroup() {
  const toggle = document.querySelector("#devicesGroupToggle");
  if (!toggle) return;
  setDevicesGroupOpen(isDevicesGroupOpen());

  // Chevron toggles collapse without changing the active view; the row itself
  // opens the overview and always expands.
  toggle.querySelector(".settings-chevron")?.addEventListener("click", (event) => {
    event.stopPropagation();
    setDevicesGroupOpen(!isDevicesGroupOpen());
  });
})();
```

Add the overview renderer next to it:

```js
/* Devices overview tiles. Renders from arrays already in memory — no fetches. */
function deviceGroupTileData() {
  const lights = latestSwitchDevices.filter((d) => d.category === "light_switch");
  const plugs  = latestSwitchDevices.filter((d) => d.category === "smart_plug");
  const onOf = (list) => `${list.filter((d) => d.is_on).length} of ${list.length} on`;
  const onlineOf = (list) => `${list.filter((d) => d.online !== false).length} online`;

  return [
    { view: "lights",     label: "Lights",      icon: "ti-bulb",       count: lights.length,                 summary: onOf(lights) },
    { view: "plugs",      label: "Plugs",       icon: "ti-plug",       count: plugs.length,                  summary: onOf(plugs) },
    { view: "ambient",    label: "Ambient",     icon: "ti-lamp-2",     count: latestAmbientLights.length,    summary: onlineOf(latestAmbientLights) },
    { view: "humidifier", label: "Humidifiers", icon: "ti-droplet",    count: latestHumidifiers.length,      summary: onlineOf(latestHumidifiers) },
    { view: "tuya",       label: "Sensors",     icon: "ti-radar-2",    count: sensorGroupCount("sensors"),   summary: onlineOf(latestTuyaDevices) },
    { view: "climate",    label: "Climate",     icon: "ti-temperature",count: latestThermostats.length,      summary: onlineOf(latestThermostats) },
  ];
}

function renderDevicesOverview() {
  const grid = document.querySelector("#devicesOverviewGrid");
  const badge = document.querySelector("#deviceGroupCount");

  if (badge) badge.textContent = String(distinctDeviceCount());

  if (!grid) return;
  grid.innerHTML = deviceGroupTileData().map((tile) => `
    <article class="device-group-tile" data-goto-view="${escapeHtml(tile.view)}">
      <div class="device-group-tile-head">
        <i class="ti ${tile.icon}" aria-hidden="true"></i>${escapeHtml(tile.label)}
      </div>
      <div class="device-group-tile-count">${tile.count}</div>
      <div class="device-group-tile-summary">${escapeHtml(tile.summary)}</div>
    </article>
  `).join("");
}

/* Distinct physical devices. A multi-capability sensor appears in more than
   one child view, so summing the child badges would over-count. */
function distinctDeviceCount() {
  const ids = new Set();
  const add = (list, prefix) => list.forEach((d, i) => ids.add(`${prefix}:${d.id ?? d.name ?? i}`));
  add(latestSwitchDevices, "switch");
  add(latestAmbientLights, "ambient");
  add(latestHumidifiers, "humidifier");
  add(latestThermostats, "climate");
  latestTuyaDevices.forEach((d) => ids.add(`tuya:${sensorBaseName(String(d.name || d.id || ""))}`));
  return ids.size;
}
```

`sensorGroupCount(mode)` arrives in Task 3. Until then, add this temporary definition immediately above `deviceGroupTileData` so this task stands alone:

```js
/* Replaced in Task 3 by the capability-aware version. */
function sensorGroupCount(_mode) {
  return groupSensorDevices(latestTuyaDevices.filter((d) => !isTuyaCamera(d))).length;
}
```

- [ ] **Step 7: Wire it into `activateView` and the group toggle**

In `activateView` (line 4306), add before the closing brace:

```js
  if (viewName === "devices") {
    setDevicesGroupOpen(true);
    renderDevicesOverview();
  }
  if (DEVICE_GROUP_VIEWS.includes(viewName)) {
    setDevicesGroupOpen(true);
  }
```

The second block auto-expands the group when a restored startup view is one of the children, so the active item is never hidden.

- [ ] **Step 8: Keep the overview live**

Add `renderDevicesOverview();` as the last statement of each of: `renderHumidifiers` (line 881), `renderTuyaDevices` (line 1524), and the ambient-light renderer that sets `ambientCount` (line 830). Guard each with `try {} catch {}`? No — call it directly; it is defensive about missing elements already.

- [ ] **Step 9: Run the tests**

Run: `python3 -m pytest tests/python/test_dashboard_devices_group.py tests/python/test_dashboard_layout.py -q`
Expected: `12 passed`.

- [ ] **Step 10: Verify in the browser**

Start the dev server and confirm: the Devices row expands/collapses via the chevron, clicking the row shows six tiles, clicking a tile navigates, and the state survives a reload.

Run: `python3 -m uvicorn src.python.web_app:app --host 0.0.0.0 --port 8000`

- [ ] **Step 11: Commit**

```bash
git add src/python/web_static/index.html src/python/web_static/styles.css src/python/web_static/app.js tests/python/test_dashboard_devices_group.py
git commit -m "feat: collapse device views under a Devices sidebar group with overview panel"
```

---

### Task 3: Environment view and the Sensors split

Adds the seventh child and splits temperature/humidity readings out of Sensors. Both views share one card renderer; only the readings reaching it differ.

**Files:**
- Modify: `src/python/web_static/index.html` (sidebar child + panel)
- Modify: `src/python/web_static/styles.css` (icon colour)
- Modify: `src/python/web_static/app.js:1368` (`renderSensorDeviceCard`), `:1524` (`renderTuyaDevices`), `activateView`
- Test: `tests/python/test_dashboard_environment_split.py` (create)

**Interfaces:**
- Consumes: `DEVICE_GROUP_VIEWS`, `renderDevicesOverview`, `sensorGroupCount` from Task 2.
- Produces:
  - `ENVIRONMENT_CAPABILITIES` — `Set` of `"temperature"`, `"humidity"`.
  - `filterReadingsForView(readings, mode)` — `mode` is `"environment"` or `"sensors"`; returns a filtered array.
  - `groupHasViewContent(group, mode)` — `boolean`.
  - `sensorGroupCount(mode)` — `number`, replacing Task 2's placeholder.
  - `renderSensorDeviceCard(group, mode)` — mode is now required.
  - `renderEnvironmentSensors()` — repaints `#environmentGrid`.
  - Panel `data-view-panel="environment"`, grid `#environmentGrid`, badge `#environmentCount`.

- [ ] **Step 1: Write the failing test**

Create `tests/python/test_dashboard_environment_split.py`:

```python
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML = PROJECT_ROOT / "src" / "python" / "web_static" / "index.html"
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"


def test_environment_is_a_device_group_child_before_sensors() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    views_start = html.index('<div class="sidebar-section">Views</div>')
    discovery_start = html.index('<div class="sidebar-section">Discovery</div>')
    views = html[views_start:discovery_start]

    children = re.findall(r'<li[^>]*\bdevice-group-item\b[^>]*\bdata-view="([^"]+)"', views)

    assert children == ["lights", "plugs", "ambient", "humidifier", "environment", "tuya", "climate"]


def test_environment_panel_and_badge_exist() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'data-view-panel="environment"' in html
    assert 'id="environmentGrid"' in html
    assert 'id="environmentCount"' in html


def test_split_filter_is_capability_driven() -> None:
    javascript = APP_JS.read_text(encoding="utf-8")

    assert "ENVIRONMENT_CAPABILITIES" in javascript
    assert "function filterReadingsForView(readings, mode)" in javascript
    assert "function groupHasViewContent(group, mode)" in javascript
    # The split must reuse the existing capability classifier, not re-derive it.
    assert "sensorCapabilityKey" in javascript


def test_card_renderer_takes_a_mode() -> None:
    javascript = APP_JS.read_text(encoding="utf-8")

    assert "function renderSensorDeviceCard(group, mode)" in javascript
    assert 'renderSensorDeviceCard(group, "sensors")' in javascript or \
           'renderSensorDeviceCard(g, "sensors")' in javascript
```

Add the behavioural half as a Node-run check, since the split logic is the part that can actually be wrong. Create `tests/python/test_environment_split_logic.py`:

```python
import shutil
import subprocess
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"

HARNESS = """
const src = require('fs').readFileSync(process.argv[1], 'utf8');
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
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `python3 -m pytest tests/python/test_dashboard_environment_split.py tests/python/test_environment_split_logic.py -q`
Expected: failures on the missing `environment` child and missing `ENVIRONMENT_CAPABILITIES`.

- [ ] **Step 3: Add the sidebar child and panel**

In `index.html`, insert directly before the `<li ... data-view="tuya">` item:

```html
      <li class="room-item device-group-item" data-view="environment">
        <span class="room-icon"><i class="ti ti-temperature-celsius"></i></span>
        Environment
        <span class="room-badge" id="environmentCount">–</span>
      </li>
```

Insert a panel directly before the `<!-- ── TUYA / SENSORS VIEW ── -->` comment:

```html
    <!-- ── ENVIRONMENT VIEW ── -->
    <div class="view-panel" data-view-panel="environment">
      <div class="section-header">
        <span class="section-title">Environment</span>
        <span class="section-meta">Temperature &amp; humidity</span>
      </div>
      <div class="device-grid" id="environmentGrid">
        <div class="loading-msg"><i class="ti ti-loader-2 spin"></i> Loading…</div>
      </div>
    </div>
```

In `styles.css`, beside the other per-view icon colours:

```css
.room-item[data-view="environment"] .room-icon { color: var(--cyan); }
```

- [ ] **Step 4: Add the split helpers to `app.js`**

Insert immediately after `countUniqueSensorCapabilities` (line 1228):

```js
/* ── Environment / Sensors split ──
   One physical device can report temperature, humidity, leak and smoke at
   once. It appears in both views, filtered to the readings each view owns,
   so nothing is hidden. Battery rides along in both as context. */
const ENVIRONMENT_CAPABILITIES = new Set(["temperature", "humidity"]);

function filterReadingsForView(readings, mode) {
  if (mode !== "environment" && mode !== "sensors") return readings;
  return readings.filter((reading) => {
    const key = sensorCapabilityKey(reading);
    if (key === "battery") return true;
    return mode === "environment"
      ? ENVIRONMENT_CAPABILITIES.has(key)
      : !ENVIRONMENT_CAPABILITIES.has(key);
  });
}

/* A battery reading alone must not conjure a card into either view. */
function groupHasViewContent(group, mode) {
  return filterReadingsForView(expandSensorReadings(group.readings), mode)
    .some((reading) => sensorCapabilityKey(reading) !== "battery");
}

function sensorGroupCount(mode) {
  const visible = latestTuyaDevices.filter((d) => !isTuyaCamera(d));
  return groupSensorDevices(visible).filter((g) => groupHasViewContent(g, mode)).length;
}
```

Delete the temporary `sensorGroupCount` placeholder added in Task 2.

- [ ] **Step 5: Make the card renderer mode-aware**

Change the signature and first lines of `renderSensorDeviceCard` (line 1368) from:

```js
function renderSensorDeviceCard(group) {
  const { name } = group;
  const readings = expandSensorReadings(group.readings);
```

to:

```js
function renderSensorDeviceCard(group, mode) {
  const { name } = group;
  const readings = filterReadingsForView(expandSensorReadings(group.readings), mode);
```

Everything downstream derives from `readings` via `findCat()`, so gauges and alert rows follow automatically with no further edits to the function.

- [ ] **Step 6: Split the two renderers**

In `renderTuyaDevices` (line 1524), replace the grouping and paint lines. Change:

```js
  const groups = groupSensorDevices(visibleDevices);
```

to:

```js
  const groups = groupSensorDevices(visibleDevices).filter((g) => groupHasViewContent(g, "sensors"));
```

and change `tuyaCount.textContent = String(visibleDevices.length);` to:

```js
  tuyaCount.textContent = String(sensorGroupCount("sensors"));
```

and the paint line from `groups.map(renderSensorDeviceCard).join("")` to:

```js
  tuyaGrid.innerHTML = banner + groups.map((g) => renderSensorDeviceCard(g, "sensors")).join("");
```

Then add the Environment renderer immediately after `renderTuyaDevices`:

```js
/* ── Environment (temperature & humidity) ── */
function renderEnvironmentSensors() {
  const grid = document.querySelector("#environmentGrid");
  const badge = document.querySelector("#environmentCount");
  const visible = latestTuyaDevices.filter((d) => !isTuyaCamera(d));
  const groups = groupSensorDevices(visible).filter((g) => groupHasViewContent(g, "environment"));

  if (badge) badge.textContent = String(groups.length);
  if (!grid) return;
  if (groups.length === 0) {
    grid.innerHTML = '<div class="empty">No temperature or humidity sensors reporting yet.</div>';
    return;
  }
  grid.innerHTML = groups.map((g) => renderSensorDeviceCard(g, "environment")).join("");
}
```

Call `renderEnvironmentSensors();` as the last statement of `renderTuyaDevices`, so both views repaint from one data load.

- [ ] **Step 7: Register the new view**

In `app.js`, add `"environment"` to `DEVICE_GROUP_VIEWS`, placing it before `"tuya"`:

```js
const DEVICE_GROUP_VIEWS = ["lights", "plugs", "ambient", "humidifier", "environment", "tuya", "climate"];
```

In `deviceGroupTileData()`, insert an Environment tile before the Sensors tile:

```js
    { view: "environment", label: "Environment", icon: "ti-temperature-celsius", count: sensorGroupCount("environment"), summary: environmentSummary() },
```

and add the summary helper beside it:

```js
/* Average temperature across environment groups, for the overview tile. */
function environmentSummary() {
  const temps = latestTuyaDevices
    .filter((d) => sensorCapabilityKey(d) === "temperature")
    .map(readingMetricNumber)
    .filter(Number.isFinite);
  if (temps.length === 0) return "No readings";
  const avg = temps.reduce((a, b) => a + b, 0) / temps.length;
  return `avg ${avg.toFixed(1)} °C`;
}
```

- [ ] **Step 8: Run the tests**

Run: `python3 -m pytest tests/python/ -q -k "dashboard or environment"`
Expected: all pass. If `node` is absent the logic test skips — that is acceptable, but prefer running it.

- [ ] **Step 9: Verify in the browser**

Confirm a multi-capability sensor appears in **both** Environment (gauges only) and Sensors (alert rows only), and that a battery-only device appears in neither.

- [ ] **Step 10: Commit**

```bash
git add src/python/web_static/ tests/python/test_dashboard_environment_split.py tests/python/test_environment_split_logic.py
git commit -m "feat: split temperature and humidity readings into an Environment view"
```

---

### Task 4: Verify the H5140's real Govee capabilities

The spec forbids inferring the capability set from the model number. This task produces a reusable probe script and records what the device actually reports; Task 5's endpoint is written against that observation.

**Files:**
- Create: `scripts/probe-govee-cloud-device.py`
- Modify: `docs/superpowers/specs/2026-07-24-devices-group-environment-design.md` (record findings)

**Interfaces:**
- Consumes: `GOVEE_API_KEY` from the environment.
- Produces: confirmed capability instance names for the H5140 — expected `sensorTemperature` and `sensorHumidity`, plus its `device` id and `sku`, for use in Tasks 5 and 7.

- [ ] **Step 1: Write the probe script**

Create `scripts/probe-govee-cloud-device.py`, following the style of the existing `scripts/discover-govee-ble.py`:

```python
#!/usr/bin/env python3
"""Print the Govee cloud device list with each device's capability instances.

Usage:
    GOVEE_API_KEY=... python3 scripts/probe-govee-cloud-device.py [SKU]

Run this on the Pi (or anywhere with the API key) before wiring a new Govee
device into the dashboard — never assume a model's capabilities from its SKU.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request

BASE = "https://openapi.api.govee.com"


def main() -> int:
    key = os.environ.get("GOVEE_API_KEY")
    if not key:
        print("GOVEE_API_KEY is not set", file=sys.stderr)
        return 2

    wanted = sys.argv[1].upper() if len(sys.argv) > 1 else None

    request = urllib.request.Request(
        f"{BASE}/router/api/v1/user/devices",
        headers={"Govee-API-Key": key, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))

    for entry in payload.get("data") or []:
        sku = str(entry.get("sku") or "")
        if wanted and sku.upper() != wanted:
            continue
        print(f"{sku}  {entry.get('deviceName')}")
        print(f"  device: {entry.get('device')}")
        for cap in entry.get("capabilities") or []:
            print(f"  - {cap.get('type')}  instance={cap.get('instance')}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run it against the H5140**

Run on the Pi (or locally with the key exported):

```bash
GOVEE_API_KEY=... python3 scripts/probe-govee-cloud-device.py H5140
```

Expected: one block for the H5140 listing its capability instances. Record the exact `instance` values and the `device` id.

- [ ] **Step 3: Record the findings in the spec**

Append a subsection to Part 3 of `docs/superpowers/specs/2026-07-24-devices-group-environment-design.md` under "Capability verification precedes implementation", stating the observed instances and the date. Do **not** commit the real `device` id — record it only as "obtained, stored in `devices.local.yaml`".

**If the observed instances are not `sensorTemperature` / `sensorHumidity`:** stop and adjust Task 5's parsing to the observed names before continuing. Note the deviation in the spec.

- [ ] **Step 4: Commit**

```bash
git add scripts/probe-govee-cloud-device.py docs/superpowers/specs/2026-07-24-devices-group-environment-design.md
git commit -m "chore: add Govee cloud capability probe and record H5140 findings"
```

---

### Task 5: Environment sensor config and API endpoint

**Files:**
- Modify: `src/python/web_app.py` — dataclass near `:155`, loader near `:1285`, helpers near `:1785`, route near `:484`
- Modify: `configs/devices.example.yaml` (new `environment:` section after `humidifiers:` at `:173-185`)
- Test: `tests/python/test_environment_sensors.py` (create)

**Interfaces:**
- Consumes: `_govee_thermometer_reading(entry)` (`web_app.py:1709`), returning `{"humidity": float, "temperature_f": float}` or `None`; `_govee_cloud_devices()`; `_govee_api_key()`; `_is_real_ble_address()`.
- Produces:
  - `EnvironmentSensorDefinition(name, provider, model, room, device_id)` — frozen dataclass.
  - `_load_environment_sensors(path: Path) -> list[EnvironmentSensorDefinition]`.
  - `_match_environment_sensor(sensor, devices) -> dict | None`.
  - `_environment_sensor_card(sensor) -> dict` with keys `name`, `room`, `model`, `temperature`, `humidity`, `online`, `status`, `note`.
  - `_environment_sensor_cards(path) -> {"sensors": [...]}`.
  - `GET /api/environment-sensors`.
  - `ENVIRONMENT_RUNTIME_STATE: dict[str, dict]`.

- [ ] **Step 1: Write the failing test**

Create `tests/python/test_environment_sensors.py`:

```python
import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.python.web_app import (
    EnvironmentSensorDefinition,
    _load_environment_sensors,
    _match_environment_sensor,
    create_app,
)
from src.python import web_app


def _write_environment_config(path: Path) -> None:
    path.write_text(
        """
environment:
  sensors:
    - name: Bedroom Thermo-Hygrometer
      provider: govee_cloud
      model: H5140
      room: Bedroom
      device_id: replace_me
    - name: Disabled Sensor
      provider: govee_cloud
      model: H5179
      enabled: false
""",
        encoding="utf-8",
    )


class FakeController:
    async def gather_status(self, *args, **kwargs):
        return []


def _client(tmp_path: Path) -> TestClient:
    discovery = tmp_path / "tplink.json"
    discovery.write_text(json.dumps({"switches": []}), encoding="utf-8")
    config = tmp_path / "devices.local.yaml"
    _write_environment_config(config)
    return TestClient(
        create_app(discovery_path=discovery, config_path=config, controller=FakeController())
    )


def test_load_parses_entries_and_skips_disabled(tmp_path: Path) -> None:
    config = tmp_path / "devices.local.yaml"
    _write_environment_config(config)

    sensors = _load_environment_sensors(config)

    assert len(sensors) == 1
    assert sensors[0].name == "Bedroom Thermo-Hygrometer"
    assert sensors[0].model == "H5140"
    assert sensors[0].room == "Bedroom"
    assert sensors[0].provider == "govee_cloud"


def test_load_tolerates_missing_file_null_and_absent_section(tmp_path: Path) -> None:
    assert _load_environment_sensors(tmp_path / "nope.yaml") == []

    absent = tmp_path / "absent.yaml"
    absent.write_text("tplink: {}\n", encoding="utf-8")
    assert _load_environment_sensors(absent) == []

    null = tmp_path / "null.yaml"
    null.write_text("environment:\n", encoding="utf-8")
    assert _load_environment_sensors(null) == []

    null_sensors = tmp_path / "null_sensors.yaml"
    null_sensors.write_text("environment:\n  sensors:\n", encoding="utf-8")
    assert _load_environment_sensors(null_sensors) == []


def test_match_prefers_device_id_then_unique_model() -> None:
    devices = [
        {"sku": "H5140", "device": "AA:BB", "capabilities": []},
        {"sku": "H5179", "device": "CC:DD", "capabilities": []},
    ]

    by_id = EnvironmentSensorDefinition(
        name="s", provider="govee_cloud", model="H5179", room=None, device_id="AA:BB"
    )
    assert _match_environment_sensor(by_id, devices)["device"] == "AA:BB"

    by_model = EnvironmentSensorDefinition(
        name="s", provider="govee_cloud", model="H5140", room=None, device_id="replace_me"
    )
    assert _match_environment_sensor(by_model, devices)["device"] == "AA:BB"


def test_match_returns_none_for_ambiguous_model() -> None:
    devices = [
        {"sku": "H5140", "device": "AA:BB", "capabilities": []},
        {"sku": "H5140", "device": "CC:DD", "capabilities": []},
    ]
    sensor = EnvironmentSensorDefinition(
        name="s", provider="govee_cloud", model="H5140", room=None, device_id="replace_me"
    )

    assert _match_environment_sensor(sensor, devices) is None


def test_endpoint_without_api_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GOVEE_API_KEY", raising=False)

    payload = _client(tmp_path).get("/api/environment-sensors").json()

    assert len(payload["sensors"]) == 1
    assert payload["sensors"][0]["status"] == "needs_api_key"
    assert payload["sensors"][0]["temperature"] is None


def test_endpoint_converts_fahrenheit_to_celsius(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GOVEE_API_KEY", "test-key")
    web_app._GOVEE_CLOUD_CACHE["devices"] = None
    web_app._GOVEE_CLOUD_CACHE["fetched"] = 0

    def fake_request(path, payload=None):
        if path.endswith("/user/devices"):
            return {"data": [{
                "sku": "H5140", "device": "AA:BB", "deviceName": "Bedroom",
                "capabilities": [
                    {"type": "devices.capabilities.property", "instance": "sensorTemperature"},
                    {"type": "devices.capabilities.property", "instance": "sensorHumidity"},
                ],
            }]}
        return {"payload": {"capabilities": [
            {"instance": "sensorTemperature", "state": {"value": 71.6}},
            {"instance": "sensorHumidity", "state": {"value": 48}},
        ]}}

    monkeypatch.setattr(web_app, "_govee_cloud_request", fake_request)

    sensor = _client(tmp_path).get("/api/environment-sensors").json()["sensors"][0]

    assert sensor["temperature"] == 22.0  # 71.6 F
    assert sensor["humidity"] == 48
    assert sensor["online"] is True


def test_endpoint_reports_offline_when_cloud_fails(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GOVEE_API_KEY", "test-key")
    web_app._GOVEE_CLOUD_CACHE["devices"] = None
    web_app._GOVEE_CLOUD_CACHE["fetched"] = 0

    def fake_request(path, payload=None):
        raise RuntimeError("cloud down")

    monkeypatch.setattr(web_app, "_govee_cloud_request", fake_request)

    sensor = _client(tmp_path).get("/api/environment-sensors").json()["sensors"][0]

    assert sensor["online"] is False
    assert sensor["temperature"] is None
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `python3 -m pytest tests/python/test_environment_sensors.py -q`
Expected: `ImportError: cannot import name 'EnvironmentSensorDefinition'`.

- [ ] **Step 3: Add the dataclass**

In `src/python/web_app.py`, immediately after `HumidifierDefinition` (which ends at line 165):

```python
@dataclass(frozen=True)
class EnvironmentSensorDefinition:
    """A standalone temperature/humidity sensor (e.g. Govee H5140)."""
    name: str
    provider: str
    model: str | None
    room: str | None
    device_id: str | None
```

- [ ] **Step 4: Add the loader**

Immediately after `_load_humidifiers` (which ends at line 1285):

```python
def _load_environment_sensors(path: Path) -> list[EnvironmentSensorDefinition]:
    if not path.exists():
        return []
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    sensors = []
    for item in (payload.get("environment") or {}).get("sensors") or []:
        if item.get("enabled") is False:
            continue
        sensors.append(
            EnvironmentSensorDefinition(
                name=str(item.get("name") or item.get("model") or "Environment sensor"),
                provider=str(item.get("provider") or "govee_cloud").lower(),
                model=str(item.get("model")) if item.get("model") else None,
                room=item.get("room"),
                device_id=str(item.get("device_id") or "") or None,
            )
        )
    return sensors
```

The `or {}` / `or []` chain is what makes a `null` section safe, matching commit `d11e07e`.

- [ ] **Step 5: Add the matcher and card builder**

After `_govee_thermometer_reading` (which ends at line 1726):

```python
ENVIRONMENT_RUNTIME_STATE: dict[str, dict[str, Any]] = {}


def _match_environment_sensor(
    sensor: EnvironmentSensorDefinition, devices: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Explicit device id wins; otherwise match a unique model. No account-wide
    fallback — that ambiguity is what breaks the humidifier's linked thermometer."""
    if _is_real_ble_address(sensor.device_id):
        for entry in devices:
            if str(entry.get("device") or "").lower() == sensor.device_id.lower():
                return entry
        return None
    if sensor.model:
        matches = [e for e in devices if str(e.get("sku") or "").upper() == sensor.model.upper()]
        if len(matches) == 1:
            return matches[0]
    return None


def _fahrenheit_to_celsius(value: float) -> float:
    return round((value - 32.0) * 5.0 / 9.0, 1)


def _environment_sensor_card(sensor: EnvironmentSensorDefinition) -> dict[str, Any]:
    card = {
        "name": sensor.name,
        "room": sensor.room,
        "model": sensor.model,
        "temperature": None,
        "humidity": None,
        "online": False,
        "status": "ok",
        "note": None,
    }

    if sensor.provider != "govee_cloud":
        card["status"] = "unsupported"
        card["note"] = "Unsupported environment sensor provider."
        return card

    if not _govee_api_key():
        card["status"] = "needs_api_key"
        card["note"] = "Set GOVEE_API_KEY on the Pi to read this sensor."
        return card

    runtime_key = sensor.device_id if _is_real_ble_address(sensor.device_id) else sensor.name

    try:
        entry = _match_environment_sensor(sensor, _govee_cloud_devices())
    except Exception:
        entry = None

    if entry is None:
        cached = ENVIRONMENT_RUNTIME_STATE.get(runtime_key)
        if cached:
            card.update(cached)
            card["online"] = False
            card["note"] = "Showing last known reading; sensor unreachable."
        else:
            card["status"] = "not_found"
            card["note"] = "Sensor not found in the Govee account."
        return card

    reading = _govee_thermometer_reading(entry)
    if reading is None:
        cached = ENVIRONMENT_RUNTIME_STATE.get(runtime_key)
        if cached:
            card.update(cached)
        card["online"] = False
        card["note"] = "Sensor did not report a reading."
        return card

    values: dict[str, Any] = {}
    if reading.get("temperature_f") is not None:
        values["temperature"] = _fahrenheit_to_celsius(float(reading["temperature_f"]))
    if reading.get("humidity") is not None:
        values["humidity"] = reading["humidity"]

    ENVIRONMENT_RUNTIME_STATE[runtime_key] = values
    card.update(values)
    card["online"] = True
    return card


def _environment_sensor_cards(path: Path) -> dict[str, Any]:
    return {"sensors": [_environment_sensor_card(s) for s in _load_environment_sensors(path)]}
```

Govee reports temperature in Fahrenheit, which is why the conversion lives here rather than in the frontend.

- [ ] **Step 6: Add the route**

In `create_app`, immediately after the `@app.get("/api/humidifiers")` handler (line 484-486):

```python
    @app.get("/api/environment-sensors")
    async def environment_sensors() -> dict[str, Any]:
        return await asyncio.to_thread(_environment_sensor_cards, app.state.config_path)
```

- [ ] **Step 7: Document the config section**

In `configs/devices.example.yaml`, after the `humidifiers:` block (ends line 185):

```yaml
environment:
  # Standalone temperature/humidity sensors read through the Govee Developer
  # API v2. Same GOVEE_API_KEY as the humidifiers above — set it in the
  # environment on the Pi, never here.
  sensors:
    # device_id is the "device" value from the Govee API device list; find it
    # with: GOVEE_API_KEY=... python3 scripts/probe-govee-cloud-device.py H5140
    # Leave replace_me and the app matches by model when the account has
    # exactly one device of that model.
    - name: Bedroom Thermo-Hygrometer
      provider: govee_cloud
      model: H5140
      room: Bedroom
      device_id: replace_me
```

- [ ] **Step 8: Run the tests**

Run: `python3 -m pytest tests/python/test_environment_sensors.py -q`
Expected: `8 passed`.

- [ ] **Step 9: Commit**

```bash
git add src/python/web_app.py configs/devices.example.yaml tests/python/test_environment_sensors.py
git commit -m "feat: add environment sensor config and /api/environment-sensors endpoint"
```

---

### Task 6: Render H5140 readings in the Environment view

**Files:**
- Modify: `src/python/web_static/app.js` (loader near `:876`, renderer near `renderEnvironmentSensors`, `activateView`, init at `:4794`)
- Test: `tests/python/test_dashboard_environment_split.py` (extend)

**Interfaces:**
- Consumes: `GET /api/environment-sensors` from Task 5 (`{"sensors": [{name, room, model, temperature, humidity, online, status, note}]}`); `renderEnvironmentSensors()` and `groupHasViewContent()` from Task 3.
- Produces: `latestEnvironmentSensors` (module-level array), `loadEnvironmentSensors()`, `environmentSensorCard(sensor)`.

- [ ] **Step 1: Write the failing test**

Append to `tests/python/test_dashboard_environment_split.py`:

```python
def test_environment_sensors_are_loaded_and_rendered() -> None:
    javascript = APP_JS.read_text(encoding="utf-8")

    assert "latestEnvironmentSensors" in javascript
    assert 'requestJson("/api/environment-sensors")' in javascript
    assert "function environmentSensorCard(sensor)" in javascript
    # Loaded on startup like ambient lights and humidifiers, not only on view switch.
    init = javascript[javascript.index("function initDefaultView"):]
    assert "loadEnvironmentSensors()" in init[:600]
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `python3 -m pytest tests/python/test_dashboard_environment_split.py -q`
Expected: FAIL on `latestEnvironmentSensors`.

- [ ] **Step 3: Add the state and loader**

In `app.js`, beside the other `latest*` declarations (line 183, after `let latestHumidifiers = [];`):

```js
let latestEnvironmentSensors = [];
```

Add the loader after `loadHumidifiers` (line 879):

```js
/* ── Environment sensors (Govee cloud thermo-hygrometers) ── */
async function loadEnvironmentSensors() {
  const payload = await requestJson("/api/environment-sensors");
  latestEnvironmentSensors = payload.sensors || [];
  renderEnvironmentSensors();
  renderDevicesOverview();
}

function environmentSensorCard(sensor) {
  const temp = sensor.temperature != null ? `${sensor.temperature}<small>°C</small>` : "–";
  const hum  = sensor.humidity != null ? `${sensor.humidity}<small>%</small>` : "–";
  const note = sensor.note
    ? `<p class="sdc-sub">${escapeHtml(sensor.note)}</p>`
    : "";

  return `<article class="sdc-card" data-device-id="${escapeHtml(sensor.name)}">
    <div class="sdc-header">
      <div>
        <h3 class="sdc-name">${escapeHtml(sensor.name)}</h3>
        <p class="sdc-sub">${escapeHtml([sensor.room, sensor.model].filter(Boolean).join(" · ") || "Govee")}</p>
      </div>
      <span class="sdc-badge">${sensor.online ? "ONLINE" : "OFFLINE"}</span>
    </div>
    <div class="sdc-gauges-row">
      <div class="sdc-gauge"><i class="ti ti-temperature"></i><span class="gauge-value">${temp}</span></div>
      <div class="sdc-gauge"><i class="ti ti-droplet"></i><span class="gauge-value">${hum}</span></div>
    </div>
    ${note}
  </article>`;
}
```

- [ ] **Step 4: Merge cloud sensors into the Environment grid**

In `renderEnvironmentSensors` (from Task 3), replace the body so cloud sensors render alongside the Tuya/HA groups:

```js
function renderEnvironmentSensors() {
  const grid = document.querySelector("#environmentGrid");
  const badge = document.querySelector("#environmentCount");
  const visible = latestTuyaDevices.filter((d) => !isTuyaCamera(d));
  const groups = groupSensorDevices(visible).filter((g) => groupHasViewContent(g, "environment"));

  const total = groups.length + latestEnvironmentSensors.length;
  if (badge) badge.textContent = String(total);
  if (!grid) return;
  if (total === 0) {
    grid.innerHTML = '<div class="empty">No temperature or humidity sensors reporting yet.</div>';
    return;
  }
  grid.innerHTML =
    latestEnvironmentSensors.map(environmentSensorCard).join("") +
    groups.map((g) => renderSensorDeviceCard(g, "environment")).join("");
}
```

Update the Environment tile count in `deviceGroupTileData()` to match:

```js
    { view: "environment", label: "Environment", icon: "ti-temperature-celsius", count: sensorGroupCount("environment") + latestEnvironmentSensors.length, summary: environmentSummary() },
```

- [ ] **Step 5: Wire loading**

In `activateView`, beside the existing ambient/humidifier blocks:

```js
  if (viewName === "environment") {
    loadEnvironmentSensors().catch((error) => console.error(error));
  }
```

In `initDefaultView` (line 4792-4794), beside the existing startup loads:

```js
  loadEnvironmentSensors().catch((error) => console.error(error));
```

- [ ] **Step 6: Run the tests**

Run: `python3 -m pytest tests/python/ -q -k "dashboard or environment"`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add src/python/web_static/app.js tests/python/test_dashboard_environment_split.py
git commit -m "feat: render Govee H5140 readings in the Environment view"
```

---

### Task 7: Fix the H7140 linked-thermometer regression

`_match_govee_thermometer` falls back to "the account's sole ambient-humidity sensor". With the H5140 on the account there are two, neither reporting CO2, so the `pure` filter does not disambiguate, `len(sensors) == 1` fails, and the humidifier orb silently loses its readout. Pin the thermometer explicitly and document the hazard.

**Files:**
- Modify: `configs/devices.example.yaml` (humidifier block, `:173-185`)
- Modify: `src/python/web_app.py:1685-1706` (comment only)
- Test: `tests/python/test_humidifiers.py` (extend)

**Interfaces:**
- Consumes: `_match_govee_thermometer(humidifier, devices)` (`web_app.py:1685`).
- Produces: no signature changes — a regression test plus config documentation.

- [ ] **Step 1: Write the failing test**

Append to `tests/python/test_humidifiers.py`:

```python
def _humidity_sensor(sku: str, device: str) -> dict:
    return {
        "sku": sku,
        "device": device,
        "capabilities": [
            {"type": "devices.capabilities.property", "instance": "sensorHumidity"},
            {"type": "devices.capabilities.property", "instance": "sensorTemperature"},
        ],
    }


def test_thermometer_fallback_is_ambiguous_with_two_humidity_sensors() -> None:
    """Adding an H5140 puts a second humidity sensor on the account, so the
    'sole sensor' fallback can no longer resolve. Documents why pinning is needed."""
    devices = [_humidity_sensor("H5179", "AA:BB"), _humidity_sensor("H5140", "CC:DD")]
    unpinned = HumidifierDefinition(
        name="Bedroom Humidifier", provider="govee_cloud", model="H7140",
        room="Bedroom", device_id="replace_me",
    )

    assert _match_govee_thermometer(unpinned, devices) is None


def test_pinned_thermometer_device_id_survives_a_second_humidity_sensor() -> None:
    devices = [_humidity_sensor("H5179", "AA:BB"), _humidity_sensor("H5140", "CC:DD")]
    pinned = HumidifierDefinition(
        name="Bedroom Humidifier", provider="govee_cloud", model="H7140",
        room="Bedroom", device_id="replace_me", thermometer_device_id="AA:BB",
    )

    assert _match_govee_thermometer(pinned, devices)["device"] == "AA:BB"


def test_pinned_thermometer_model_survives_a_second_humidity_sensor() -> None:
    devices = [_humidity_sensor("H5179", "AA:BB"), _humidity_sensor("H5140", "CC:DD")]
    pinned = HumidifierDefinition(
        name="Bedroom Humidifier", provider="govee_cloud", model="H7140",
        room="Bedroom", device_id="replace_me", thermometer_model="H5179",
    )

    assert _match_govee_thermometer(pinned, devices)["device"] == "AA:BB"
```

- [ ] **Step 2: Run it**

Run: `python3 -m pytest tests/python/test_humidifiers.py -q -k thermometer`
Expected: all three PASS. They characterise existing behaviour — the first proves the regression is real, the other two prove pinning is the cure. If any fail, the code differs from the spec's analysis; stop and re-read `_match_govee_thermometer` before continuing.

- [ ] **Step 3: Document the hazard in the config example**

In `configs/devices.example.yaml`, extend the humidifier entry (line 181-185) to:

```yaml
    - name: Bedroom Humidifier
      provider: govee_cloud
      model: H7140
      room: Bedroom
      device_id: replace_me
      # The card shows ambient temperature/humidity from a linked Govee
      # thermometer. Without an explicit id the app falls back to "the only
      # humidity sensor on the account" — which STOPS WORKING as soon as a
      # second one (e.g. an H5140 in the environment: section below) is added.
      # Pin it. Find the id with:
      #   GOVEE_API_KEY=... python3 scripts/probe-govee-cloud-device.py H5179
      thermometer_device_id: replace_me
      thermometer_model: H5179
```

- [ ] **Step 4: Sharpen the code comment**

In `src/python/web_app.py`, replace the `_match_govee_thermometer` docstring (line 1688-1689) with:

```python
    """Resolve the linked thermometer: explicit id, then model, then the account's
    sole ambient-humidity sensor.

    The final fallback only works while exactly one humidity sensor is on the
    account. Configs relying on it break silently when a second is added — pin
    thermometer_device_id instead. See test_humidifiers.py::
    test_thermometer_fallback_is_ambiguous_with_two_humidity_sensors.
    """
```

- [ ] **Step 5: Run the full suite**

Run: `python3 -m pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add configs/devices.example.yaml src/python/web_app.py tests/python/test_humidifiers.py
git commit -m "fix: pin humidifier thermometer so a second Govee humidity sensor cannot break it"
```

---

### Task 8: Deploy and verify on the Pi

**Files:**
- Modify: `configs/devices.local.yaml` **on the Pi only** — never committed.

**Interfaces:**
- Consumes: everything from Tasks 1-7.
- Produces: a running dashboard on the Pi with the Devices group, Environment view and live H5140 readings.

- [ ] **Step 1: Run the full test suite**

Run: `python3 -m pytest -q`
Expected: all pass, no failures, no errors.

- [ ] **Step 2: Add the real config on the Pi**

SSH to the Pi and edit `configs/devices.local.yaml`. Add the `environment:` section with the real H5140 `device_id` recorded in Task 4, and pin `thermometer_device_id` on the existing humidifier entry to the H5179's real id.

```bash
scripts/connect-pi.sh --check
```

This file is git-ignored; do not commit it or paste real device ids into the repo.

- [ ] **Step 3: Deploy**

```bash
scripts/deploy-dashboard.sh
```

- [ ] **Step 4: Verify each part in the browser**

Open the dashboard on the Pi and confirm:

1. Devices group collapses via the chevron and persists across reload.
2. Clicking Devices shows seven tiles; each navigates.
3. The Devices badge matches the number of physical devices, not the sum of the child badges.
4. A multi-capability sensor appears in **both** Environment and Sensors, with the right readings in each.
5. The H5140 card shows a live temperature in °C and humidity in %.
6. **The humidifier orb still shows its ambient temperature and humidity** — this is the regression from Task 7; confirm the pin worked against the real account.
7. On a phone, the rail shows the seven device icons flat with no Devices parent.

- [ ] **Step 5: Commit any config-example corrections**

If real-world use revealed a wrong comment or default in `configs/devices.example.yaml`, fix it and commit:

```bash
git add configs/devices.example.yaml
git commit -m "docs: correct environment sensor config example after Pi verification"
```

---

## Self-Review

**Spec coverage:**

| Spec section | Task |
|---|---|
| Part 1 sidebar structure, styling, interaction | 2 |
| Part 1 overview panel, `data-goto-view` reuse | 2 |
| Part 1 distinct-device badge | 2 (`distinctDeviceCount`) |
| Part 1 mobile rail flattening + ordering caveat | 2 (Step 5) |
| Part 2 split rule, non-battery qualification | 3 |
| Part 2 scope boundary (no Ecobee, no humidifier thermometer) | 3 — Environment reads only `latestTuyaDevices` + `latestEnvironmentSensors` |
| Part 3 capability verification precedes implementation | 4 |
| Part 3 config schema, null tolerance | 5 |
| Part 3 backend endpoint, °F→°C, runtime cache | 5 |
| Part 3 frontend loader and card | 6 |
| Part 4 H7140 regression fix | 7 |
| Testing: devices group, environment sensors, split, regression | 2, 3, 5, 6, 7 |
| Testing: repair stale test, harden fragile parse | 1 |

No spec requirement is unassigned.

**Placeholder scan:** No TBD/TODO. Every code step carries complete code. Task 2 Step 6 introduces a deliberately temporary `sensorGroupCount` so the task stands alone; Task 3 Step 4 explicitly deletes it — this is stated in both places rather than left implicit.

**Type consistency:** `filterReadingsForView(readings, mode)`, `groupHasViewContent(group, mode)`, `sensorGroupCount(mode)` and `renderSensorDeviceCard(group, mode)` all take the same `mode` values (`"environment"` / `"sensors"`) across Tasks 3 and 6. `EnvironmentSensorDefinition` field order in Task 5's dataclass matches every keyword construction in its tests. `_environment_sensor_card` returns the exact key set (`name`, `room`, `model`, `temperature`, `humidity`, `online`, `status`, `note`) that `environmentSensorCard(sensor)` reads in Task 6. `latestEnvironmentSensors` is declared in Task 6 Step 3 and used in Task 6 Steps 4-5 only.

**One ordering note for the executor:** Task 2's `deviceGroupTileData` is edited again in Tasks 3 and 6. Execute in order; do not parallelise Tasks 2, 3 and 6.
