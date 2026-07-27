# User-Managed Device Groups — UI (Cycle 2 of 2)

**Date:** 2026-07-26
**Status:** Approved

## Goal

Cycle 1 turned the seven device groups into data: a document, a CRUD API, a
membership-resolution engine, and a sidebar driven by the loaded groups. But
nothing consumes the engine — `resolveDeviceGroupMembers` is defined and never
called, and the seven panels still render by type filter. An override written
through the API today has no visible effect anywhere.

This cycle makes groups real:

1. **Panels render membership**, not type filters — this activates the engine.
2. **Manage Devices** — move any device into or out of any group.
3. **New Group / Edit / Delete** — full lifecycle, including built-ins.
4. **Dynamic panels** for groups with no static markup.
5. **Remove the `railButtons` staleness class** rather than patching it.

## Part 1: Membership-driven panels

Each of the seven renderers currently selects devices by type
(`category === "light_switch"`, or taking a `latest*` array wholesale). Each
switches to the group's resolved members:

```js
resolveDeviceGroupMembers(group, collectHomeInventory(), overrides).map((m) => m.data)
```

With an empty `overrides` map, membership is exactly the old type filter, so the
seeded baseline still asserts zero visible change. That equivalence is the
regression gate for this part.

### Foreign kinds must not vanish

Once any device can be ticked into any group, a bespoke renderer can receive a
shape it cannot handle — a thermostat in Lights, where `renderDevices` expects
switch-shaped objects.

Each built-in panel therefore renders in two passes:

- Its **native kinds** through its existing bespoke renderer, unchanged. Lights
  keeps its dimmer dials and scene row, Humidifiers keeps its mist orb, Climate
  keeps its setpoints.
- Any **foreign kinds** through the generic mixed-device renderer from Part 4,
  appended below as its own section.

Nothing a user ticks silently disappears, and no bespoke renderer is handed a
shape it was not written for.

## Part 2: The implicit Unassigned group

Built-in groups become deletable (Part 5). Deleting Lights would otherwise strip
every light of its only rule-based home and they would vanish from the dashboard.

A synthetic group prevents that, mirroring the Areas feature's existing
`auto:unassigned` bucket (`app.js:3280`) in both id shape and behaviour:

```js
{ id: "auto:unassigned", name: "Unassigned", icon: "help-hexagon",
  color: "slate", kinds: [], builtin: false, synthetic: true }
```

- It collects every inventory device that resolves into **no** group.
- It appears in the sidebar and the Devices overview **only when non-empty**.
- It always sorts last, like its Areas counterpart.
- It is never persisted, never editable, never deletable, and is rejected by the
  API as a group id.
- Its panel uses the generic renderer, since its contents are arbitrary.

Devices can therefore never become invisible, whatever the user deletes.

## Part 3: Manage Devices

A `Manage Devices` button in each group panel's section header, beside the back
button, mirroring the Areas `#areaManageButton`.

The modal lists every device in `collectHomeInventory()` with a checkbox:
checked means "member of this group". Each row shows the device icon, name, kind,
and **why it is or is not a member** — `by rule`, `added`, or `removed` — so the
state is never opaque.

### Toggling writes only deviations from the rule

| Rule says | User wants | Written |
|---|---|---|
| member | member | override cleared |
| member | not member | `exclude` gains this group |
| not member | member | `include` gains this group |
| not member | not member | override cleared |

The override document stores only deviations, so a later change to a group's
`kinds` still flows through to devices the user never touched.

### The merge requirement

`PUT /api/device-groups/overrides` **replaces a device's entire entry**. When
toggling group X, the client must send that device's existing `include` and
`exclude` for every *other* group alongside the change.

Sending only group X would silently wipe the same device's Environment override.
This is the single most likely correctness bug in this cycle and has a dedicated
test.

### Sensor-split devices

Cycle 1 left sensor-split devices rule-driven and flagged the decision here.
They are now fully manageable: Environment and Sensors are independent
checkboxes, so a 4-in-1 can be removed from one while staying in the other. That
is exactly what per-group include/exclude was designed to express.

## Part 4: New Group, Edit, Delete, and the generic renderer

### The group modal

One modal serves create and edit, following `#areaModal`:

- **Name** — text, ≤ 40 chars.
- **Icon** — a picker like `#areaIconPicker`, using a device-oriented icon list.
- **Colour** — eleven swatches, one per allowed palette name, rendered from the
  same allowlist the API validates against so the two cannot drift.

