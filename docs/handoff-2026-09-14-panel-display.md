# Handoff: the Voice Panel's touch screen, 2026-09-14

Written to be picked up cold. The open work is **bringing up the 4" display on
the Voice Panel (Waveshare ESP32-S3-Touch-LCD-4B) under ESPHome**. Everything
else from the 2026-09-13/14 sessions is finished and listed at the end.

## Where it stands

**The screen is completely dark** — no picture and no backlight glow, even after
a USB power cycle. **Voice is unaffected**: wake word, microphone and the voice
resolver all work with the display firmware running.

**The LCD itself is fine.** Before the Voice Panel firmware, the board ran
Waveshare's demo firmware and the screen worked. So the fault is a difference
between `configs/esphome/voice-panel.yaml` and Waveshare's demo, not hardware.

What the firmware reports (Home Assistant, config_hash `0xa8c115df`):

| Signal | Value | Meaning |
| --- | --- | --- |
| `binary_sensor.voice_panel_display_failed` | off | `esp_lcd_new_rgb_panel` + reset + init returned OK |
| `binary_sensor.voice_panel_touch_failed` | off | GT911 answered (dump says address `0x5D`) |
| `sensor.voice_panel_psram_free` | 7,866,692 B | of 8,388,608 → ~510 KB used ≈ the 460 KB RGB frame buffer: the panel *was* created |
| microphone capturing / satellite | on / idle | wake word healthy |

So the MCU side of the RGB panel runs. What is not happening is the ST7701
coming out of sleep (and/or the backlight coming on). The init commands go over
a **bit-banged 3-wire SPI through the TCA9554 expander** — the most likely place
for the difference.

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
