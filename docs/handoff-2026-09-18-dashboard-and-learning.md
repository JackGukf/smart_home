# Handoff 2026-09-18: the dashboard redesign, house learning, CO2, IR and the remote

Two days (2026-09-16 to 09-18) of work on the dashboard, driven by the owner
reviewing each change on the wall panel, a PC, an iPhone 15 and a 13-inch iPad
Air. Dashboard **v0.7.0, build 261**; everything is pushed (`main` at
`5a5c39c`). The Voice Panel runs new firmware (flashed 2026-09-18 13:21 PDT).

Start with **Open items**, then **Traps** - several cost an hour each.

> **Continued in `docs/handoff-2026-09-19-cast-lighting-energy.md`** - cast to
> the TV, the family room lights, All lights, the IR remotes page, Energy and a
> new Home layout. Open item 1 below (learn the cabinet light's IR button) is
> obsolete: a TP-Link plug replaced it.

## Text overlap: how to know, rather than to hope (2026-09-20)

`scripts/check-card-overlap.py` drives the board's own Chromium over the
DevTools protocol, loads the dashboard at every size this house reads it on -
iPhone 15, iPad 13, the 1920x1080 wall panel, a laptop, a desktop - and asks
the page which pieces of text overlap, which are clipped, and which spill out
of their card. Run it on the board:

    .venv/bin/python scripts/check-card-overlap.py                       # all views, all sizes
    .venv/bin/python scripts/check-card-overlap.py --view home --device iphone15
    .venv/bin/python scripts/check-card-overlap.py --kind clipped --kind spill

It exits 1 when it finds something, so it can gate a deploy. Three things it
learned the hard way:

- **It signs itself in** with the session cookie the TV cast uses, and stops
  with "not signed in" if it lands on the login page. Its first run reported a
  clean sweep while looking at the login form - silence has to mean "checked",
  never "saw nothing".
- **A clipped box is not an overlap.** A caption with `overflow: hidden` has a
  box that runs past the edge hiding it; rects are cut down by every clipping
  ancestor before they are compared.
- **Layered text is left alone** - a badge on a tile, a label inside the
  thermostat dial - because it is meant to sit over something.

What it caught first time out: the **Temperatures card**. Its hero row was a
grid of four tracks (indoor, humidity, CO2, outdoor), and grid tracks answer
"too narrow" by running past each other - CO2 printed over Outdoor by 19px on
the iPhone, and on the **laptop** too, because that card sits in a narrow
column whatever the window is doing. A media query would have fixed the phone
and missed the laptop. The row is now a wrapping flex row, which needs no
query at all - and no container query, which matters because the owner's iPad
ignores those. The week's forecast temperatures stack on narrow screens for
the same reason.


## What exists now

### Home view
- **Header:** hour:minute clock and a rotating news line (Settings → News:
  breaking and finance sources, market tickers). `src/python/news_feed.py`.
- **Weather card:** clock, date, today and a seven-day strip; sky follows the sun.
- **Camera card:** 16:9 picture, a strip of the *outdoor* cameras below it in
  route order with the back yard last, and "last person" seen.
- **Climate** (ecobee dial) at half width beside **Quick actions**: All lights
  on/off, Movie mode (HA `script.movie_mode`), Good night.
  - Each action now shows running → done / partly / failed, and a panel lists
    every device it touched and where it ended up. An ⓘ on each shows the same
    list before a run. Scripts are run *by name*, which waits for the end, then
    read back step by step (`src/python/script_steps.py`).
- **Temperatures:** indoor average, CO₂ (ppm and level), outdoor, and four 24 h
  sparklines (`src/python/sensor_history.py`), plus "worth a look" outliers.
- **Security card:** alarm state, arm buttons, sensors grouped by kind
  (Doors & windows, Safety, Cameras, Motion).
- **Areas** grid.
- On an iPad (two columns, 740-1100 px; and 1101-1400 × ≥821 px, the 13-inch in
  landscape) Weather, Temperatures and Security use narrow-card rules - plain
  media queries on purpose, see Traps.

### Security view
- A **rendered picture of the house** (`web_static/security-house.jpg`, 1312 ×
  1199, 324 KB) with a live pin per room, placed over the icons the picture
  paints. Covers hide what the picture paints that is not true: "Bedroom 1-3"
  become Master / North / South Bedroom; the legend becomes the alarm state and
  a line per floor; the logo becomes the latest reading. Pin positions are
  `HOUSE_ROOMS` in `app.js` - **a new picture means re-measuring them**.
- The picture takes the screen height (`--house-fit`); beside it the room card
  (sensors, then Arm beep / Siren / Test siren / **SOS**, which now asks first)
  and **Recent activity** (house memory, bursts folded, tap selects the room).

### Status view
Stat strip; **Today at a glance** (doors, people, motion since midnight, hourly
columns); a board of small charts (activity by hour, busiest sensors, camera
sightings, board memory and temperature, batteries); **House learning** tile;
services; morning digest. `src/python/status_overview.py`.

### Other views
- **Environment:** the Govee **H5140 CO₂ monitor** leads with CO₂, its level and
  a 24 h line. Polled once a minute from the Govee cloud and mirrored to HA as
  `sensor.co2_monitor_co2` (states API: it vanishes on an HA restart until the
  next poll).
- **Ambient lights:** the H6054 and H6076 are read and, when LAN/BLE fails,
  controlled through the Govee cloud. The H613A (BLE only, not on the account)
  shows "as last set".
- **Devices → IR remotes:** the three Tuya IR hubs, driven **locally**. Learn a
  button from its original remote, test, save; send it. Each learned button is
  an HA `button.<hub>_<button>` through MQTT discovery (`src/python/tuya_ir.py`,
  codes in `configs/ir_buttons.json`, git-ignored).
- **Settings** is app tiles (Theme, Startup, News, About - version and build -,
  Home view). Media has YouTube (full screen), Music, Bluetooth.

### House memory and learning (the "smart" plan)
- **Phase 0 - `house-memory.service`** (user unit): every HA state change kept in
  `~/house-memory/events.db` (SQLite, ~2 MB/day), backfilled from the recorder
  after any restart. Labels from the Status tile (Normal / False alarm /
  Unusual) are the training signal. `src/python/house_memory*.py`.
- **Phase 1 prep - `house-learning.timer`**, 03:30 **America/Vancouver**:
  retrains a small routine model (per sensor and the house: chance of activity
  by weekday and hour), keeps it only if it beats the current one on unseen
  days, writes `model_runs`, and records unusual moments **silently** in
  `shadow_alerts`. `src/python/house_learning.py`. At 10 days: 92% of hours
  right vs 83% for a guess. "Ready" needs every weekday seen 4× (~early
  October). Nothing alerts yet - by design.
- The **morning digest** timer now runs at 04:00 Vancouver time (it ran at
  04:00 UTC = 21:00 local) and carries a learning line.

### Home Assistant
- **Movie mode** (`script.movie_mode`) was replaced: Projector, Fire TV, Z906
  on through the family room IR remote; wait 2 s; Family room and Kitchen
  switches off if on (the TP-Link entities, not the Matter bridge's `_2`
  copies); Family room LED off; **cabinet light off** =
  `button.smart_ir_cabinet_cabinet_light_off`. The old script is saved on the
  board as `~/movie_mode.previous-2026-09-18.json`.
- Entities the dashboard sets: `sensor.co2_monitor_co2`, `sensor.wall_panel_camera`.

### Voice Panel - Wall panel page
Six view buttons (shorter now), **Scroll up / Scroll down**, and **◀ Home camera
▶** with the camera's name. Events `esphome.wall_panel_scroll` {direction} and
`esphome.wall_panel_camera` {step} are checked against fixed lists and forwarded
only on the wall panel's own event stream; the wall panel reports its camera to
`POST /api/wall-panel/camera`. Files: `configs/esphome/voice-panel.yaml`,
`panel/card-view.yaml`, `panel/wall-button.yaml`.

Flash (from the repo root; `compile` first - `run` exits 0 on a broken config):

```bash
docker run --rm --name esph-compile -v "$PWD/configs/esphome:/config" -v "$PWD/configs/esphome/.esphome:/cache" ghcr.io/esphome/esphome compile voice-panel.yaml
```

```bash
docker run --rm --name esph-upload -v "$PWD/configs/esphome:/config" -v "$PWD/configs/esphome/.esphome:/cache" ghcr.io/esphome/esphome upload voice-panel.yaml --device 192.168.0.58
```

## Open items (need the owner, or time)

1. ~~**Learn the cabinet light's button:**~~ **Obsolete (2026-09-18, later):** the
   cabinet's LED is now on a TP-Link HS103 plug (`switch.family_room_cabinet_led`,
   192.168.0.142), and Movie mode switches that plus the two IKEA TRADFRI cabinet
   drivers off; the IR step is gone (`scripts/install-panel-scenes.py`). Kept below
   for the Tuya note.
   Was: **Learn the cabinet light's button:** Devices → IR remotes → Smart IR Cabinet →
   Learn a button, press the remote's off button at the hub, name it exactly
   **"Cabinet light off"**. Movie mode's last step presses it; until then that
   step is skipped (the Quick action list says "not in Home Assistant").
   *Or* renew the **Tuya IoT Core** trial (iot.tuya.com → Cloud → IoT Core) to
   read the Smart Life app's learned codes - every Tuya cloud call fails with
   "IoT Core service subscription has expired".
