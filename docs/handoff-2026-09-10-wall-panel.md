# Handoff: the wall panel, 2026-09-10 → 12

Written to be picked up cold. The Raspberry Pi 4 stopped being a spare build
target and became a wall display; everything else here follows from making that
display useful and then making it fast enough.

The how-to lives in **`docs/kiosk-display.md`** — this file is the narrative, the
measurements, and what is still open.

## State at the end

| | |
| --- | --- |
| Panel | `smarthome@192.168.0.176`, Debian 13, labwc/Wayland, HDMI-A-1 |
| Kiosk | autostarts from `~/.config/autostart/smart-home-kiosk.desktop` |
| Dashboard build | **#207**, and the panel pulls new builds in by itself |
| NPU detector | **five cameras** (was three), held-open RTSP consumers |
| Camera route | `Front approach`: garage → frontyard → front door, live |
| Board load | 2.6–3.2 of 12 cores, 93% idle, 39–42 °C |

Ten commits, `5758a6e..1bbf009`. Everything is deployed and verified on the
hardware, not just tested.

## What was built

**The panel** (`5758a6e`). Full-screen dashboard from cold boot, logging itself
into both the dashboard and Home Assistant by IP address. Two scripts:
`setup-kiosk-display.sh` for the panel, `enable-kiosk-autologin.py` for the
board. `192.168.0.176` is now a credential — see `docs/kiosk-display.md`.

**Deploys reach open browsers** (`d817f6c`). The page polls `build_info.json`
once a minute and reloads on a change, waiting for `/api/health` first so a
reload cannot land during the service restart a deploy causes. Without this the
panel would hold its build for weeks; with it, every deploy this session arrived
on the panel unattended.

**A camera shows itself on motion** (`d817f6c`), then **follows a person along a
route** (`8e5df4d`). Off by default per screen — a tickbox on the camera card,
stored in that browser's `localStorage`, so the panel and a laptop can disagree.
The route opens the camera someone has reached plus the one they are walking
towards, and advances one-way.

**The detector stopped asking for frames one at a time** (`8e5df4d`). It used to
fetch a JPEG per cycle from go2rtc: a fresh consumer each time, waiting for the
camera's next keyframe, **0.6–3.2 s a frame against 64 ms of inference**. Nearly
all the latency was in the asking. One held-open RTSP consumer is ~2 ms a frame,
at ~15% of a core per camera to keep decoding.

## Measurements worth keeping

Panel, one stream, measured with frames counted rather than CPU alone:

| Stream | CPU (of one core) | fps |
| --- | --- | --- |
| 1920×1080 | 72% | 20.4 |
| 1280×720 (Tapo C210) | 37% | 11.3 |
| 640×360 (Tapo C200) | 41% | 14.6 |
| 640×352 | 33–37% | 12.6 |

**A stream costs ~35% of a core just to exist.** Resolution only starts to matter
at 1080p — 720p costs the same as 360p. So stream *count* matters more than
resolution, which is why the route holds two and not three.

Simultaneous streams on the panel: **six play** (2.26 of 4 cores, 69% busy);
**eight do not** — two tiles froze a minute behind with visible decode
corruption, and CPU *fell*, because a stalled tile is cheap.

Of the three camera brands here, **Tapo is the best behaved**: plain RTSP, H.264,
a proper substream on a standard path, no ffmpeg on the board, best pixels per
CPU. Wyze needs `rtsps` so go2rtc wraps it in ffmpeg even to copy. The Hipcam
pair were the worst until this session.

## Things that were believed and turned out wrong

Each of these was stated confidently before being measured. They are the reason
this file exists.

- **"The panel software-decodes video."** It does not. Chromium holds
  `/dev/video10`, the `bcm2835-codec` H.264 decoder, open on both the WebRTC and
  MSE paths, with no flags. The Pi 4 also has an HEVC decoder at `/dev/video19`.
  The CPU goes on scaling and compositing, not decoding.
