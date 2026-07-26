# Devices View Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle the Devices overview tiles with distinct per-group colours and a larger icon, and add a return button to each of the seven device views.

**Architecture:** Each group's colour is defined once as a `--group-color` custom property on a selector list covering both the sidebar item and the overview tile, so the two cannot drift apart. The tiles gain a top accent strip reading that variable. The return button reuses the existing `.command` button class and is shown only when a module-level flag records that the user arrived from the Devices overview.

**Tech Stack:** Vanilla JS (no framework, no build step), CSS custom properties, pytest, Tabler Icons (`ti ti-*`).

**Spec:** `docs/superpowers/specs/2026-07-26-devices-view-polish-design.md`

## Global Constraints

- No build step: `app.js`, `index.html` and `styles.css` are served as-is. No frameworks, no bundler, no package.json, no new runtime dependencies. A JS syntax error ships straight to users — always run `node --check`.
- Icons come from the already-loaded Tabler webfont (`<i class="ti ti-*">`). Do not add icon libraries.
- The seven device views keep their existing `data-view` values exactly: `lights`, `plugs`, `ambient`, `humidifier` (singular), `environment`, `tuya` (this is the Sensors view), `climate`.
- Python 3; `pyproject.toml` sets `pythonpath = ["."]`; run `python3 -m pytest` from the project root.
- Never commit real device IDs, API keys, or credentials.
- Pre-existing unrelated test failures: **4 failed, 7 errors** (matter_bridge C++ work-in-progress in the tree, a docker-permissions test, a tplink test). Do not attempt to fix these. Current total: 4 failed, 264 passed, 7 errors.
- A post-commit hook auto-deploys to the Pi and bumps `BUILD_COUNT` / `build_info.json` / `index.html` cache-bust values. That churn is expected — never include those files in a commit and never revert them.

## File Structure

| File | Responsibility in this plan |
|---|---|
| `src/python/web_static/styles.css` | New palette vars; `--group-color` definitions; tile restyle; back-button spacing |
| `src/python/web_static/index.html` | Back button markup in seven panels; `.section-actions` wrappers where missing |
| `src/python/web_static/app.js` | Tile markup (accent strip); `arrivedFromDevices` flag; back-button visibility |
| `tests/python/test_devices_view_polish.py` | New — colour uniqueness, tile markup, back-button markup and wiring |

---

### Task 1: Per-group colours with a single source of truth

Adds two palette colours and defines `--group-color` once per group on a selector list covering both the sidebar item and the overview tile. Fixes the two existing collisions (`devices`/`plugs` both `--accent`; `environment`/`tuya` both `--cyan`).

**Files:**
- Modify: `src/python/web_static/styles.css` (`:root` palette block; the per-view icon colour block at ~`:381-388`)
- Test: `tests/python/test_devices_view_polish.py` (create)

**Interfaces:**
- Consumes: nothing.
- Produces:
  - CSS vars `--teal: #2dd4bf;` and `--indigo: #818cf8;` in `:root`.
  - A `--group-color` custom property resolvable on `.room-item[data-view="X"]` and `.device-group-tile[data-goto-view="X"]` for all seven groups.
  - `.room-icon { color: var(--group-color, currentColor); }` — later tasks rely on the tile reading `var(--group-color)`.

- [ ] **Step 1: Write the failing test**

Create `tests/python/test_devices_view_polish.py`:

