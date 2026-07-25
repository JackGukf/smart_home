# Devices Sidebar Group + Environment Sub-Group + Govee H5140 — Design

**Date:** 2026-07-24
**Status:** Approved

## Goal

The dashboard sidebar has grown to eleven flat view entries. Collapse the six
device-oriented views under a single **Devices** group, add a seventh
**Environment** child holding temperature and humidity readings, and connect a
newly added Govee H5140 thermo-hygrometer to that new view.

Three parts, in dependency order:

1. **Devices group** — sidebar restructure plus a Devices overview panel.
2. **Environment split** — carve temperature/humidity readings out of the
   existing Sensors view into a new Environment view.
3. **Govee H5140** — new standalone `govee_cloud` environment sensor, plus a
   fix for the H7140 regression that adding it would otherwise cause.

Home, Cameras, Home Asst, Alarm and Status stay as top-level views. The
Discovery and System sidebar sections are untouched.

## Part 1: Devices group

### Sidebar structure

```
Home
Cameras
Devices                 <- new group header, also a view
  |- Lights
  |- Plugs
  |- Ambient
  |- Humidifiers
  |- Environment        <- new (Part 2)
  |- Sensors            <- non-environmental readings only (Part 2)
  |- Climate
Home Asst
Alarm
Status
```

The six existing `<li>` entries keep their `data-view` values and source
position; they gain a `device-group-item` class. Environment is inserted
directly before Sensors so the two halves of the split sit adjacent.

New parent entry:

```html
<li class="room-item" id="devicesGroupToggle" data-view="devices">
  <span class="room-icon"><i class="ti ti-devices"></i></span>
  Devices
  <span class="room-badge" id="deviceGroupCount">-</span>
  <i class="ti ti-chevron-right settings-chevron" aria-hidden="true"></i>
</li>
```

### Styling

Reuse the existing collapsible vocabulary rather than inventing new visuals:

- `.device-group-item { padding-left: 24px; }` mirrors `.system-settings-item`
  (`styles.css:330`).
- `#devicesGroupToggle.open .settings-chevron { transform: rotate(90deg); }`
  mirrors the `#systemSettingsToggle` rule (`styles.css:328`).
- `.room-item[data-view="devices"] .room-icon` and
  `.room-item[data-view="environment"] .room-icon` get colours from the
  existing per-view palette block (`styles.css:377`).

### Interaction

- **Row click** — `activateView("devices")` and force the group open.
- **Chevron click** — toggle collapse only, with `stopPropagation()` so the
  active view does not change. The row always expands, so the chevron is the
  only way back to collapsed.
- State persists in `localStorage` under `devices_group_open_v1`, defaulting to
  open on a fresh browser.
- On load, if the restored startup view is one of the seven children, the group
  auto-expands so the active item is never hidden.

`railButtons` is derived from `.room-item[data-view]` (`app.js:136`), so
Devices and Environment appear in the startup-view dropdown automatically and
`getDefaultView()` validation keeps working. No change needed there.

### Devices overview panel

New `<div class="view-panel" data-view-panel="devices">`: a section header plus
a grid of seven tiles, one per child. Each tile shows icon, name, count and a
one-line summary (`3 of 7 on`, `2 online`, `avg 21.4 C`).

Two deliberate reuse decisions:

- Tiles carry `data-goto-view="lights"` and so on. A document-level handler for
  `[data-goto-view]` already exists (`app.js:4120`), so tile navigation needs
  **no new JavaScript**.
- The panel renders from arrays already in memory — `latestSwitchDevices`,
  `latestAmbientLights`, `latestHumidifiers`, `latestTuyaDevices`,
  `latestThermostats` (`app.js:177-183`) — plus `latestEnvironmentSensors` from
  Part 3. **No new backend endpoints and no new fetches.**

A single `renderDevicesOverview()` is called from `activateView("devices")` and
from the tail of each existing loader, so counts stay live.

### Devices badge

The badge counts **distinct physical devices**, not the sum of the seven child
badges. Part 2 makes a multi-capability sensor appear in both Environment and
Sensors, so a naive sum would double-count it and report more devices than the
user owns. De-duplicate on device identity before counting.

### Mobile rail

At `max-width: 900px` the sidebar is a 68px icon rail (56px at 480px), where
24px indentation and chevrons do not work. Inside the existing media query:

