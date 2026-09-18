# Cast to TV

The dashboard, as live video, on a TV with the **LLANO-S450** EZCast dongle in
one of its HDMI inputs. Switched in **Settings → Cast to TV**; off by default.

It is a picture of the dashboard, not the dashboard: nothing on it can be
touched, it runs at 4 fps, and a few seconds behind. For a screen you use, the
Raspberry Pi 4 wall panel (`docs/kiosk-display.md`) is the better answer; this
is for a TV with nothing else plugged in.

## How

```
headless Chromium --(CDP screenshots, 4/s)--> ffmpeg libx264 --> MPEG-TS
    --> http://192.168.0.83:8765/<token>.ts --> DLNA SetAVTransportURI + Play
```

`src/python/dashboard_cast.py`, run by `dashboard-cast.service` (a systemd *user*
unit). The switch is the unit: `systemctl --user enable --now` / `disable --now`,
done by `PUT /api/cast`. The deploy installs the unit and never enables it; it
restarts it only if it is already running.

| | Cost |
| --- | --- |
| Off | Nothing. No process; the unit file on disk. |
| On, TV off or busy | One idle Python process; an SSDP search every 30 s. |
| On, casting | ~1.3-1.5 cores (Chromium ~115%, ffmpeg ~30%), ~600-700 MiB heap + shared memory with the front door camera on Home, ~2.4 Mbit/s to the dongle. Measured 2026-09-18. |

When on, it casts only to an **idle** dongle (never over somebody's phone, but
over a stream of its own left from before), stops Chromium and ffmpeg when the
dongle stops pulling the stream or plays something else, and tells the dongle to
stop when switched off.

**Capture and encoding are decoupled**, which is what made it reliable. Chromium's
screenshots update the latest frame; a feeder hands ffmpeg that frame at a steady
4 fps whatever Chromium is doing. So a slow or stuck Chromium freezes the picture
instead of starving the stream (a starved stream is what the dongle drops), and
Chromium can be replaced mid-stream: when a picture is 20 s late, when the unit's
heap plus shared memory passes 900 MiB (`DASHBOARD_CAST_MEMORY_MB`), and hourly.
The first version ended the whole cast on one slow screenshot, and on three slow
status answers - the dongle times out on requests while it decodes, so **whether it
still pulls the stream** is the liveness signal, not its SOAP answers. It also
misses SSDP searches while busy, so the last known description URL is tried first.

The page's clock follows the browser's zone: Chromium gets
`TZ=America/Vancouver` (`DASHBOARD_CAST_TZ`), independent of the board's.

The stream URL carries a per-session token and is served only to the dongle's address. Settings, all
optional, in `.env`: `DASHBOARD_CAST_RENDERER` (name to match, default
`LLANO-S450`), `DASHBOARD_CAST_FPS` (4), `DASHBOARD_CAST_PORT` (8765),
`DASHBOARD_CAST_URL` (Home), `DASHBOARD_CAST_TZ` (`America/Vancouver`).

## What the dongle can and cannot do

Measured 2026-09-18 against its firmware (Actions-Micro, Cast build 1.36):

- **Google Cast web pages: no.** `GET_APP_AVAILABILITY` answers
  `APP_UNAVAILABLE` for DashCast (`84912283`), Home Assistant's Lovelace
  (`A078F6B0`) and media (`B45F4572`) receivers, and YouTube. Only the Default
  Media Receiver (`CC1AD845`) and Backdrop are available.
- **Google Cast images: no.** The Default Media Receiver accepts `image/jpeg` and
  never fetches it.
- **DLNA: yes.** Images and a live MPEG-TS H.264 stream both play.
- **AirPlay:** advertises photo and screen mirroring but not video URLs (feature
  bit 0 clear). No Linux sender for mirroring; not pursued.

## Traps

- **The dongle's Cast TLS is too old for current Python.** It offers only RSA key
  exchange ciphers; the default context fails the handshake, which is why Home
  Assistant's Cast integration logs connection failures for it. A context with
  `set_ciphers("DEFAULT:@SECLEVEL=0")` connects. Not needed for DLNA.
- **Chromium hangs silently in a systemd user unit on this board.** The user
  manager carries the desktop session (`DISPLAY`, `WAYLAND_DISPLAY`, the session
  bus); Chromium asks the GNOME keyring for a password store and never opens
  DevTools. It works from ssh, which makes it look like something else. Pass
  `--password-store=basic` and drop those variables.
- **The first `about:blank` tab can spin** and never answer DevTools. Open a
  fresh one with `PUT /json/new`.
- **Write frames to ffmpeg off the event loop.** A blocking `stdin.write` stalls
  the loop that drains ffmpeg's stdout, and the two deadlock with no error.
- **`-x264-params repeat-headers=1`.** The dongle joins mid-stream; without SPS/PPS
  on every keyframe it decodes nothing.
- **Renderer shared memory is decoded camera video.** 230-290 MiB with the family
  room camera on Home, rising to ~430 MiB and trimmed back around 600-700 MiB for
  the unit with the front door camera. Heap stays flat, so it is a cache, but it
  is shmem - not reclaimable on a swapless board. Hence the 900 MiB Chromium
  refresh under `MemoryMax=1536M`.
- **Home Assistant's own camera snapshots are ffmpeg `image2pipe` processes
  too**, as root in its container. Never clean up by matching that pattern.