`POST` on create, `PATCH` on edit. Delete sits in the edit modal behind a
confirmation naming the group.

A created group has `kinds: []`, so it starts empty and is populated through
Manage Devices. That is the intended flow, not a gap.

### The generic mixed-device renderer

`renderGenericGroupBody(members)` renders one section per device kind present,
dispatching to the existing per-kind card renderers exactly as `renderAreaDetail`
does (`areaThermoCardHtml`, `ambientLightCard`, `humidifierCard`,
`renderSensorDeviceCard`, `cameraCardHtml`, `environmentSensorCard`, and the
switch grid).

It is deliberately **extracted from** `renderAreaDetail` and shared, rather than
copied — the two have identical needs, and a copy would drift. `renderAreaDetail`
is refactored to call it, which is the one piece of Areas code this cycle
touches.

### Dynamic panels

A group with no static panel gets one created on demand: a
`<div class="view-panel" data-view-panel="<id>">` containing a section header
(title, back button, Manage Devices, Edit) and a body from the generic renderer.
Panels are created into the same container as the static ones.

A deleted built-in leaves its static panel behind as unreachable markup — no nav
item activates it. Recreating a group whose name slugs to the same id reuses that
panel, which is harmless: the panel is membership-driven, so it renders whatever
the new group actually contains.

## Part 5: API change — built-in groups become deletable

`DELETE /api/device-groups/{group_id}` currently returns 409 for a `builtin`
group. That check is removed; any group may be deleted.

`builtin` keeps its meaning as "seeded, and may carry `chrome` / `readingFilter`"
— it simply no longer gates deletion.

Existing override-cleanup on delete is unchanged, and remains correct: the
deleted id is stripped from every include and exclude list, and entries left
empty are dropped.

`auto:unassigned` is rejected as a group id on create, so the synthetic bucket
can never be shadowed by a real group.

## Part 6: Removing the `railButtons` staleness class

`railButtons` is a `const` snapshot of the static `<li>` elements taken at module
load (`app.js:136`). Once groups can be created, an appended nav item is absent
from it — losing active-class toggling, startup-view validation, and its entry in
the startup dropdown.

Re-deriving the snapshot after each sync would fix the symptom but introduce a
double-registration hazard, since `syncDeviceGroupNav` attaches its own click
listener to items it creates.

This cycle removes the class of bug instead:

- Replace the snapshot with `railButtonEls()`, which queries the DOM fresh at
  each use. Always correct, and the cost is negligible at this list size.
- Replace the per-item click listeners with **one delegated listener** on the
  sidebar list, matched on `.room-item[data-view]`. `syncDeviceGroupNav` then
  attaches no listeners at all, so no item can be double-registered or
  unregistered.

## Testing

Baseline fidelity remains the gate:

- With no overrides, every one of the seven panels renders exactly the device set
  it renders today. This is what proves Part 1 is a behaviour-preserving swap.
- The seeded document still matches the live sidebar, as in Cycle 1.

Membership and overrides:

- The override merge: toggling group X for a device that already has an
  Environment override preserves the Environment entry. This is the cycle's most
  likely bug.
- Each of the four toggle transitions in the Part 3 table produces the stated
  document.
- A 4-in-1 removed from Environment remains in Sensors.

Unassigned and deletion:

- Deleting a group moves its rule-only members into `auto:unassigned` rather than
  making them disappear.
- `auto:unassigned` is hidden when empty and always sorts last.
- `auto:unassigned` is rejected as a create id.
- Deleting a built-in now returns 200, and its overrides are cleaned up.

Foreign kinds:

- A thermostat included in Lights renders in a generic section, and the light
  grid does not receive it.

Navigation:

- A newly created group's nav item gets the active class when activated, appears
  in the startup-view dropdown, and validates as a saved `default_view` — the
  four things the old snapshot broke.
- One click on a nav item activates exactly one view (guards double-registration).

## Out of scope

- Any change to the Areas feature beyond extracting the shared generic renderer.
- Reordering groups from the UI. The `PUT /order` endpoint exists from Cycle 1
  and stays API-only; drag-to-reorder is a separate piece of work.
- Editing a group's `kinds` rule from the UI. Rules stay seeded-only; membership
  is adjusted per device through Manage Devices.
- The mobile rail, which keeps the flattened behaviour established earlier.