```python
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML = PROJECT_ROOT / "src" / "python" / "web_static" / "index.html"
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"
STYLES_CSS = PROJECT_ROOT / "src" / "python" / "web_static" / "styles.css"

DEVICE_GROUP_VIEWS = ["lights", "plugs", "ambient", "humidifier", "environment", "tuya", "climate"]


def _group_colors(css: str) -> dict[str, str]:
    """Map each device-group view to the --group-color variable it resolves to.

    Parses rules of the form:
        .room-item[data-view="lights"],
        .device-group-tile[data-goto-view="lights"] { --group-color: var(--amber); }
    """
    colors: dict[str, str] = {}
    for block in re.finditer(r"([^{}]+)\{([^{}]*--group-color\s*:\s*([^;}]+)[;}][^{}]*)\}", css):
        selector, _body, value = block.group(1), block.group(2), block.group(3).strip()
        for view in re.findall(r'data-view="([^"]+)"', selector):
            colors[view] = value
        for view in re.findall(r'data-goto-view="([^"]+)"', selector):
            colors[view] = value
    return colors


def test_new_palette_colors_are_defined_before_use() -> None:
    css = STYLES_CSS.read_text(encoding="utf-8")

    assert "--teal:" in css
    assert "--indigo:" in css
    # Must be declared in :root before any rule references them.
    root_end = css.index("}", css.index(":root"))
    root_block = css[:root_end]
    assert "--teal:" in root_block
    assert "--indigo:" in root_block


def test_every_device_group_resolves_a_group_color() -> None:
    colors = _group_colors(STYLES_CSS.read_text(encoding="utf-8"))

    missing = [v for v in DEVICE_GROUP_VIEWS if v not in colors]
    assert not missing, f"no --group-color for: {missing}"


def test_no_two_device_groups_share_a_colour() -> None:
    """The bug this guards: devices/plugs both used --accent and
    environment/tuya both used --cyan before this change."""
    colors = _group_colors(STYLES_CSS.read_text(encoding="utf-8"))
    used = {v: colors[v] for v in DEVICE_GROUP_VIEWS}

    duplicates = {c for c in used.values() if list(used.values()).count(c) > 1}
    assert not duplicates, f"colour reused across sibling groups: {duplicates} in {used}"


def test_sidebar_icon_reads_the_group_color_variable() -> None:
    """Sidebar and tile must consume one definition, or they drift apart."""
    css = STYLES_CSS.read_text(encoding="utf-8")

    assert re.search(r"\.room-icon\s*\{[^}]*color:\s*var\(--group-color", css)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m pytest tests/python/test_devices_view_polish.py -v`
Expected: FAIL — `--teal:` not in css, and no `--group-color` rules exist yet.

- [ ] **Step 3: Add the two palette colours**

In `src/python/web_static/styles.css`, inside the `:root` block, immediately after the `--pink:` line:

```css
  --teal:         #2dd4bf;
  --indigo:       #818cf8;
```

- [ ] **Step 4: Replace the per-view icon colour block**

Find the existing block (around lines 381-388):

```css
.room-item[data-view="lights"]        .room-icon { color: var(--amber); }
.room-item[data-view="plugs"]         .room-icon { color: var(--accent); }
.room-item[data-view="environment"]   .room-icon { color: var(--cyan); }
.room-item[data-view="tuya"]          .room-icon { color: var(--cyan); }
.room-item[data-view="climate"]       .room-icon { color: var(--orange); }
.room-item[data-view="homeassistant"] .room-icon { color: var(--purple); }
.room-item[data-view="cameras"]       .room-icon { color: var(--green); }
.room-item[data-view="devices"]     .room-icon { color: var(--accent); }
```

Replace it entirely with:

```css
/* ── Per-group colour, defined once and consumed by BOTH the sidebar item and
   the Devices overview tile. Defining it twice is what let devices/plugs and
   environment/tuya silently collide before. ── */
.room-item[data-view="lights"],
.device-group-tile[data-goto-view="lights"]      { --group-color: var(--amber); }
.room-item[data-view="plugs"],
.device-group-tile[data-goto-view="plugs"]       { --group-color: var(--accent); }
.room-item[data-view="ambient"],
.device-group-tile[data-goto-view="ambient"]     { --group-color: var(--purple); }
.room-item[data-view="humidifier"],
.device-group-tile[data-goto-view="humidifier"]  { --group-color: var(--cyan); }
.room-item[data-view="environment"],
.device-group-tile[data-goto-view="environment"] { --group-color: var(--teal); }
.room-item[data-view="tuya"],
.device-group-tile[data-goto-view="tuya"]        { --group-color: var(--indigo); }
.room-item[data-view="climate"],
.device-group-tile[data-goto-view="climate"]     { --group-color: var(--orange); }

/* Top-level views outside the Devices group. Sharing a colour across sections
   is fine; sharing between siblings is not. */
.room-item[data-view="devices"]       { --group-color: var(--accent); }
.room-item[data-view="homeassistant"] { --group-color: var(--purple); }
.room-item[data-view="cameras"]       { --group-color: var(--green); }

.room-icon { color: var(--group-color, currentColor); }
```

Note `.room-item[data-view="devices"]` deliberately has no matching
`.device-group-tile` — Devices is the parent, not one of its own tiles.

- [ ] **Step 5: Check the two later per-view rules still work**

Two more icon-colour rules live further down the file (`alarm` at ~`:2872`, `home` at ~`:3266`) in the older `.room-icon { color: ... }` form. Convert them for consistency so every rule uses one mechanism:

```css
.room-item[data-view="alarm"] { --group-color: var(--red); }
```

```css
.room-item[data-view="home"] { --group-color: var(--pink); }
```

Because `.room-icon { color: var(--group-color, ...) }` appears earlier in the
file at equal specificity to nothing else, and these set only the variable,
source order no longer matters for them.

- [ ] **Step 6: Verify the active-state override still wins**

`.room-item.active .room-icon { color: var(--accent) !important; }` already exists further down. Confirm it is still present and unmodified — the active item must stay accent-coloured, not group-coloured. Run:

`grep -n "room-item.active .room-icon" src/python/web_static/styles.css`

Expected: the rule exists with `!important`. Do not change it.

- [ ] **Step 7: Run the tests**

Run: `python3 -m pytest tests/python/test_devices_view_polish.py -v`
Expected: 4 passed.

- [ ] **Step 8: Commit**

```bash
git add src/python/web_static/styles.css tests/python/test_devices_view_polish.py
git commit -m "feat: give each device group a distinct colour from one source"
```

---

### Task 2: Restyle the overview tiles

Top accent strip in the group colour, icon inline beside the label at 20px, count as the hero number.

**Files:**
- Modify: `src/python/web_static/app.js` (`renderDevicesOverview`, ~`:326`)
- Modify: `src/python/web_static/styles.css` (the `Devices overview tiles` block)
- Test: `tests/python/test_devices_view_polish.py` (extend)

**Interfaces:**
- Consumes: `--group-color` from Task 1; `deviceGroupTileData()` returning objects with `view`, `label`, `icon`, `count`, `summary`.
- Produces: tile markup containing `<div class="device-group-tile-accent">`, and CSS classes `.device-group-tile-accent`, `.device-group-tile-body`.

- [ ] **Step 1: Write the failing test**

Append to `tests/python/test_devices_view_polish.py`:

```python
def test_tile_markup_has_an_accent_strip_and_keeps_navigation() -> None:
    javascript = APP_JS.read_text(encoding="utf-8")

    assert "device-group-tile-accent" in javascript
    # Navigation still rides the existing document-level [data-goto-view] handler.
    assert 'data-goto-view="${escapeHtml(tile.view)}"' in javascript


def test_tile_accent_and_icon_read_the_group_colour() -> None:
    css = STYLES_CSS.read_text(encoding="utf-8")

    accent = re.search(r"\.device-group-tile-accent\s*\{([^}]*)\}", css)
    assert accent, "no .device-group-tile-accent rule"
    assert "var(--group-color" in accent.group(1)

    icon = re.search(r"\.device-group-tile-head\s+i\s*\{([^}]*)\}", css)
    assert icon, "no .device-group-tile-head i rule"
    assert "var(--group-color" in icon.group(1)


def test_tile_has_a_group_colour_fallback() -> None:
    """A group without an assignment must still render, not vanish."""
    css = STYLES_CSS.read_text(encoding="utf-8")

    tile = re.search(r"\.device-group-tile\s*\{([^}]*)\}", css)
    assert tile, "no .device-group-tile rule"
    assert "--group-color:" in tile.group(1), "tile needs a default --group-color"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m pytest tests/python/test_devices_view_polish.py -v`
