# Handoff 2026-09-19: cast to the TV, family room lighting, All lights, Energy

One long session (2026-09-18 evening to 09-19), driven by the owner on the wall
panel and the Voice Panel. Dashboard **v0.7.0, build 286**; everything is pushed
(`main` at `cc49a16`). The Voice Panel runs new firmware (flashed 2026-09-19).
The board's timezone is now **America/Vancouver** (it was UTC; the owner ran
`timedatectl`). Logs and journal timestamps are local from here on.

Start with **Open items**, then **Traps**.

## What exists now

### Cast to TV (`docs/dashboard-cast.md`)
- The dashboard as live video on the TV's **LLANO-S450** EZCast dongle (HDMI):
  headless Chromium → screenshots at 4 fps → ffmpeg H.264 → DLNA. The dongle
  refuses every Cast receiver that shows a web page, so video is the only way.
- `dashboard-cast.service` (user unit), **off by default**; off, nothing runs.
  Settings → **Cast to TV** switches it (`systemctl --user enable|disable --now`).
- Capture and encoding are decoupled: a stuck Chromium is replaced mid-stream;
  Chromium is also refreshed past 900 MiB and hourly. Liveness is "the dongle
  still pulls the stream", not its SOAP answers.
- Chromium gets `TZ=America/Vancouver` and opens `/?screen=tv`; the Home camera
  card defaults to the **front door camera** on any screen that never picked one.
- Home Assistant: **`switch.tv_cast`** ("TV cast", MQTT discovery by the
  dashboard) with a `text` attribute ("Casting to LLANO-S450 …").
- **Voice Panel → TV cast** (launcher page 2): the switch and a remote like
  Wall panel's - six views, scroll, ◀ Home camera ▶. Events
  `esphome.tv_cast_show_view|scroll|camera` reach only the cast's browser (a
  loopback stream asking for `?screen=tv`); it reports its camera to
  `sensor.tv_cast_camera`. Cost: ~1.4 cores, ~600-700 MiB while casting.

### Family room lighting
| Device | Entity | Notes |
| --- | --- | --- |
| IKEA TRÅDFRI driver 30 W (upper) | `light.0x286847fffe5eb711` | Zigbee; dashboard device "Cabinet LED upper", dimmable |
| IKEA TRÅDFRI driver 10 W (lower) | `light.0x64028ffffe64de32` | Zigbee; "Cabinet LED lower" |
| TP-Link HS103 plug, 192.168.0.142 | `switch.family_room_cabinet_led` | the cabinet LED strip; in `tplink_switches.json` and HA (TP-Link integration, Family room) |
| Family room LED | `light.family_room_led` | now a dashboard device too (Family Room, Lights group) |

- Both IKEA drivers: **z2m `debounce: 0.5`** and **`on_off_transition_time: 0`**
  (see Traps). Set on the board, not in the repo.
- **Movie mode** (`scripts/install-panel-scenes.py`, now the source of truth):
  projector, 1 s, Fire TV, 1 s, Z906, 2 s; family room and kitchen switches off
  if on; Family room LED, both IKEA drivers and the cabinet plug off. The IR
  "Smart IR Cabinet" step is gone (never learned; the plug replaced it).
- **Automations** (`scripts/install-family-room-late-off.py`, installs both):
  - `family_room_lights_off_late`: from the start time to 06:00, when
    `binary_sensor.0xa4c138d00106c90d_presence` has seen nobody for 10 min, the
    four accent lights go off. Three triggers (occupancy off 10 min, the start
    time, any of the four on 10 min).
  - `family_room_lights_on_motion`: sun below the horizon, occupancy on →
    each of the four turned on **only if it is off**; not within 3 h of Movie
    mode (its `last_triggered`).
  - The start time is **`input_datetime.family_room_lights_off_after`** (23:30),
    set from Settings → **Night lights**.
- **Owner's rule:** anything that turns lights on sends "on" only to lights that
  are off, one check per light. "On" to a light already on made the IKEA
  drivers flash. Applied to the motion automation, `panel_all_lights_on` and the
  dashboard's All lights on.

### All lights on / off
- **Dashboard:** the Lights group, plus/minus a saved list
  (`dashboard_light_scenes.json`: include the two cabinet plugs, exclude
  **Stick S3** `matter:1`, a virtual light). **Manage** on the All lights ⓘ
  sheets edits it. One card per device.
- **Voice Panel and "Okay Nabu"** run `script.panel_all_lights_on/_off`; after a
  Manage change the dashboard maps its devices to HA entities
  (`src/python/panel_scenes.py`: `ha:` direct, Matter by name in the Matter
  integration, TP-Link by MAC among TP-Link + Switch-as-light entities) and
  rewrites both scripts (`POST /api/light-scenes/sync`). Now 10 devices.
- Fixed: scenes sent Home Assistant lights to the TP-Link endpoint (404 for every
  `ha:` light); they also switched the two demo cards in Settings → Theme.
- A tapped card holds its state 3 s after a read agrees (`PENDING_SETTLE_MS`),
  so a late stale report cannot flip it back.

