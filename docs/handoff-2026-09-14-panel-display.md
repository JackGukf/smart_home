# Handoff: the Voice Panel's touch screen, 2026-09-14

Written to be picked up cold. The open work is **bringing up the 4" display on
the Voice Panel (Waveshare ESP32-S3-Touch-LCD-4B) under ESPHome**. Everything
else from the 2026-09-13/14 sessions is finished and listed at the end.

## Where it stands

**Updated end of 2026-09-14: the screen works, and the GUI is built through
Cameras.** Owner-tested: Home (six lights and the ecobee, dimmers' brightness on
the full-screen light page), Scenes (HA scripts, also by voice), Security, and a
near-live front door camera from the board's relay (`panel-camera.service`). Voice
works on every page; no flicker. The sections below record how the dark screen
was brought up (flashes 1–10) and each GUI phase after it.

Next, from the design's build order: garage camera (recheck the panel's heap
first), wall-panel remote ("show view" event), sleep/wake. Still open: re-measure
the wake word with the display on; codify `allow_service_calls` in
`setup-ha-voice.py`; a Security card that fires does not move to the front.

The bring-up notes below were written while the screen was still dark.

## What the demo does, verified

Source: `ESP32-S3-Touch-LCD-4B-Demos.zip` → `Arduino-v3.2.0/examples/01_HelloWorld`
and `06_LVGL_Arduino_v9` (a copy was extracted in an old session scratchpad; it is
not in the repo — re-download from Waveshare if needed), plus Arduino_GFX source on
GitHub (`src/databus/Arduino_XCA9554SWSPI.cpp`, `src/display/Arduino_RGB_Display.cpp`).

**RGB panel** — `Arduino_ESP32RGBPanel(...)`:

```
DE 17  VSYNC 3  HSYNC 46  PCLK 9
B0-4: 10 11 12 13 14
G0-5: 21 8 18 45 38 39
R0-4: 40 41 42 2 1
hsync: polarity 1, front 10, pulse 8, back 50
vsync: polarity 1, front 10, pulse 8, back 20
pclk_active_neg 0, prefer_speed = default (not given)
```

None collide with audio (I2S 5/6/7/15/16) or I2C (47/48). ESPHome's built-in
`WAVESHARE-4-480X480` model is **a different board** (its data pins use GPIO5 and
47/48) — do not use it.

**Expander SPI bus** — `Arduino_XCA9554SWSPI(rst=7, cs=0, sck=2, mosi=1, &Wire, 0x20)`.
Its `begin()`:

1. TCA9554 CONFIG = 0xFF (all inputs), OUTPUT = 0x00
2. `rst` (pin 7): output, LOW, 10 ms, HIGH, 100 ms
3. cs (0), sck (2), mosi (1): outputs, all **HIGH** (clock idles high → SPI mode 3)

**Sketch `setup()`**, before the display starts:

```
Wire.begin(47, 48)
expander pin 5, 6 → OUTPUT
pin 6 LOW;  delay 200
pin 5 LOW;  delay 200
pin 5 HIGH; delay 200
gfx->begin()
```

Touch: `GT911.setPins(-1, -1)` — **no reset or interrupt line**; `GT911.begin(Wire, 0x5D, 47, 48)`.
Only the audio demos touch expander pin 3 (audio enable). Nothing in any demo
controls a backlight explicitly.

**`Arduino_RGB_Display::begin()`**, with `rst = GFX_NOT_DEFINED`:

1. `bus->begin()` (the expander SPI steps above)
2. no reset pin → **software reset: command 0x01, delay 120 ms**
3. `batchOperation(st7701_type1_init_operations)` — the full table, which ends
   `0x21` (INVON), `0x3A 0x60`, `0x11` (SLPOUT), delay 120, `0x29` (DISPON)
4. **only then** `rgbpanel->begin()` and the frame buffer

The full `st7701_type1_init_operations` table is transcribed into
`voice-panel.yaml` (`init_sequence`), minus the four commands ESPHome appends
itself.

## What the ESPHome config does now

`configs/esphome/voice-panel.yaml`, section "Display, phase 1":