Expected: FAIL — `device-group-tile-accent` not in app.js.

- [ ] **Step 3: Update the tile markup**

In `src/python/web_static/app.js`, find the template inside `renderDevicesOverview`:

```js
  grid.innerHTML = deviceGroupTileData().map((tile) => `
    <article class="device-group-tile" data-goto-view="${escapeHtml(tile.view)}">
      <div class="device-group-tile-head">
        <i class="ti ${tile.icon}" aria-hidden="true"></i>${escapeHtml(tile.label)}
      </div>
      <div class="device-group-tile-count">${tile.count}</div>
      <div class="device-group-tile-summary">${escapeHtml(tile.summary)}</div>
    </article>
  `).join("");
```

Replace it with:

```js
  grid.innerHTML = deviceGroupTileData().map((tile) => `
    <article class="device-group-tile" data-goto-view="${escapeHtml(tile.view)}">
      <div class="device-group-tile-accent" aria-hidden="true"></div>
      <div class="device-group-tile-body">
        <div class="device-group-tile-head">
          <i class="ti ${tile.icon}" aria-hidden="true"></i>${escapeHtml(tile.label)}
        </div>
        <div class="device-group-tile-count">${tile.count}</div>
        <div class="device-group-tile-summary">${escapeHtml(tile.summary)}</div>
      </div>
    </article>
  `).join("");
```

`tile.icon` stays uninterpolated-but-unescaped because it is one of seven
hardcoded literals in `deviceGroupTileData()` — never device-supplied. Every
device-supplied value (`view`, `label`, `summary`) keeps its `escapeHtml`.

- [ ] **Step 4: Replace the tile CSS**

In `src/python/web_static/styles.css`, replace the existing `.device-group-tile`, `.device-group-tile:hover`, `.device-group-tile-head`, `.device-group-tile-count` and `.device-group-tile-summary` rules with:

```css
.device-group-tile {
  --group-color: var(--muted);
  display: flex;
  flex-direction: column;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  overflow: hidden;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s, transform 0.15s;
}

.device-group-tile:hover {
  background: var(--card-2);
  border-color: var(--border-hover);
  transform: translateY(-1px);
}

.device-group-tile-accent {
  height: 3px;
  background: var(--group-color);
  flex-shrink: 0;
}

.device-group-tile-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 16px 18px 18px;
}

.device-group-tile-head {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text);
  font-size: 13px;
  font-weight: 500;
}

.device-group-tile-head i {
  font-size: 20px;
  color: var(--group-color);
}

.device-group-tile-count {
  font-family: var(--mono);
  font-size: 28px;
  line-height: 1;
  color: var(--text);
}

.device-group-tile-summary {
  font-size: 11px;
  color: var(--muted);
}
```

The `--group-color: var(--muted)` on `.device-group-tile` is the fallback: a
group with no colour assignment renders a grey strip rather than nothing.

- [ ] **Step 5: Verify the JS still parses**

Run: `node --check src/python/web_static/app.js`
Expected: no output, exit 0.

- [ ] **Step 6: Run the tests**

Run: `python3 -m pytest tests/python/test_devices_view_polish.py -v`
Expected: 7 passed.

- [ ] **Step 7: Commit**

```bash
git add src/python/web_static/app.js src/python/web_static/styles.css tests/python/test_devices_view_polish.py
git commit -m "feat: restyle Devices tiles with a group-coloured accent strip"
```

