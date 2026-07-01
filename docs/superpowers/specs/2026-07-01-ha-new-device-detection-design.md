# Home Assistant New-Device Detection & Auto-Placement — Design Spec
**Date:** 2026-07-01
**Status:** Approved

## Overview

Home Assistant `climate` and `sensor`/`binary_sensor` entities already flow automatically into their correct dashboard views today (Climate/Ecobee view, Sensors/Tuya view respectively — see `_ecobee_payload_from_home_assistant` and `_tuya_cards_from_home_assistant`), with no confirmation step. **`light`/`switch` domain entities are the one gap**: `_is_tuya_home_assistant_entity()` currently routes them into the Sensors/Tuya tab too (as `tuya_light`/`tuya_switch`), which is the wrong place — they belong in Lights/Plugs. This is almost certainly why the North bedroom light switch isn't where it's expected.

This spec is scoped to that gap: automatic detection of newly-appeared HA `light`/`switch` entities, a popup notification asking for confirmation, and — once confirmed — placement into the correct view (Lights or Plugs) with removal from the Sensors/Tuya tab so it isn't shown twice. Climate, sensor, binary_sensor, and all other domains are unaffected — their existing auto-inclusion behavior is untouched.

As an immediate, related change (not gated on this feature), the already-existing "North bedroom light switch" (a Tapo switch added to Home Assistant via Matter) is added to the Lights view directly, and excluded from the Sensors/Tuya tab.

## Persistence: known-entity registry

A new file `home_assistant_known_entities.json` at the project root (same pattern as the existing `tplink_switches.json` discovery cache — machine-managed, not user-edited, git-ignored) stores a JSON array of HA `entity_id` values that have already been handled (confirmed or ignored):

```json
{"known_entity_ids": ["light.kitchen", "switch.north_bedroom_light_switch", "..."]}
```