2. **H6076 "LAN Control"** is off (likely a firmware update); turning it back on in
   the Govee app restores fast local control. The cloud fallback covers it.
3. **Backdoor vibration sensor** reads unknown for 35+ h; **"WATER SENSOR"
   moisture** is unavailable. Batteries: water sensor 26%, fire alarm 40%.
4. **Label events** on the Status tile - the Phase 1 models learn from them.
   Phase 1 proper (alerts that speak) waits for ~4 weeks of data and a measured
   precision on the shadow alerts.
5. **GitHub secret scanning** flagged `tests/python/test_tuya_ir.py:212`
   (`"env-pw"`), a test placeholder - checked against the real secrets, no match.
   Close the alert as "Used in tests".
6. Still open from before: rotate the shared camera password; DHCP reservations
   for the board (.83), the panel (.58) and the wall panel (.176).

## Traps found this session

- **Deleting CSS rules by pattern can take a closing brace** and silently drop
  every rule after it: the dashboard rendered unstyled (build 236).
  `tests/python/test_stylesheet_integrity.py` now checks the braces.
- **A deploy announced its build before the service was back**; open browsers
  reloaded into the restart and stayed dead. `deploy-dashboard.sh` now waits for
  `/static/app.js` before shipping `build_info.json`.
- **Container queries do nothing on Safari before iPadOS 16**, and `cqh` units are
  dropped there. The first iPad fix was built on them and changed nothing on the
  owner's iPad. The iPad rules are media queries now; `cqh` sizes have a plain
  fallback first. Tests guard both.