---

### Task 3: Return button on the seven device views

Shown only when the user arrived from the Devices overview.

**Files:**
- Modify: `src/python/web_static/index.html` (seven `section-header` blocks)
- Modify: `src/python/web_static/app.js` (`activateView` ~`:4531`; the `[data-goto-view]` handler ~`:4345`; the rail click handler ~`:4994`)
- Modify: `src/python/web_static/styles.css` (button spacing)
- Test: `tests/python/test_devices_view_polish.py` (extend)

**Interfaces:**
- Consumes: `activateView(viewName)`, `DEVICE_GROUP_VIEWS` (already contains the seven views in sidebar order).
- Produces: `arrivedFromDevices` (module-level boolean), `setDevicesBackVisible(show)`, buttons carrying `data-back-to-devices`.

- [ ] **Step 1: Write the failing test**

Append to `tests/python/test_devices_view_polish.py`:

```python
def test_all_seven_device_panels_have_a_hidden_back_button() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")

    for view in DEVICE_GROUP_VIEWS:
        start = html.index(f'data-view-panel="{view}"')
        panel = html[start:start + 700]
        assert "data-back-to-devices" in panel, f"{view} panel has no back button"
        button = re.search(r"<button[^>]*data-back-to-devices[^>]*>", panel)
        assert button, f"{view} back button is not a <button>"
        assert "hidden" in button.group(0), (
            f"{view} back button must ship hidden so it cannot flash before JS runs"
        )


def test_back_button_visibility_is_tracked_by_a_flag() -> None:
    javascript = APP_JS.read_text(encoding="utf-8")

    assert "arrivedFromDevices" in javascript
    assert "function setDevicesBackVisible" in javascript


def test_flag_is_only_set_for_clicks_inside_the_devices_panel() -> None:
    """data-goto-view is also used by the Home view's thermostat dial, camera
    frame and device rows, and by Area detail cards. Only the Devices overview
    may set the flag, or those other jumps would show a false back button."""
    javascript = APP_JS.read_text(encoding="utf-8")

    handler_at = javascript.index('closest("[data-goto-view]")')
    handler = javascript[handler_at:handler_at + 500]
    assert 'data-view-panel="devices"' in handler, (
        "the goto handler must scope the flag to the Devices panel"
    )


def test_sidebar_click_clears_the_flag() -> None:
    javascript = APP_JS.read_text(encoding="utf-8")

    at = javascript.index("railButtons.forEach")
    handler = javascript[at:at + 300]
    assert "arrivedFromDevices = false" in handler
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m pytest tests/python/test_devices_view_polish.py -v`
Expected: FAIL — `data-back-to-devices` not found in the lights panel.

- [ ] **Step 3: Add the button to the Lights panel**

The Lights panel already has a `.section-actions` wrapper. In `src/python/web_static/index.html`, inside that wrapper, add the button as its FIRST child (before the `section-meta` span):

```html
          <button class="command device-back-btn" type="button" data-back-to-devices hidden>
            <i class="ti ti-arrow-left" aria-hidden="true"></i> Devices
          </button>
```

- [ ] **Step 4: Add wrappers and buttons to the other six panels**

The other six have a bare `<span class="section-meta">` with no wrapper. For EACH of `plugs`, `ambient`, `humidifier`, `environment`, `tuya`, `climate`, replace the bare span with a wrapper containing the button and the original span. The exact replacements:

`plugs`:
```html
        <div class="section-actions">
          <button class="command device-back-btn" type="button" data-back-to-devices hidden>
            <i class="ti ti-arrow-left" aria-hidden="true"></i> Devices
          </button>
          <span class="section-meta">TP-Link · local control</span>
        </div>
```