### IR remotes page (Devices → IR remotes)
- The Zigbee **IR remote family room** (HOBEIAN ZG-IR01, `0xa4c1380c14c64266`)
  shows its five learned channels - Projector, Fire TV Stick, Z906 Speaker and
  both volumes - each with **On / Off** (a channel holds one code for each;
  "registered" in z2m's `select.*_switchN_on/_off`). Channel 6 is unused.
- ← Devices, **Manage** (which remotes show) and **Edit** (name, icon, colour),
  saved in `dashboard_ir_page.json` - not a device group.
- The three Wi-Fi Tuya hubs still show nothing: their Smart Life codes are in
  Tuya's cloud and the IoT Core subscription is still expired (re-checked).

### Home, Energy, Discovery (dashboard)
- **Home** is the owner's layout (`DEFAULT_HOME_LAYOUT`, version
  `2026-09-19-energy-2`): Weather | Climate | Quick actions across a five-row
  top; Areas then Security on the right; Camera in the middle; Energy then
  Temperatures on the left. Columns total 20 rows each.
- **Energy card** (under Weather): live kW with the last hour, a state pill, the
  last 24 h in kWh and $, gas yesterday. **Energy view** (sidebar, between
  Cameras and Devices): electricity and gas side by side over 30 whole days,
  and electricity for the last 24 hours against a usual day.
- **`/api/energy` is sample data** (`src/python/energy.py`): generated from the
  clock, same on every screen, `"sample": true`; the card and view say so. Rates
  are illustrative (BC Hydro Step 1 $0.1143/kWh, FortisBC $15.20/GJ).
- **Discovery** is one sidebar entry (last in Views) opening three app tiles:
  Add Matter, Add Zigbee, Bluetooth; each page has "‹ Discovery".

### Voice Panel firmware
- TV cast app (launcher page 2, icon `app_cast`); Movie mode card "Projector,
  Fire TV, Z906 on; family room lights off"; All lights cards "Every light and
  LED strip". `card-view.yaml` / `wall-button.yaml` now take `remote` (wall|tv).

### Only on the board (not in git)
- `configs/devices.local.yaml`: dashboard devices for both IKEA drivers and
  Family room LED (backups `*.bak-2026-09-18-ikea`, `*.bak-2026-09-19-scenes`).
- `dashboard_light_scenes.json` (include/exclude + the entities last synced),
  `dashboard_areas.json` (`dev:192.168.0.142` → family-room).
- z2m device options (debounce) and the drivers' own transition setting.
- HA: `switch.tv_cast`, `input_datetime.family_room_lights_off_after`, the two
  automations and three scripts (all reinstallable from `scripts/`).

## Open items
1. **PowerLync:** done in code since the same day - pair it with
   `scripts/setup-ha-powerlync.py --code … --apply` and the dashboard goes live
   by itself. Gas: see `docs/energy-monitoring.md`.
2. **Test-run Movie mode** once (never run since the IR pauses and the plug).
3. **First night of the automations** - check the logbook in the morning.
4. **6 AM to sunrise:** motion turns the accent lights on and nothing turns them
   off. Extend the off rule to sunrise if that matters.
5. **Tuya IoT Core** (iot.tuya.com → Cloud → IoT Core): renewing it would let the
   three Wi-Fi IR hubs import their Smart Life codes.
6. **Voice Panel All lights** follow Manage only after a Manage change; a device
   joining the Lights group some other way reaches them at the next change.
7. **Cast to TV** cannot tell the TV is on another input: if the dongle stays
   powered it keeps pulling the stream (~1.4 cores for nobody).
8. Still open from before: rotate the shared camera password; DHCP reservations
   for .83, .58 and .176.

## Traps found this session
- **Chromium hangs silently in a systemd user unit here** - the user manager
  carries the desktop session and Chromium waits on the GNOME keyring. Pass
  `--password-store=basic` and drop `DISPLAY`, `WAYLAND_DISPLAY`,
  `DBUS_SESSION_BUS_ADDRESS`. Works from ssh, which misleads.
- **The EZCast's Cast TLS is too old** for current Python (why HA's Cast
  integration never reached it); `set_ciphers("DEFAULT:@SECLEVEL=0")` connects.
- **IKEA drivers report their previous state right after a command** (ON, OFF,
  OFF, ON for one "on"): z2m `debounce` fixes it at the source.
- **HA 2026.6 MQTT discovery sets entity ids with `default_entity_id`**, not
  `object_id`.
- **Switch-as-light:** two TP-Link wall switches are HA *switches*; the `light.`
  entities scripts use are "Switch as light" wrappers on the same device.
- **`install-panel-scenes.py` had an older Movie mode than the live one** until
  this session - check a script against HA before `--apply`.
- **The dashboard's "confirm HA device" endpoint rewrites `devices.local.yaml`
  with `yaml.dump`** - comments are lost. Back it up first.
- **`/api/devices` is a cache:** the read straight after a command still reports
  the old state; the page's pending-command hold covers it.
- **Never wrap `docker run … esphome logs` in `timeout`** - the container keeps
  running and holds one of the panel's five API connections.
- **`pkill -f` / `pgrep -f` over ssh match the ssh command line itself**, and
  **HA's own camera snapshots are ffmpeg `image2pipe` processes** - never clean
  up by matching those patterns.