- `spi: interface: software`, clk = expander 2, mosi = expander 1
- `display: platform mipi_rgb, model CUSTOM`, the pins/porches above,
  `pclk_frequency 12MHz`, `invert_colors: true`, `pixel_mode: 18bit`,
  `cs_pin` expander 0, `reset_pin` expander 5, `enable_pin` [expander 6 inverted,
  expander 7], `init_sequence` = `delay 120ms` + the ST7701 register table
- `touchscreen: gt911` with no reset/interrupt pins
- `lvgl`: one test page ("Voice Panel", a label, a blue **Tap** button),
  `buffer_size: 25%`
- `debug` sensors (heap free, largest block, PSRAM free) and template binary
  sensors "Display failed" / "Touch failed"

How ESPHome's `mipi_rgb` (2026.8.2) actually behaves — read from its source:

- `MipiRgbSpi::setup()`: enable pins HIGH (10 ms) → reset HIGH, **5 ms**, LOW,
  **5 ms**, HIGH → `spi_setup()` → init sequence → create RGB panel
- no DC pin → 9-bit words (`write(value, 9)`, data with bit 8 set) — correct for 3-wire
- `get_sequence()` **appends** PIXFMT, MADCTL, INVON/INVOFF, SLPOUT (+delays), DISPON
  to any custom sequence; it does **not** add a software reset when a reset pin is set
- **`spi_mode` defaults to MODE0** for a custom model; the boot dump shows
  `SPI Data rate: 1MHz`. ESPHome's own Waveshare ST7701 model sets `spi_mode: MODE3`.
- `pca9554` setup: all inputs, outputs latched low (same as the demo)
- `mipi_rgb` exposes no HSYNC/VSYNC/DE idle-polarity options

## Attempts so far