```css
#devicesGroupToggle { display: none; }
.device-group-item[hidden] { display: flex; }
```

The second rule has the same specificity as `.room-item[hidden]`
(`styles.css:318`), so it must appear **later in the file** to win. The rail
therefore looks and behaves exactly as it does today.

**Accepted consequence:** with the parent hidden, the Devices overview panel is
unreachable on a phone. This is a deliberate trade to keep mobile navigation
one-tap; revisit by keeping the icon visible if it proves annoying.

## Part 2: Environment split

### Where temperature and humidity live today

The Sensors view renders Home Assistant / Tuya entities grouped per physical
device into multi-capability cards (`renderSensorDeviceCard`, `app.js:1368`).
One device can report temperature, humidity, leak, smoke, tamper and battery at
once. `expandSensorReadings()` (`app.js:1333`) synthesises temperature,
humidity, illuminance and occupancy readings from raw Tuya `values` before the
card is built.

### Split rule

A device appears in **both** views, filtered to the relevant readings. One new
helper, applied **after** `expandSensorReadings()` so synthetic readings are
included:

```
filterReadingsForView(readings, mode)
  "environment" -> keep temperature + humidity (+ battery as context)
  "sensors"     -> drop temperature + humidity, keep the rest
```

`renderSensorDeviceCard(group, mode)` gains a mode parameter and filters before
its `findCat()` lookups. Because gauges and alert rows are both derived from
those lookups, they fall out correctly with **no change to the card markup**.

A group appears in a view only if it has at least one surviving **non-battery**
reading. Battery alone must not conjure a card into either view.

Net effect: a 4-in-1 shows temperature and humidity gauges in Environment, and
its leak/smoke/motion rows in Sensors. Nothing is lost, nothing is hidden.

### Scope boundary

Environment shows **only** Tuya/HA temperature-humidity sensors and the H5140.
It deliberately does not duplicate:

- **Ecobee thermostat readings** — Climate remains the single control surface
  for setpoints and modes, and owns its own readings.
- **The humidifier's linked thermometer** — that reading stays inside the
  humidifier orb where it provides context for mist control.

### Rendering

Environment reuses the existing `sdc-card` markup and the `device-grid`
container. No new card design; the only difference is which readings reach the
renderer.

## Part 3: Govee H5140

### What already exists

`_govee_thermometer_reading()` (`web_app.py:1709`) already parses
`sensorHumidity` and `sensorTemperature` capability instances from any Govee
cloud device. It is currently reachable only as a linked accessory of a
humidifier, via `_match_govee_thermometer()` (`web_app.py:1685`). Making the
H5140 a standalone device is therefore config plus endpoint plus reuse — **no
new Govee protocol code**.

### Capability verification precedes implementation

Before writing the endpoint, query `/router/api/v1/user/devices` on the Pi and
record the H5140's actual capability instances, exactly as was done for the
H7140. This design assumes `sensorTemperature` and `sensorHumidity`; if the
device reports different instances, the endpoint adapts to what was observed.
Do not infer the capability set from the model number.

#### Verified 2026-07-25

Ran `scripts/probe-govee-cloud-device.py` on the Pi against the live account.

The H5140 reports exactly the assumed capability instances, confirming
`_govee_thermometer_reading()` needs no changes for Task 5:

- `sensorTemperature` (type `devices.capabilities.property`)
- `sensorHumidity` (type `devices.capabilities.property`)
- `carbonDioxideConcentration` (type `devices.capabilities.property`) — extra;
  the device is Govee-labeled a "Smart CO₂ Monitor" that also reports ambient
  temperature/humidity. Its `device` id was obtained and is stored in
  `devices.local.yaml` on the Pi.

Running the probe with no SKU filter across the whole account found **2
devices exposing a `sensorHumidity` capability** (H5179 "Govee Thermometer"
and the H5140 above). This confirms the concern about
`_match_govee_thermometer()`'s final fallback in `web_app.py` ("the account's
sole ambient-humidity sensor") — with two humidity-capable devices now
present, that fallback can no longer assume uniqueness. The existing
CO2-exclusion tie-break in that function (preferring the sensor that lacks
`carbonDioxideConcentration`) already resolves this specific pair correctly,
but the underlying assumption of at-most-one sensor is confirmed false and
should be kept in mind for Task 7's regression work.

