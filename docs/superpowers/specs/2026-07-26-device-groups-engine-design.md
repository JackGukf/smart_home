# User-Managed Device Groups — Engine (Cycle 1 of 2)

**Date:** 2026-07-26
**Status:** Approved

## Goal

Turn the seven hardcoded device groups into data, so a later cycle can let the
user create groups and move devices between them.

**Cycle 1 (this spec) ships zero visible change.** It delivers the data model,
the CRUD and ordering API, the membership-resolution rules, and a sidebar
rendered from that data — seeded so the dashboard looks and behaves exactly as
it does today. Built-in group panels keep their existing dedicated renderers,
untouched.

**Cycle 2 (separate spec)** adds the visible value: a Manage Devices modal, a
New Group flow, and a generic mixed-device renderer for user-created groups.

Splitting this way means the risky refactor lands behind an exact, asserted
baseline rather than behind visual confidence.

## Part 1: Data model

New file `dashboard_device_groups.json`, alongside the existing
`dashboard_areas.json` and loaded with the same tolerance for a missing,
empty, or `null` document.

```json
{
  "groups": [
    {"id": "lights", "name": "Lights", "icon": "bulb", "color": "amber",
     "kinds": ["light"], "chrome": ["lightScenes", "lightDragLock"], "builtin": true},
    {"id": "plugs", "name": "Plugs", "icon": "plug", "color": "accent",
     "kinds": ["plug"], "chrome": ["plugActions"], "builtin": true},
    {"id": "ambient", "name": "Ambient", "icon": "lamp-2", "color": "purple",
     "kinds": ["ambient"], "chrome": [], "builtin": true},
    {"id": "humidifier", "name": "Humidifiers", "icon": "droplet", "color": "cyan",
     "kinds": ["humidifier"], "chrome": [], "builtin": true},
    {"id": "environment", "name": "Environment", "icon": "temperature-celsius",
     "color": "teal", "kinds": ["sensor", "environment"],
     "readingFilter": "environment", "chrome": [], "builtin": true},
    {"id": "tuya", "name": "Sensors", "icon": "radar-2", "color": "indigo",
     "kinds": ["sensor"], "readingFilter": "sensors", "chrome": [], "builtin": true},
    {"id": "climate", "name": "Climate", "icon": "temperature", "color": "orange",
     "kinds": ["thermostat"], "chrome": [], "builtin": true}
  ],
  "overrides": {}
}
```

### A group's `id` is its `data-view` value

The Sensors group seeds with **`id: "tuya"`**, display name `"Sensors"`. This is
deliberate and load-bearing: `data-view="tuya"` is what the sidebar uses today
and what `localStorage`'s `default_view` may already hold. Renaming the id to
`sensors` would silently break a saved startup view. A test asserts a persisted
`default_view` of `tuya` still resolves.

The same reasoning fixes the other six ids to `lights`, `plugs`, `ambient`,
`humidifier`, `environment`, `climate`.

### Display order is array order

The `groups` array order is the sidebar order. There is no `order` integer to
drift out of sync with it.

## Part 2: Membership resolution

### Automatic membership is multi-valued

```
auto(group)   = devices whose kind is in group.kinds
members(group) = (auto(group) minus devices whose override excludes this group)
                 ∪ (devices whose override includes this group)
```

A device may belong to several groups at once. This is essential rather than
incidental: a 4-in-1 sensor legitimately appears in both Environment and
Sensors, because those are two views of its readings, not two competing homes.

### `overrides` shape

```json
"overrides": {
  "<deviceKey>": { "include": ["groupId", ...], "exclude": ["groupId", ...] }
}
```

Cycle 1 defines this shape and honours it in resolution, and ships the endpoint
that writes it — but no UI calls that endpoint yet. Defining it now means Cycle 2
adds UI against a proven API instead of migrating a simpler `deviceKey → groupId`
map, which could not express multi-group membership at all.

`deviceKey` values come from the existing `collectHomeInventory()` scheme
(`dev:`, `sensor:`, `cam:`, `thermo:`, `ambient:`, `humidifier:`, and the new
`env:`).

### The sensor-split limitation, stated plainly

`readingFilter` applies **only to `sensor`-kind members**. `environment`-kind
devices (the standalone Govee cloud sensors) are rendered whole.

Because a single device can be excluded from one split group and not the other,
overrides on sensor-split devices are expressible but not yet exercised by any
UI. **Cycle 1 leaves sensor-split membership rule-driven.** Cycle 2 decides
whether Manage Devices offers per-group include/exclude for these devices or
keeps them rule-only; either way the model already supports both.

### `collectHomeInventory()` gains the missing kind

`collectHomeInventory()` currently produces `light`, `plug`, `sensor`, `camera`,
`thermostat`, `ambient`, `humidifier` — but **not** the standalone Govee
environment sensors, which are absent from the shared inventory entirely. This
spec adds them as `kind: "environment"` with key `env:<name>`, so the Environment
group can collect them by rule.

## Part 3: Backend API