| Flash | Change | Result |
| --- | --- | --- |
| 1 (`0x8ed1ba34`) | first config; reset = expander 7; GT911 reset = 5, interrupt = 6 | black; GT911 setup ran *after* the display and pulsed pin 5, which is the display reset — would have blanked it |
| 2 (`0x9a3a6d4f`) | reset = 5, enable = 6 (inverted); GT911 without pins | black, completely dark |
| 3 (`0xa8c115df`) | + enable expander 7 HIGH, + `delay 120ms` before init; failure sensors | black, completely dark, also after USB power cycle; failure sensors off |
| 4 (`0x8d1fc1ae`) | + `spi_mode: MODE3`, `data_rate: 2MHz`, software reset `0x01` + 120 ms prepended to `init_sequence` | **backlight now on** (faint glow), still no picture — first change the panel reacted to. Note: ESPHome's bit-bang SPI samples on the rising edge in both MODE0 and MODE3, so the software reset is the likelier cause |
| 5 (`0xaf0ec229`) | LVGL commented out, `show_test_card: true`, `update_interval: 5s` — separates panel from LVGL | backlight on, black. **Not LVGL.** |
| 6 | `reset_pin`/`enable_pins` removed; demo-exact sequence in a blocking `on_boot` lambda at priority 700 (pin 7 pulse; CS/SCK/MOSI high; 6 low; 5 low 200 ms → high 200 ms) | **test card visible — the display works under ESPHome** (`0x2ad30547`) |
| 7 | test card → driver `lambda` drawing text; "RED/GREEN/BLUE" each in its own colour to check channel order | text sharp and placed right; **green correct, red and blue swapped** (`0xeffb189e`) |
| 8 | red and blue `data_pins` lists exchanged (`color_order` is ignored for a CUSTOM model, and the appended MADCTL `0x00` would overwrite a BGR bit in the table); LVGL test page restored (`update_interval: never`, no lambda/font) — checks colours, LVGL and GT911 touch | **colours correct, LVGL renders, touch works** (`0x111b2b3e`). The screen **flickered after the OTA reboot**; after a USB power cycle, no flicker. Open: does a warm restart (OTA, HA restart) bring it back? |
| 9 (`0xb440d6e2`) | + `button: restart` (diagnostic), to reproduce a warm restart from HA | after the OTA reboot **flickered again until Tap was pressed**, then stable. A redraw, not a re-init, cures it → the RGB stream loses sync during a busy boot. `mipi_rgb` calls `esp_lcd_rgb_panel_restart` every `loop()`, but `CONFIG_LCD_RGB_RESTART_IN_VSYNC` was off |
| 10 | + `sdkconfig_options`: `LCD_RGB_RESTART_IN_VSYNC`, `LCD_RGB_ISR_IRAM_SAFE`, `SPIRAM_XIP_FROM_PSRAM` (Espressif's RGB drift fixes; XIP costs ~1.7 MB PSRAM) | **no flicker** (`0xb62d785a`) after the OTA reboot and after two `button.voice_panel_restart` presses from HA — fixed. PSRAM free 6.26 MB, heap free 96.8 KB (largest block 56 KB), mic capturing |

After flash 10 the Waveshare-demo test page was replaced by the first GUI phase
(below), flash `0xab924b1d`.

## GUI phase 2: Home and the full-screen light (flashed 2026-09-14)

Built from `docs/design/voice-panel-screens.html` (step 2 of its build order).
Step 1's wake-word re-measure with the display on is **still owed** — it needs a
person speaking; the header's "Okay Nabu" dot shows whether the engine is running.

- **Entities** (resolved against HA's registry, not by name — every wall switch
  has a same-named Dashboard Bridge twin, and only the TP-Link originals carry
  brightness): toggles `light.bedroom_master_bedroom_light`,
  `light.living_room_living_room_switch_2` (both `switch_as_x` over HS200),
  `light.bedroom_north_bedroom_light_switch`, `light.stick_s3` (bridge only);
  dimmers `light.kitchen_light_switch`, `light.family_room_switch` (HS220);
  thermostat `climate.my_ecobee` (HomeKit, heat mode, single `temperature`).
- **HA permission changed:** the Voice Panel's ESPHome entry had
  `allow_service_calls: false`, which silently drops every `homeassistant.action`
  from the device. Set to true through the options flow. *Not yet codified* in
  `scripts/setup-ha-voice.py` — a rebuild would lose it.
- **Files:** `configs/esphome/panel/card-{toggle,dimmer}.yaml` (card templates via
  `!include` vars), `panel/ha-{toggle,dimmer-on,dimmer-level}.yaml` (state feeds),
  `panel/images/*.png` rendered by `scripts/render-panel-icons.py` (the ESPHome
  image has no cairosvg, so the design's SVGs are redrawn in Pillow).
- **Behaviour:** switches send explicit on/off; sliders send one `light.turn_on
  brightness_pct` on release (0 → off); thermostat ±1 °C clamped 10–26, shown at
  once and corrected by HA; lamp/bulb icons open the full-screen page, whose
  power button sends `light.toggle`; the house returns. Menu icon is a no-op
  until Scenes exists. Warm gradient stands in for the room photo.
- **Owner-tested 2026-09-14: everything works.** Fixed after that test:
  - card names overlapped the state line: LVGL's `long_mode: dot` only truncates
    with a **fixed height**; with content height it wraps
  - on the light page the power button covered the level text: the design lifts
    it 58 px above the dock's centre, so it is now centred, with the text at y 266
  - icons: the big lamp's glow was clipped into a rectangle, the small glow muddy
- **Cost:** flash 2.37 MB, PSRAM free 6.26 → 5.60 MB, heap free 102.8 KB
  (largest block 62 KB), microphone capturing, satellite idle.

## GUI phase 3: Scenes, the menu, and dimmers as on/off cards (flashed 2026-09-14)

Committed phase 2 first (`493c676`). Then, flash `0x37252aef`:

- **Dimmers changed by the owner's choice** (of three proposals): most of the time
  only on/off is wanted, so Kitchen and Family room are now ordinary on/off cards.
  Tapping the lamp opens the full-screen page, which for a dimmer adds a tall
  brightness bar (one command on release) and 100/75/50/25 % presets, with the
  lamp shifted left. `card-dimmer.yaml` and `ha-dimmer-on.yaml` are gone; every
  light uses `card-toggle.yaml` + `ha-toggle.yaml` with vars `dimmer` and `level`,
  and `ha-dimmer-level.yaml` keeps `kitchen_pct` / `family_pct`.
- **Scenes are Home Assistant scripts**, installed by
  `scripts/install-panel-scenes.py --apply` through the config API (validated and
  reloaded): `script.panel_all_lights_on`, `script.panel_all_lights_off`,
  `script.movie_mode`. `tests/python/test_install_panel_scenes.py` checks the six
  lights match the panel's cards and Movie mode is the owner's decision. The two
  scenes already in HA ("Turn on all lights" and pair) were not reused — they are
  not in `scenes.yaml` and what they switch is not visible.
- **Scenes page** (`panel/card-scene.yaml`): blue play button runs the script, the
  card is outlined green and a line says what ran. **≡ menu**: the header moved to
  LVGL's `top_layer` (one bar for every page, hidden on the light page), with a
  drawer for Home and Scenes.
- **Trap:** ESPHome pastes a one-line `!lambda return …` for `lvgl.label.update`
  straight into `lv_label_set_text()`, which takes `const char*` — a `std::string`
  expression then fails to compile. Use a two-statement lambda. And quote any
  lambda containing `a ? b : c`, or YAML reads `b : c` as a mapping.
- **Owner-found state bugs, fixed next flash:**
  - *Kitchen and Family room showed off while on.* A `homeassistant`
    binary_sensor's `on_state` does not fire for the state received on connect
    unless `trigger_on_initial_state: true` (ESPHome's default since that option
    replaced `publish_initial_state`). Lights off at boot looked right by luck;
    before, the dimmers' brightness sensor (a `sensor`, which does fire) hid it.
  - *Stick S3 flipped off and back on after a tap.* An HA update crossing the
    command redrew the card. Now a tap draws the whole card at once and starts
    `${key}_settle` (5 s, restart mode); while it runs HA updates do not redraw
    the card, and when it ends the card shows HA's actual state — a failed
    command shows up then, not as a flicker (`panel/light-show.yaml`,
    `panel/light-settle.yaml`).
- **Committed** as `e0a01a7` after the owner confirmed the state fixes.

## Voice scenes (applied 2026-09-14)

- `scripts/setup-ha-voice.py` now keeps `VOICE_SCRIPTS` (the three scene scripts)
  exposed to Assist — a new script is not exposed by default.
- `configs/homeassistant/custom_sentences/en/voice_scenes.yaml` maps "movie mode",
  "start movie mode", "movie night", "let's watch a movie", "all lights on/off" onto
  HA's own `HassTurnOn` with `name` + `domain: script`. "Turn on all the lights" is
  deliberately left to HA's built-in sentence (every light in the house).
- Applied with `setup-ha-voice.py --apply` (exposure + sentences + conversation
  reload, no restart). `tests/python/test_voice_scenes.py` checks the names match the
  installer's aliases, the phrasings, and that exposure is stable.
- Trap: the test helpers' template expander does not handle `(a|b)` nested inside
  `[ ]`; the sentence file avoids nesting so the tests and HA read it the same.
- Not yet: `allow_service_calls`
  still not codified in `setup-ha-voice.py`; wake word not re-measured with the
  display on.

## GUI phase 4: Security (flashed 2026-09-14, `0x2569d1af`)

- Read-only page, third menu entry. Top card: shield, "ALL CLEAR" / "ATTENTION",
  "Alarm <state> • 6 sensors", and a CLEAR / ALERT pill — red when any sensor is on
  or `alarm_control_panel.duo_gong_neng_bao_jing_zhu_ji` is `triggered`
  (`security_refresh` script).
- Six cards from the board's `dashboard_home_alarm.json`: front yard, front door
  camera and garage person detection (NPU), front door and office window
  contacts, fire alarm detector smoke. A card turns red with its state ("Open",
  "SMOKE", "Person • HH:MM" — the panel's own clock at the moment it fired).
- `panel/card-security.yaml` + `panel/ha-security.yaml` (again with
  `trigger_on_initial_state: true`); icons drawn by `render-panel-icons.py`.
- Not done from the design: a sensor needing attention does not *move to the
  front* — reordering LVGL cards was left out; it turns red in place.

Security committed as `b002a05`.

## Dashboard: switch cards lagged after a light changed elsewhere (fixed and deployed 2026-09-14)

Owner saw some lights update on the PC dashboard at once and others seconds later.
Measured 2026-09-14 with the panel's scenes (HA history + dashboard access log +
a websocket recorder):

- HA reported every light within 0.1–1.8 s (Master bedroom's HS200 up to 5 s).
- Matter lights (Stick S3, North Bedroom) are read from HA on every dashboard
  refresh — correct at once. TP-Link switches (Master bedroom, Living room switch
  2, Kitchen, Family room) come from `/api/devices`, a cache polled in the
  background at most every `DEVICE_CACHE_STALE_AFTER` (10 s); the refresh each HA
  report triggered read the pre-change state.
- They corrected only when something else refreshed the page — the Dashboard
  Bridge's Matter copies of those switches, which change on the bridge's 10 s poll
  of `/bridge/state/all`: 3–10 s later.
- The event stream also *dropped* changes inside its 0.4 s window: a scene of ~10
  changes reached browsers as 3–4.
- A real poll of all 8 switches takes 1.6 s (4 at a time), so polling is not slow.

Fix in `web_app.py`: `_coalesced_changes` holds a change inside the window and sends
it when the window ends; a light/switch change is sent at once *and again* after
`_fresh_device_cache` sees a switch poll that began after the change (shared by all
browsers, capped at `EVENT_REFRESH_TIMEOUT` 4 s). Tests:
`tests/python/test_event_stream_freshness.py`; full suite 2230 passed. **Committing
it deploys the dashboard** (post-commit hook).

## GUI phase 5: Cameras, front door first

- go2rtc on the board answers `http://192.168.0.83:1984/api/frame.jpeg?src=front_door_camera&width=432`
  over the LAN without auth: ~25 KB, 1.7–1.9 s (mostly waiting for a frame). Garage
  at 480 wide took 7.3 s once — measure again before adding it.
- `image: platform: online_image` (the top-level `online_image:` key is deprecated
  until 2027.1), JPEG → RGB565 432×243, `http_request` added. Fetched by
  `camera_fetch` every 2 s only while `cameras_page` shows, never while one is
  still downloading (`cam_busy`); `go_page` releases it on leaving.
- **Trap:** once any `image:` entry has a `platform:`, every entry needs one — the
  file images are now `platform: file`.

### Owner test of the 2 s snapshots, and the relay that replaced them

Owner: not live; voice could not turn Living room switch 2 off *while on the camera
page* (fine back on Home); screen flickered. Evidence:

- `online_image::update()` opens the HTTP request and waits for the response
  headers **inside the main loop**; go2rtc sends no headers until the camera's
  next frame, 1.2–2.2 s (five back-to-back tries). At one fetch per 2 s the loop
  was blocked most of the time.
- HA's pipeline debug for the Voice Panel at those minutes: heard
  `" Turn on, turn on, turn on, switch 2."` and `" Turn off."` — audio stalled and
  repeated — then the full command worked once off the page.
- go2rtc's `stream.mjpeg` is 404 in this build.

Fix: **`src/python/panel_camera.py`**, `panel-camera.service` (user unit), installed
with `scripts/install-panel-camera.sh` on the board. While the panel asks, ffmpeg
decodes go2rtc's local RTSP (`rtsp://127.0.0.1:8554/<stream>`, no credentials) to
432×243 JPEG at 4 fps — measured 0.7 s to first frame in isolation, ~17 KB, 23% of
one core — and keeps the latest. `GET :1985/camera/front_door_camera.jpg` answers in
~2 ms with that frame, or 503 immediately while none is fresh (≈2.5 s after the
first request as installed); 20 s without requests stops ffmpeg. Only
`PANEL_CAMERA_STREAMS` are served (default front door); LAN-open like go2rtc.
Tests: `tests/python/test_panel_camera.py`.

Panel (`0x4313aaa5`): fetches from the relay every 300 ms while the Cameras page
shows (skipped while one is in flight), **never while `voice_assistant.is_running`**,
and says "Camera not answering" only after 10 failures in a row.

**Last view first** (flash `0xfec65508`, after the owner saw "Loading..." → "Camera
not answering" → picture on opening the page): the relay keeps the last frame when
ffmpeg stops and saves it to `~/.cache/panel-camera/<stream>.jpg` (~17 KB, atomic,
also every 60 s while watched), served at `/camera/<stream>/last.jpg` (200 in ~2 ms,
404 if none; the request also starts ffmpeg). The panel fetches that first, tagged
LAST VIEW, then switches the same `online_image` (`set_url`, no second buffer) to
live frames, tagged LIVE. The old "10 failures" message fired during the normal
2–3 s warm-up; now it needs 8 s with no picture since opening or the last frame.
Panel memory is unchanged: `runtime_image` and the download buffer allocate with
`RAMAllocator`, i.e. PSRAM first.

**Trap (owner found it on the second visit):** `online_image.release` ends a
download in flight *without* calling `on_download_finished` or `on_error`. Frames
are fetched back to back, so leaving the page almost always cut one off, and
`cam_busy` stayed true: on returning, the relay's log showed no request at all from
the panel, and the page sat on "Loading...". `go_page` now clears `cam_busy` after
the release, and `camera_open` clears it again.

**Owner-tested 2026-09-14:** picture good, voice works with the Cameras page open,
no flicker. Heap free read 80 KB (largest block 40 KB) straight after that flash,
against 94 KB / 53 KB before — recheck before adding the garage camera.

Ruled out between flashes 5 and 6, from source rather than by flashing:

- **The init table is correct.** Parsed Arduino_GFX's `st7701_type1_init_operations`
  and compared op by op with `init_sequence`: all 33 register commands identical.
  ESPHome appends `0x3A 0x66` (the demo sends `0x60`), `0x36 0x00`, `0x21`, `0x11`, `0x29`.
- **The bit protocol matches.** The demo writes MOSI, SCK low, SCK high, idle high —
  ESPHome's MODE3. CS per 9-bit word (ESPHome) vs per batch (demo) is what ESPHome's
  working Waveshare ST7701 model already does.
- **But MODE3 lost the first command.** Expander outputs start low; ESPHome's first
  transfer drops CS, then raises SCK to idle — a spurious rising edge that shifts
  the first word. That word was the software reset. Flash 6 pre-drives SCK high.
- Pixel clock: the demo uses 12 MHz on octal PSRAM, same as here. Data pin order is
  byte-swapped by ESPHome on purpose (big-endian buffer); wrong order would give
  wrong colours, not black. An IPS panel is black when not driven, so black alone
  does not prove the ST7701 is asleep.

## Differences still left, most likely first

1. **SPI mode.** The demo idles the clock HIGH (mode 3); ESPHome's custom model
   uses MODE0. If the ST7701 never parses SLPOUT/DISPON it stays asleep. Set
   `spi_mode: MODE3` on the display. *Cheapest test — do this first.*
2. **No software reset.** The demo sends `0x01` + 120 ms before the table; ESPHome
   does not when `reset_pin` is set. Prepend `- [0x01]` and `- delay 120ms`.
3. **Reset timing.** Demo: 200 ms LOW, 200 ms after HIGH. ESPHome: 5 ms / 5 ms.
   The added `delay 120ms` covers the "after", not a longer LOW pulse. If 1 and 2
   fail, drop `reset_pin` and do the demo's exact pin-6/pin-5 sequence with delays
   in an early `on_boot` (check `mipi_rgb`'s setup priority so it runs first), or a
   `pca9554` `output` + `delay` before the display.
4. **Pin 7 is pulsed** LOW→HIGH in the demo, only raised here.
5. **CS/SCK/MOSI idle HIGH before the first transfer** in the demo.
6. **Order:** the demo sends the init table *before* creating the RGB panel —
   ESPHome does the same, so probably not it.
7. **The backlight.** No demo controls it, yet it lit with the demo, so it follows
   something the demo does (panel power/DISPON, or one of the expander lines).
   If 1–3 give a picture, this answers itself.

## Next tests, in order

1. `spi_mode: MODE3` (and `data_rate: 2MHz` like ESPHome's Waveshare model); flash; look.
2. Prepend software reset `0x01` + `delay 120ms` to `init_sequence`; flash; look.
3. `show_test_card: true` with LVGL removed, to separate panel from LVGL.
4. Demo-exact reset/enable timing via `on_boot` (item 3 above).
5. **See boot errors directly**: USB serial from Windows (WSL needs `usbipd-win`),
   because the API log client connects after setup and never sees boot `[E]` lines.
6. Last resort, and it replaces the voice firmware: flash `01_HelloWorld` again to
   re-confirm the hardware, then re-flash ESPHome from Windows (`web.esphome.io`).

Every check needs a person looking at the screen; ask for it after each flash.

## Traps met this session

- **`timeout N docker run ... logs` leaves the container running** (the timeout
  kills only the client). Two captures ran for hours holding the build cache. Use
  `docker run -d --name X ... logs`, `timeout N docker logs -f X`, `docker rm -f X`.
- **The build cache mount**: compile/upload need `-v configs/esphome/.esphome:/cache`
  as well as `/config`, or the IDF Python env mismatches.
- **PSRAM arithmetic**: 8 MB = 8,388,608 B. Reading 7.87 MB free as "almost nothing
  used" was wrong; ~510 KB is used, the frame buffer.
- **Boot errors are invisible to `esphome logs`** — use the failed-flag sensors or
  USB serial.

## The design that follows bring-up

Approved design, interactive preview: `docs/design/voice-panel-screens.html`
(also published as an artifact). Style follows Waveshare's own demo screenshots:
frosted cards over a pre-blurred warm room photo, "≡ room" menu, full-screen page
per light with a round blue power button. **Decisions made by the owner:**

- Movie mode: Living room switch 2 off, Living room cabinet LED off, Living room
  ambient light on (Home Assistant script, so voice and dashboard share it)
- Light cards: the six on the dashboard's Lights card (Master bedroom light,
  Living room switch 2, North Bedroom Light Switch, Stick S3 as toggles; Kitchen
  light switch and Family room switch as dimmer sliders — both HS220) + the ecobee
  thermostat card. No plugs.
- Wall-panel views: Home, Cameras, Security, Devices, Climate, Status (needs a new
  "show view" event on the dashboard's `/api/events/stream`, wall panel only)
- Cameras: `front_door_camera` and `garage_camera` via go2rtc `frame.jpeg`,
  480 wide, every 2 s only while the page is open (measured 121 KB/1.66 s and
  45 KB/0.52 s full size)
- Security: the six sensors in `dashboard_home_alarm.json`

Build order once the screen shows the test page: re-measure the wake word with
the display on → Home (lights + thermostat + full-screen light) → scenes →
security → wall-panel remote → cameras → sleep/wake. LVGL 9.5 in ESPHome has every
widget and style needed; **do not use live `blur_backdrop`** (no GPU, shares PSRAM
with the wake word) — pre-blur the background image.

## Everything else from 2026-09-13/14 — finished

| | Where it is recorded |
| --- | --- |
| Wake word stopped after first playback → restart script | `docs/handoff-2026-09-13-voice-satellite.md`, `voice-panel.yaml` |
| Voice Panel pipeline with no LLM; wake-word echo ignored | same handoff, `scripts/setup-ha-voice.py` |
| Custom sentences: time/date/weekday, room status (temperature, humidity, doors, water, thermostat) | `configs/homeassistant/custom_sentences/en/` |
| Bridged Matter duplicates hidden; wall switches as lights; LLANO kept via Apple TV; Raspberry PI plug never on voice; repeaters hidden | `setup-ha-voice.py` + tests |
| Voice resolver (fuzzy match, "Did you mean…?") and Whisper name prompt | `configs/homeassistant/custom_components/voice_resolver`, `docker-compose.voice.yml` |
| Piper on 4 cores (2.02 s → 0.84 s) | `docker-compose.voice.yml` |
| HA network adapter was still `docker0` after the Ethernet move → set to `enp97s0`; Govee LAN light joined | `CLAUDE.md` |
| New-device banners sync across screens, capped at 40 vh | `app.js`, `tests/python/test_notification_sync.py` |
| go2rtc.yaml written 0600 | `scripts/generate-go2rtc-config.py` |
| **Still open, needs the owner:** rotate the shared camera password on all six cameras, then regenerate go2rtc and redact four local session logs | memory `camera-password-rotation-pending` |
| **Still open:** push to GitHub — many commits are local only | — |