### Config schema

New top-level section in `configs/devices.example.yaml`:

```yaml
environment:
  sensors:
    # Govee thermo-hygrometers are read through the Govee Developer API v2.
    # Set GOVEE_API_KEY in the environment on the Pi - never here.
    # device_id is the "device" value from the Govee API device list. Leave
    # replace_me and the app matches by model when the account has exactly
    # one device of that model.
    - name: Bedroom Thermo-Hygrometer
      provider: govee_cloud
      model: H5140
      room: Bedroom
      device_id: replace_me
```

Real values go in `configs/devices.local.yaml` on the Pi, which is git-ignored.
The section must tolerate being `null` or absent, matching the fix in commit
`d11e07e` for the humidifiers and ambient_lights sections.

### Backend

Mirrors the humidifier structure in `web_app.py`:

- `EnvironmentSensorDefinition` dataclass — `name`, `provider`, `model`,
  `room`, `device_id`.
- A loader alongside the humidifier loader, null-tolerant as above.
- `GET /api/environment-sensors` returning `name`, `room`, `model`,
  `temperature`, `humidity`, `online`, built on the existing
  `_govee_thermometer_reading()`.
- Runtime cache keyed on stable config identity, following commit `24e0d33`
  which established that pattern for humidifiers.

**Unit conversion:** `_govee_thermometer_reading()` returns `temperature_f`,
since that is how Govee reports it. The endpoint converts to Celsius so the
value matches the rest of the dashboard.

### Frontend

- `loadEnvironmentSensors()` alongside `loadHumidifiers()`, populating
  `latestEnvironmentSensors`.
- Called from `activateView("environment")` and on initial load, matching how
  ambient lights and humidifiers are wired (`app.js:4793`).
- H5140 readings render as `sdc-card` entries in the Environment grid,
  alongside the Tuya/HA sensors from Part 2.

## Part 4: H7140 regression fix

`_match_govee_thermometer()` (`web_app.py:1685`) resolves the humidifier's
linked thermometer by explicit id, then model, then a fallback to *the
account's sole ambient-humidity sensor*. The example config ships
`device_id: replace_me`, so the H7140 currently depends on that fallback.

Adding the H5140 puts two humidity sensors on the account. Neither reports CO2,
so the `pure` filter does not disambiguate them, `len(sensors) == 1` fails, the
function returns `None`, and **the humidifier orb silently loses its humidity
and temperature readout**.

Fix: pin `thermometer_device_id` explicitly for the H7140 in config, and
document in `devices.example.yaml` that the fallback is only safe with exactly
one humidity sensor on the account.

## Testing

New coverage:

- `tests/python/test_dashboard_devices_group.py` — Devices item and panel exist;
  the seven children sit between Devices and Home Asst; each child carries
  `device-group-item`; the panel has seven `data-goto-view` tiles.
- `tests/python/test_environment_sensors.py` — config parsing including the
  null/absent section; endpoint response shape; Fahrenheit to Celsius
  conversion; missing-API-key and device-offline paths.
- Split coverage — a synthetic 4-in-1 appears in both views with the correct
  readings in each; a battery-only device appears in neither.
- Regression — `_match_govee_thermometer()` still resolves correctly when the
  account holds two humidity sensors.

Pre-existing failure to repair:

`test_dashboard_layout.py::test_ambient_view_is_hidden_but_backend_is_preserved`
**already fails on `main` before any change in this design.** It asserts the
Ambient view is absent, but commit `efeda71` re-added it without updating the
test. Rewrite it to assert what is now true — Ambient view present *and*
backend preserved — rather than deleting it, keeping the backend-preserved half
of the coverage.

Fragile test to harden:

`test_dashboard_layout.py::test_status_view_is_last_view_item` splits on the
literal string `<li class="room-item"`, which no longer matches an `<li>` whose
class attribute has more than one class. The seven children gain
`device-group-item`, so they would silently drop out of the parsed view order
and the test would keep passing while checking less. Make the parse tolerant of
multi-class items.

## Out of scope

- Redesigning the sensor card markup.
- Moving Ecobee readings into Environment.
- Any change to the Discovery or System sidebar sections.
- Any change to Home, Cameras, Home Asst, Alarm or Status.
