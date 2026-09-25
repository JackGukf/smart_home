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
  - `family_room_lights_on_motion`: occupancy on, **at any time of day** (the
    sun condition was dropped 2026-09-19 at the owner's request) →
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
1. **PowerLync:** live since 2026-09-24 09:20 - see "Update 2026-09-24" below.
   Still to come by themselves: the daily bars (from 2026-09-25) and the usual
   day (after three whole days). Gas: see `docs/energy-monitoring.md`.
2. **Test-run Movie mode** once (never run since the IR pauses and the plug).
3. **First night of the automations** - check the logbook in the morning.
4. **Daytime:** motion turns the accent lights on at any hour and nothing turns
   them off until the Night lights time - the owner's choice (2026-09-19).
5. **Tuya IoT Core** (iot.tuya.com → Cloud → IoT Core): renewing it would let the
   three Wi-Fi IR hubs import their Smart Life codes.
6. **Voice Panel All lights** follow Manage only after a Manage change; a device
   joining the Lights group some other way reaches them at the next change.
7. **Cast to TV** cannot tell the TV is on another input: if the dongle stays
   powered it keeps pulling the stream (~1.4 cores for nobody).
8. Still open from before: rotate the shared camera password; DHCP reservations
   for .83, .58 and .176.

## Update 2026-09-24: the meter reports, and its first reading was a spike

The PowerLync (paired 2026-09-23, every value 0) started reporting at
**09:20 on 2026-09-24**. Its kWh register went from 0 straight to
**104491.9 kWh** - the meter's lifetime total - and Home Assistant, which
treats the register as `total_increasing`, booked all of it as consumption in
the 09:00 hour. The Home card showed **104492.4 kWh today**.

- **Fixed in Home Assistant's statistics** (the board, not git): the
  equivalent of Developer Tools → Statistics → *Adjust sum*, WebSocket
  `recorder/adjust_sum_statistics` on
  `sensor.powerlync_energy_monitor_002_004cce_grid_total_energy_consumed`,
  `start_time` 2026-09-24 09:00 local, **adjustment −104491.9 kWh**. The 09:00
  hour now reads 0.5 kWh (09:20 to 10:00, real). HA's own Energy dashboard is
  corrected by the same change. Undo would be the same call with +104491.9.
- **Guarded in code** (`metered_kwh` in `src/python/energy.py`, commit
  `dd48c61`), for the Energy view and the nightly forecast alike:
  - a period whose register reads **0** is a gap, not a 0 kWh hour - so the
    hours before 09:20 do not drag the usual day or the base load to zero;
  - a change above **48 kWh per hour** (200 A at 240 V; 24x that per day) is
    a register jump, not electricity, and is dropped.
  The statistics are now fetched with `types: change, state` so the first rule
  can see the register.
- **Why it can happen again:** if BC Hydro re-joins the PowerLync, or it
  reports 0 for a moment, HA reads a drop as a meter reset and books the next
  real reading as consumption again. The page is protected; HA's Energy
  dashboard is not - repeat the adjustment, using the jump size from the
  register's history (`/api/history/period`, the first non-zero reading).

### Home Energy card, bigger flow (same day)

On the PC the power flow got 99 px of a 222 px card. The three figures under it
(Today, On pace, This bill) now put label and value on one line when they fit
(52 → 26 px; a narrow card wraps them back to two), and the compact flow's
viewBox is cropped to `0 14 350 114` (only glow was outside it); its height cap
is 260 px. At 1920 × 1080 the flow is now 384 × 125 px, at 2560 × 1440
660 × 215. Values stay next to their labels, not right-aligned, because the
card's resize handle sits in the bottom-right corner. `check-card-overlap.py
--view home --view energy`: no findings on all 7 sizes. The iPad 13" portrait
card is short and its flow is still small there - untouched.

## Update 2026-09-24 (evening): house modes, the armed house, remote access

All of it on the board and in git; details in `docs/house-modes.md`.

- **Remote access:** Tailscale on the board (`orangepi6`, `100.110.87.106`,
  `docs/tailscale.md`), `--accept-dns=false` so `/etc/resolv.conf` - which
  Docker copies into containers - is left alone.
- **House modes** (`scripts/install-house-modes.py`, `input_select.house_mode`):
  Away when every phone is out *and* the house is still (all lights off, living
  room sunset-23:30), Home again (ambient lights in the dark), Vacation after
  24 h or by hand (alarm armed away, ecobee vacation), night arm from 01:30 and
  disarm at 07:00. The actions follow the change of mode, so the Security
  view's **House mode** card picks any mode by hand and does what presence would.
  The living room late-off rule now skips Away/Vacation.
- **Armed house** (`scripts/install-security-response.py`): the Zigbee alarm
  speaker for an unexpected person downstairs, a red banner with Stop on the
  dashboard, bedroom button once = stop / twice = Night arm (its old light
  automations deleted), and a **While armed · outdoors** log on Security.
- **Garage camera counts the driveway only:** `NPU_ZONES` in the board's
  `.env` (backup `.env.bak-2026-09-24-zones`); a person counts where their feet
  are.

Open, in order:

1. **The iPhone:** HA app location *Always* (it is *When in use*), and Tailscale
   kept connected with the app's external URL
   `http://orangepi6.tail9804d9.ts.net:8123`. Until then Away and arrival
   never fire by themselves; the dashboard buttons work.
2. **Two night schedules.** The alarm arms itself *away* at 01:30 and disarms
   at 07:00 (not Home Assistant - most likely the Smart Life app). Keep it or
   ours, not both; ours arms *home*.
3. **First real night:** the speaker has only been checked by rendering the
   banner, never sounded by the rule. Check the logbook for
   `security_intruder_siren` in the morning, and arm/disarm once by hand
   through the Tuya cloud.
4. The "unexpected" rule's trade-off: an intruder within 30 minutes of the
   household's last movement downstairs is not flagged. Pets would set it off
   on Away - there are none known.
5. Other residents' phones, for Away to mean empty rather than "Jack is out".

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
