# Devices View Polish: Tile Styling + Return Button — Design

**Date:** 2026-07-26
**Status:** Approved

## Goal

The Devices overview panel shipped functional but visually plain: flat cards with
small muted icons. Two changes:

1. **Restyle the tiles** so each group reads at a glance, with a distinct colour
   and a larger icon, matching the colour already used in the sidebar.
2. **Add a return button** to each of the seven device views so the user can get
   back to the Devices overview.

This spec deliberately covers only these two items. User-managed device groups
(creating groups, assigning devices between them) are a separate, larger piece
of work with its own design cycle. See "Out of scope".

## Part 1: One colour source, consumed twice

### The problem

Per-view icon colours are hardcoded in the sidebar (`styles.css:381-388`). Two
pairs currently collide:

- `devices` and `plugs` both use `var(--accent)`
- `environment` and `tuya` (Sensors) both use `var(--cyan)`

The collision was invisible while icons were small and muted. Making them
colourful and larger makes it obvious. Hardcoding the colour a second time in
the tile CSS would guarantee the sidebar and the tile drift apart.

### The fix

Define each group's colour **once** as a custom property on both selectors, and
have the sidebar icon and the tile consume it:

```css
.room-item[data-view="lights"],
.device-group-tile[data-goto-view="lights"] { --group-color: var(--amber); }
```

Then `.room-icon { color: var(--group-color); }` and the tile's accent strip and
icon both read `var(--group-color)`. One edit changes both places.

### Colour assignments

The palette (`styles.css` `:root`) offers eight colours. Four are already claimed
by top-level views: Cameras `--green`, Home Asst `--purple`, Alarm `--red`, Home
`--pink`. Seven device groups need seven distinct colours, so two are added.

| Group | Variable | Change |
|---|---|---|
| Lights | `--amber` | unchanged |
| Plugs | `--accent` | unchanged |
| Ambient | `--purple` | new (was unset) |
| Humidifiers | `--cyan` | new (was unset) |
| Environment | `--teal` | **new palette var** — was colliding with Sensors |
| Sensors | `--indigo` | **new palette var** |
| Climate | `--orange` | unchanged |

New palette variables, following the existing naming and saturation:

```css
--teal:   #2dd4bf;
--indigo: #818cf8;
```

The **Devices parent** takes a new `--slate: #94a3b8;`. The table above covers
only the seven children, so the parent row would otherwise have stayed on
`--accent` alongside Plugs two rows below it — the very collision this section
set out to remove. A neutral tone also reads correctly: the parent is a
container, not another device category competing with its children.

Only Ambient (`--purple`) still matches a top-level view (Home Asst). Collisions
**across** sidebar sections are acceptable; collisions between rows visible at
the same time in the same section are what read as a bug.

`--group-color` must have a sensible fallback so a group without an assignment
still renders — default it to `var(--muted)` on `.device-group-tile`.

## Part 2: Tile restyle

Style direction: **top accent bar**. Chosen over an icon-chip treatment and a
fully tinted card; the strip marks the category without seven saturated
surfaces competing for attention.

Per tile:

- A 3px top strip in `var(--group-color)`. The card gets `overflow: hidden` so
  the strip follows the border radius.
- Icon inline beside the label, 20px, in `var(--group-color)`.
- The count becomes the hero: 28px, `var(--mono)`, `var(--text)`.
- The one-line summary sits beneath it in `var(--muted)`.
- Hover keeps the existing background and border-colour shift, plus a 1px lift
  via `transform: translateY(-1px)`.

The markup gains one element for the strip. Tiles keep their existing
`data-goto-view` attribute, so navigation continues to work through the existing
document-level handler with no JavaScript change.

**Do not add a `title` or `aria-label` duplicating the visible label** — the tile
already contains its own text.

## Part 3: Return button

### Placement

A button in the `section-header` of all seven device view panels, reusing the
existing `.command` class from `#homeAssistantBack` (`index.html:278`) so it
inherits the established button vocabulary. No new component.

```html
<button class="command device-back-btn" type="button" data-back-to-devices hidden>
  <i class="ti ti-arrow-left" aria-hidden="true"></i> Devices
</button>
```

Several device panels have a bare `<span class="section-meta">` rather than a
`.section-actions` wrapper. Those headers need the wrapper added so the button
and the meta text sit together, matching the Lights panel which already has one
(`index.html:200`).

### Visibility rule

The button appears **only when the user arrived from the Devices overview**, not
when they clicked the sidebar directly. One module-level flag:

- Clicking a tile in the Devices panel sets `arrivedFromDevices = true`.
- Clicking any sidebar rail item sets it `false`.
- `activateView` shows the back button only when entering one of the seven
  children with the flag set; it hides the button in every other case.
- Clicking the button calls `activateView("devices")` and clears the flag.

The flag is deliberately **not persisted**. It describes one navigation step, not
user preference, so a page reload should start clean with the button hidden.

### Why conditional

Always-on would be simpler, but a back button pointing somewhere the user never
came from is misleading. The cost is that the header shifts slightly depending on
entry path; that is accepted.

## Testing

- HTML assertions: all seven device panels contain a `data-back-to-devices`
  button, and each is `hidden` in the served markup so it never flashes before
  JavaScript runs.
- A Node-harness test (extending the existing `test_environment_split_logic.py`
  pattern — the repo has no JS toolchain and adding one stays out of scope)
  asserting that every one of the seven groups resolves a `--group-color` and
  that **no two siblings share a colour**. This is the check that would have
  caught the existing collision.
- JS assertions for the flag transitions: set on tile click, cleared on sidebar
  click, cleared after the back button fires.
- CSS assertion that `--teal` and `--indigo` are defined in `:root` before any
  rule references them.

## Out of scope

Deferred to a separate design cycle, by explicit decision:

- **User-managed device groups** — creating groups, assigning devices between
  them, and replacing the seven built-in type views with user-defined ones.
  Note for that work: `renderAreaDetail` (`app.js:4111`) already dispatches to
  the type-specific card renderers (`areaThermoCardHtml`, `ambientLightCard`,
  `humidifierCard`, `renderSensorDeviceCard`, `cameraCardHtml`), and
  `collectHomeInventory` (`app.js:4300`) already produces a unified mixed-device
  inventory with stable keys. Custom groups can reuse both, so replacing the
  built-ins does not cost the type-specific controls.

- Any change to the seven views' contents, the split logic, or the backend.
- Any change to the mobile rail behaviour.