`ambient`:
```html
        <div class="section-actions">
          <button class="command device-back-btn" type="button" data-back-to-devices hidden>
            <i class="ti ti-arrow-left" aria-hidden="true"></i> Devices
          </button>
          <span class="section-meta">Govee · Bluetooth (local control)</span>
        </div>
```

`humidifier`:
```html
        <div class="section-actions">
          <button class="command device-back-btn" type="button" data-back-to-devices hidden>
            <i class="ti ti-arrow-left" aria-hidden="true"></i> Devices
          </button>
          <span class="section-meta">Govee · Cloud API</span>
        </div>
```

`environment`:
```html
        <div class="section-actions">
          <button class="command device-back-btn" type="button" data-back-to-devices hidden>
            <i class="ti ti-arrow-left" aria-hidden="true"></i> Devices
          </button>
          <span class="section-meta">Temperature &amp; humidity</span>
        </div>
```

`tuya`:
```html
        <div class="section-actions">
          <button class="command device-back-btn" type="button" data-back-to-devices hidden>
            <i class="ti ti-arrow-left" aria-hidden="true"></i> Devices
          </button>
          <span class="section-meta">Tuya / Home Assistant</span>
        </div>
```

`climate`:
```html
        <div class="section-actions">
          <button class="command device-back-btn" type="button" data-back-to-devices hidden>
            <i class="ti ti-arrow-left" aria-hidden="true"></i> Devices
          </button>
          <span class="section-meta">Ecobee thermostats</span>
        </div>
```

- [ ] **Step 5: Add the CSS**

In `src/python/web_static/styles.css`, after the `.section-actions` rule (~`:542`):

```css
/* [hidden] must beat .command's inline-flex, same idiom as .room-item[hidden]. */
.device-back-btn[hidden] { display: none; }
```

- [ ] **Step 6: Add the flag and the visibility helper**

In `src/python/web_static/app.js`, immediately after the `DEVICE_GROUP_VIEWS` declaration:

```js
/* Tracks whether the current view was reached from the Devices overview, so the
   back button only appears when there is somewhere to go back to. Deliberately
   not persisted: it describes one navigation step, not a preference. */
let arrivedFromDevices = false;

function setDevicesBackVisible(show) {
  document.querySelectorAll("[data-back-to-devices]").forEach((btn) => {
    btn.hidden = !show;
  });
}
```

- [ ] **Step 7: Scope the flag to the Devices panel**

Find the generic goto handler (~`:4345`):

```js
  const gotoCard = event.target.closest("[data-goto-view]");
  if (gotoCard) activateView(gotoCard.dataset.gotoView);
```

Replace with:

```js
  const gotoCard = event.target.closest("[data-goto-view]");
  if (gotoCard) {
    // data-goto-view is also used by the Home view's thermostat dial, camera
    // frame and device rows, and by Area detail cards. Only a jump from the
    // Devices overview should arm the back button.
    arrivedFromDevices = Boolean(gotoCard.closest('[data-view-panel="devices"]'));
    activateView(gotoCard.dataset.gotoView);
  }
```

- [ ] **Step 8: Clear the flag on direct sidebar navigation**

Find the rail handler (~`:4994`):

```js
railButtons.forEach((btn) => {
  btn.addEventListener("click", () => activateView(btn.dataset.view));
});
```

Replace with:

```js
railButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    arrivedFromDevices = false;
    activateView(btn.dataset.view);
  });
});
```

- [ ] **Step 9: Drive visibility from `activateView`**

In `activateView` (~`:4531`), inside the existing `if (DEVICE_GROUP_VIEWS.includes(viewName))` block, add the visibility call, and hide the button for every other view. The block currently reads:

```js
  if (DEVICE_GROUP_VIEWS.includes(viewName)) {
    setDevicesGroupOpen(true);
  }
```

Replace with:

```js
  if (DEVICE_GROUP_VIEWS.includes(viewName)) {
    setDevicesGroupOpen(true);
    setDevicesBackVisible(arrivedFromDevices);
  } else {
    setDevicesBackVisible(false);
  }
```