**Bootstrap:** the first time the dashboard runs after this ships (i.e. the file doesn't exist yet), it is seeded with every `light`/`switch` domain `entity_id` currently returned by HA's `/api/states`. This means no popups fire retroactively for pre-existing entities — only `light`/`switch` entities that appear in HA *after* this ships are treated as new. Only `light`/`switch` entities are tracked in this registry at all — other domains are out of scope (see Overview).

## Backend changes (`src/python/web_app.py`)

### Known-entity helpers
- `_load_known_ha_entities(path) -> set[str]`
- `_save_known_ha_entities(path, ids: set[str])`
- `_seed_known_ha_entities_if_missing(path, states)` — called once at startup; if the file doesn't exist, writes it with every current `light`/`switch` entity_id and returns immediately (no diffing needed on the seeding run).

### Type → view mapping
New pure function `_ha_light_switch_dashboard_category(device_class: str | None) -> str`, applied only to `light`/`switch` domain entities:

| HA domain | device_class | Result |
|---|---|---|
| `light` | any | `light_switch` (Lights view) |
| `switch` | `outlet` | `smart_plug` (Plugs view) |
| `switch` | other/none | `light_switch` (Lights view) |

All other domains (`climate`, `sensor`, `binary_sensor`, `cover`, `fan`, `lock`, `media_player`, ...) are unaffected by this feature and keep their exact current behavior.

### `/api/home-assistant/entities` change
Existing endpoint gains an `is_new: bool` field, set only for `light`/`switch` domain entities not yet in the known-set. All other domains always report `is_new: false` (or omit the field).

### New endpoints
| Method | Path | Body | Effect |
|---|---|---|---|
| POST | `/api/home-assistant/devices/{entity_id}/confirm` | `{name, room, category}` | Appends an entry to `home_assistant_devices:` in `configs/devices.local.yaml`; adds `entity_id` to the known-set file |
| POST | `/api/home-assistant/devices/{entity_id}/ignore` | — | Adds `entity_id` to the known-set file only |

### `devices.local.yaml` schema addition
```yaml
home_assistant_devices:
  # Written automatically when you confirm a new-device popup on the dashboard.
  - entity_id: switch.north_bedroom_light_switch
    name: North bedroom light switch
    room: North Bedroom
    category: light_switch
```
Also documented in `configs/devices.example.yaml` with a comment, matching the existing `matter.devices` section's style.

### Merging into views
`_device_cards()` (feeds `/api/devices`, which the Lights/Plugs views read) gains a step that reads `home_assistant_devices` from config, fetches current state for each listed `entity_id` from HA, and appends a card shaped like the existing TP-Link cards (`id`, `name`, `host` set to `entity_id`, `category`, `room`, `is_on`, `brightness`) so the frontend needs no changes to `cameraMedia`/`lightDevices` filtering logic. The card's command actions route through the existing HA service-call helper already used for HA-controlled entities.

### Excluding confirmed devices from the Sensors/Tuya tab
`_is_tuya_home_assistant_entity()` already excludes TP-Link-named entities via the `tplink_names` set (line ~856-861 today) so they don't show up twice. This gets the same treatment: it gains a `confirmed_ha_entity_ids: set[str]` parameter (the `entity_id`s listed under `home_assistant_devices` in config) and returns `False` early if `entity_id in confirmed_ha_entity_ids`. `_tuya_cards_from_home_assistant()` is updated to load and pass this set. This is what makes a confirmed light/switch disappear from Sensors once it's placed in Lights/Plugs — otherwise it would show in both tabs.

## Frontend changes (`src/python/web_static/app.js`)

- In `loadDevices()`, after `homeAssistantData` is fetched (already polled every 60s), iterate entities with `is_new: true`. For each one not already surfaced, call `pushNotification("new_device", ...)` using the existing notif-banner system (the same one used for doorbell-ring alerts today), with `meta: {entityId, suggestedName, suggestedRoom, suggestedCategory}`.
- `respondToNotification()` gains a `new_device` branch: opens a small modal (structurally the same as the existing Matter commissioning modal — `#matterModal`/`initMatterModal()` pattern) pre-filled with the HA friendly name and a room guessed via the existing `_room_from_name()` helper, showing the auto-picked view/category as editable fields.
- Modal Confirm → `POST /api/home-assistant/devices/{entity_id}/confirm` with the (possibly edited) name/room/category, then dismiss the notification and refresh devices.
- Modal Cancel / banner "Close" → `POST /api/home-assistant/devices/{entity_id}/ignore`, dismiss notification. Per design decision, ignored devices never resurface.

## North bedroom light switch (immediate one-off)

Added directly as a `home_assistant_devices:` entry in `configs/devices.local.yaml` in the same change, with `category: light_switch`. It will also be present in the initial seed of the known-entity registry (since it already exists in HA), so it will not additionally trigger a popup.

## Error handling / edge cases

- HA unreachable: `/api/home-assistant/entities` already degrades gracefully today (returns empty/cached data per existing behavior); no new-device detection runs that cycle, nothing else breaks.
- Confirmed device later removed from HA: card simply stops updating (shows last-known/unavailable state), same as any other HA entity today — no special handling needed.
- Multiple new entities in the same poll each get their own notification banner, consistent with existing multi-notification behavior (e.g. multiple doorbell events).
- Renaming/removing a confirmed device: reuses the existing per-view rename/remove UI (e.g. `data-camera-edit`-style pattern already present for other device types) — not new UI.

## Testing

- Backend: new `tests/python/test_home_assistant_new_devices.py` covering:
  - `_ha_light_switch_dashboard_category` mapping (the `switch`+`outlet` vs `switch`+none distinction)
  - Seed-on-first-run behavior (no `is_new` entities immediately after seeding)
  - `is_new` correctly true for a light/switch entity_id absent from the known-set, false after confirm or ignore, and always false for non-light/switch domains
  - `confirm` endpoint writes the correct shape into `devices.local.yaml` and updates the known-set
  - `ignore` endpoint updates the known-set without touching `devices.local.yaml`
  - A confirmed entity_id is excluded from `_tuya_cards_from_home_assistant()`'s output (no duplicate in Sensors tab)
- Frontend: manual verification via the browser preview — remove an entity_id from the known-set file, reload, confirm the notification banner appears with correct suggested name/room/category, confirm the modal Confirm/Ignore paths both work and the device appears in (or is absent from) the Lights view afterward.

## What Doesn't Change

- The "Home Asst" tab continues to show all entities in `include_domains` exactly as it does today, regardless of new-device popup state.
- Existing TP-Link, Tuya, Matter (this Pi's own fabric), and camera flows are untouched.
- `climate`, `sensor`, `binary_sensor`, `cover`, `fan`, `lock`, and any other non-light/switch domain keep their exact current behavior (auto-included in Climate/Ecobee or Sensors/Tuya tabs as applicable today) — never trigger a popup, never touched by the new known-entity registry.

## Non-Goals

- Auto-detecting removed/deleted HA entities (no "device disappeared" notification).
- Editing a confirmed device's category after the fact from the popup flow (use the existing per-view rename UI instead).
- Any change to how devices are detected/added on the TP-Link or Tuya side — this is HA-entity-specific.