- **"Enabling V4L2 flags will help."** They halve CPU and quarter the frame rate.
  `--enable-features=V4L2FlatStatefulVideoDecoder` drops 72% → 46% and 20.4 fps →
  **3.85**. The zero-copy variant reports `Context lost during MakeCurrent`.
- **"The frontyard camera has a Wi-Fi problem."** The board loses packets to its
  own router at the same rate. It is the board's link, not the camera.
- **"Pre-warm only the next camera."** True, but not for the reason first given:
  the binding constraint is that re-creating an `<iframe>` reloads it, so slots
  had to become DOM nodes managed individually.

The recurring lesson: **CPU alone is a trap.** A player showing a black
rectangle is the cheapest configuration there is, and it nearly read as success
three separate times. Every measurement here now counts frames.

## Camera and board fixes

- **Garage camera off HEVC** (`dd503b2`). WebRTC cannot carry HEVC, so go2rtc
  transcoded it permanently — 7–19% of a board core. It now encodes H.264 and
  go2rtc copies bytes. Its ONVIF *reports* H264 while streaming HEVC, so
  `--show` says there is nothing to fix; the write works anyway. Tool:
  `scripts/camera-set-h264.py`.
- **Frontyard on its 640×352 substream.** 72% → 33% on the panel, no transcode.
- **Front door deliberately left at 1080p.** It is the camera you want a face
  from and where the route ends. Worst case is now one 1080p plus one substream,
  about one core of four.
- **Stream names** `chortau_camera_1/2` → `frontyard_camera`/`garage_camera`,
  done before anything bound to the old entity ids.

## Open — needs a person, not a session

1. ~~**Wi-Fi power save on the board.**~~ ~~**Ethernet.**~~ **Both done
   2026-09-12** — the board is on `enp97s0` and Wi-Fi is disconnected. Items 1
   and 2 were the same problem and Ethernet was always the better half of it.
   Measured before and after, same test to the router:

   | | avg | peak | loss |
   | --- | ---: | ---: | ---: |
   | Wi-Fi, power save on | 333 ms | ~2 s | ~5% |
   | **Ethernet, 1000 Mb/s** | **0.78 ms** | 2.1 ms | **0%** |

   Two consequences worth carrying forward. **The wall panel is still on Wi-Fi**,
   and panel → board still measures ~50 ms average with a 308 ms peak — so any
   latency that survived this change belongs to the panel's link, not the
   board's. And **`192.168.0.83` is a DHCP lease**: the whole repo now hardcodes
   it, so it needs a router reservation before it moves on its own.
2. **The board's fan is doing nothing.** 26,012 samples over nine days: 91% of
   the time at 35–44 °C, one sample ever at 65 °C, critical trip **98 °C**, and
   the thermal governor has asked for cooling **zero** times. There is no
   OS-controlled fan — nothing in `hwmon`, no PWM, no tachometer, and no fan node
   in the device tree — so it runs flat out forever. Unplug it and watch
   `~/resource-history.log`.

   **The panel settled the same question first.** Its fan came out on 2026-09-12
   and it went 36 °C → 55–58 °C, peak 59 °C, **zero throttling** across seven
   hours, against an 80 °C trip. The board has a bigger heatsink, twelve cores it
   barely uses, and a 98 °C trip, so it is the safer of the two. The panel now
   logs too — `resource-logger.service` there as well as on the board.
3. **Server-side camera mosaic**, parked in `PROJECT_CONTEXT.md` with its
   measurements. Six-camera mosaic costs 67% of one core of twelve. The GPU
   cannot help: this board exposes **no hardware video codec** (no V4L2 device
   has an output queue; `/dev/video-cixdec0` is the ISP), and `overlay_opencl`
   segfaults on the real pipeline while Vulkan fails at the first filter.

## Related

- `docs/kiosk-display.md` — how to build, verify and undo all of the above
- `PROJECT_CONTEXT.md` — the mosaic entry under Recommended next milestones
- `CLAUDE.md` — the move to Ethernet, the DHCP-lease warning, and the detector's frame source