Mirrors the Areas endpoints in shape, validation style, and error codes.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/device-groups` | The whole document |
| POST | `/api/device-groups` | Create a user group |
| PATCH | `/api/device-groups/{id}` | Rename / recolour / change icon |
| DELETE | `/api/device-groups/{id}` | Delete a **non-built-in** group |
| PUT | `/api/device-groups/order` | Reorder; body is a list of ids |
| PUT | `/api/device-groups/overrides` | Set one device's include/exclude |

### Creation policy

`POST` accepts **only** `name`, `icon`, `color`.

- `kinds` defaults to `[]` — a user-created group is empty until Cycle 2 gives
  it members. This is intended for Cycle 1 and stated here so it is not mistaken
  for an oversight.
- `chrome` and `readingFilter` are **not client-settable**. A request carrying
  either is rejected with 400. They exist only on seeded built-ins.
- `builtin` is server-assigned `false` and never accepted from a client.

### Validation

- `name`: non-empty, ≤ 40 chars, unique **case-insensitively** across both `name`
  and derived `id`. 409 on collision.
- `id`: slug derived from name, same helper as areas. 400 if it slugs to empty.
- `color`: must be one of `accent`, `amber`, `cyan`, `green`, `indigo`, `orange`,
  `pink`, `purple`, `red`, `slate`, `teal`. Anything else → 400 on write, and →
  `slate` on load (a hand-edited file must not break the dashboard).
- `icon`: `^[a-z0-9-]{1,32}$`. Anything else → 400 on write, `"device-desktop"`
  on load.
- `kinds`: every entry must be one of `light`, `plug`, `sensor`, `camera`,
  `thermostat`, `ambient`, `humidifier`, `environment`. 400 otherwise.
- `readingFilter`, where present: `environment` or `sensors`. 400 otherwise.
- `DELETE` on a `builtin` group → 409. Deleting a built-in would strip a device
  kind of its only home; whether to allow it is a Cycle 2 decision, taken
  alongside the UI that would offer it.
- `PUT /order`: the body must be a permutation of the existing ids — no
  additions, no omissions, no duplicates. 400 otherwise.
- `PUT /overrides`: unknown group ids → 404. Unknown device keys are **accepted**
  and stored, because a device may be offline or not yet discovered when the
  override is written.

### Stale data is tolerated, not enforced

Deleting a group leaves override entries naming it. Resolution ignores unknown
group ids rather than erroring, and the loader prunes them on next save. Same
for renamed groups: an id never changes on rename (only `name` does), so renames
cannot orphan an override.

## Part 4: Colour and icon safety

`color` and `icon` originate in a JSON file that a user may hand-edit, and both
reach the DOM — `color` as a CSS custom property, `icon` inside
`class="ti ti-<icon>"`. Neither is ever interpolated into a markup string.

- Validation runs **server-side on write and again on load**, so a hand-edited
  file cannot smuggle a value past the API.
- The palette name maps to a fixed CSS variable through a lookup table. The
  value written to the DOM is always `var(--<name>)` chosen from the allowlist,
  never a caller-supplied string.
- The property is set with `element.style.setProperty("--group-color", …)`, not
  by building a `style="…"` attribute.
- The icon class is set with `classList.add()` after the pattern check.

This replaces the static per-group CSS block introduced in the previous cycle —
static rules cannot cover groups that do not exist at build time.

## Part 5: Sidebar rendered from data

`renderDeviceGroupNav()` builds the child `<li>` elements from the group
document and injects them between the Devices parent and the Home Asst item.
Each carries `class="room-item device-group-item"`, `data-view="<id>"`, its
badge, and its `--group-color` set via the DOM API.

Everything built in the previous cycle keeps working unchanged, because the ids
are unchanged: `DEVICE_GROUP_VIEWS`, the collapse/persist behaviour, the
`arrivedFromDevices` back button, and the overview tiles.

`DEVICE_GROUP_VIEWS` stops being a hardcoded array and becomes derived from the
loaded groups.

## Part 6: Built-in panels are not touched

Built-in groups keep their existing dedicated renderers: `renderDevices`
(lights and plugs into their separate grids), `renderAmbientLights`,
`renderHumidifiers`, `renderEnvironmentSensors`, `renderTuyaDevices`, and the
thermostat renderer.

`renderAreaDetail()` is **not** reused for them. Its switch section deliberately
merges lights and plugs into one "Lights & Plugs" block; adopting it would
silently change two panels that are separate today. The generic mixed-device
renderer arrives in Cycle 2 and serves **only user-created groups**.

This is the single biggest reduction in this cycle's regression risk.

## Testing

Baseline fidelity — the point of the cycle:

- The seeded document reproduces today's seven groups exactly: ids, names,
  icons, colours, kinds, and order. Asserted field by field against the values
  currently in `index.html` and `styles.css`, so "no visible change" is proven
  rather than assumed.
- A persisted `default_view` of `tuya` still resolves after the refactor.

Resolution:

- A type rule collects a matching device.
- An `exclude` override removes a device from an otherwise-matching group.
- An `include` override adds a device to a group its kind does not match.
- A sensor device appears in **both** Environment and Sensors.
- An override naming a deleted group is ignored, not fatal.
- An override for an unknown device key is stored and ignored harmlessly.

API:

- Duplicate name differing only by case → 409.
- `chrome` or `readingFilter` in a POST body → 400.
- Invalid `kinds` entry, invalid `readingFilter`, invalid `icon` → 400.
- `color: "red"` → accepted. `color: "red; background:url(x)"` → 400 on write,
  and coerced to `slate` when present in a hand-edited file on load.
- `DELETE` on a built-in → 409; on a user group → 200.
- `PUT /order` with a missing, extra, or duplicated id → 400.

Loader tolerance, per the `d11e07e` pattern: missing file, `null` document,
`null` `groups`, `null` `overrides` — each returns the seeded default rather
than raising.

## Out of scope (Cycle 2)

- Manage Devices modal and New Group modal.
- The generic mixed-device renderer for user-created groups.
- Whether Manage Devices offers per-group include/exclude for sensor-split
  devices, or keeps them rule-driven.
- Whether built-in groups become deletable, and where their devices go if so.
- Any change to the Areas feature, which keeps its own separate document.