- **The owner's iPad Air is the 13-inch**: 1366 × 1024 in landscape, i.e. the
  *three*-column Home, not the two-column iPad band.
- **The hallway wall panel is 1920 × 1080**, not 1280 × 800.
- **The global `aside {}` rule is the sidebar's** (sticky, window height) and
  applies to any `<aside>`: a card made an `<aside>` grew to the window.
- **Declaring state late in `app.js`** that startup code reads throws a
  temporal-dead-zone error and stops the page; declare it near the top (see
  `isWallPanel`).
- **An HA script called as `script.turn_on` returns at once**; called by its own
  name (`script.<name>`) it runs to the end - that is how a Quick action knows
  what happened.
- **House learning:** count *rises* (off → on), not "on" - a camera holding
  "person" on a static shape made the house busy at 3 am. Judge alerts with a
  model that did not train on those hours. Refuse to run without the house's
  time zone (a UTC run shifted the routine by 7 hours and looked plausible).
- **The Voice Panel's view-card icons are private-use glyphs** - invisible in a
  terminal; match lines by structure, not by copying the text.

## Tools

- `scripts/dashboard-screenshot.mjs` - headless screenshots of the dashboard at
  any screen size, run on the wall panel (trusted host, no login). Every layout
  in this session was checked with it; `grim` on the panel captures the real
  screen (`XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-0 grim x.png`).
- Tests: 2,495 passing (`python3 -m pytest`).