- [ ] **Step 10: Wire the button itself**

Add near the other top-level event wiring, after the `railButtons.forEach` block:

```js
/* Back to the Devices overview */
document.addEventListener("click", (event) => {
  if (!event.target.closest("[data-back-to-devices]")) return;
  arrivedFromDevices = false;
  activateView("devices");
});
```

- [ ] **Step 11: Verify the JS parses**

Run: `node --check src/python/web_static/app.js`
Expected: no output, exit 0.

- [ ] **Step 12: Run the full relevant test set**

Run: `python3 -m pytest tests/python/test_devices_view_polish.py tests/python/test_dashboard_devices_group.py tests/python/test_dashboard_environment_split.py tests/python/test_dashboard_layout.py -v`
Expected: all pass.

- [ ] **Step 13: Confirm no regression in the wider suite**

Run: `python3 -m pytest tests/python/ -q`
Expected: `4 failed, N passed, 7 errors` — the same 4 failures and 7 errors as before. Flag any other deviation.

- [ ] **Step 14: Commit**

```bash
git add src/python/web_static/index.html src/python/web_static/app.js src/python/web_static/styles.css tests/python/test_devices_view_polish.py
git commit -m "feat: add a Devices return button shown only when arriving from the overview"
```

---

## Self-Review

**Spec coverage:**

| Spec section | Task |
|---|---|
| Part 1 — one colour source, `--group-color` indirection | 1 |
| Part 1 — `--teal` / `--indigo` added, seven distinct assignments | 1 |
| Part 2 — top accent strip, 20px coloured icon, 28px hero count, hover lift | 2 |
| Part 2 — `--group-color` fallback so an unassigned group still renders | 2 (Step 4) |
| Part 3 — button in all seven headers, reusing `.command` | 3 (Steps 3-4) |
| Part 3 — `.section-actions` wrapper added where missing | 3 (Step 4) |
| Part 3 — conditional visibility, flag not persisted | 3 (Steps 6-10) |
| Testing — colour uniqueness check | 1 |
| Testing — buttons ship `hidden` | 3 (Step 1) |
| Testing — flag transitions | 3 (Step 1) |
| Testing — `--teal`/`--indigo` declared before use | 1 |

No spec requirement is unassigned.

**One deliberate refinement of the spec:** the spec proposed a Node-harness test for colour uniqueness. These assertions parse CSS, not JavaScript behaviour, so they are written as Python string/regex tests instead — the same style already used for CSS assertions elsewhere in the suite. No Node harness is needed for this plan.

**One risk the spec did not anticipate, now covered:** `data-goto-view` is used in five places, not just the Devices tiles — the Home view's thermostat dial (`app.js:3402`), camera frame (`:3542`) and custom device rows (`:3707`), and Area detail thermo cards (`:4070`). All share the single document-level handler at `:4345`. Task 3 Step 7 scopes the flag with `gotoCard.closest('[data-view-panel="devices"]')`, and Task 3 Step 1 has a test that fails if that scoping is missing. Without it, clicking a thermostat on the Home view would land on Climate showing a false "Devices" back button.

**Placeholder scan:** no TBD/TODO. Every code step carries complete code, including all six repeated button blocks written out in full rather than "same as above".

**Type consistency:** `setDevicesBackVisible(show)` is defined in Task 3 Step 6 and called in Steps 9 only. `arrivedFromDevices` is declared in Step 6 and read/written in Steps 7, 8, 9 and 10. `--group-color` is produced in Task 1 and consumed in Task 2. `DEVICE_GROUP_VIEWS` is pre-existing and already contains exactly the seven views this plan targets, in sidebar order.

**Ordering note for the executor:** Task 2 depends on Task 1's `--group-color`; Task 3 is independent of both but touches the same three files, so run the tasks in order rather than in parallel.
