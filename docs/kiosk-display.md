# Wall panel: the dashboard on the Raspberry Pi 4

The Raspberry Pi 4 runs none of this project. It is a browser on a wall, pointed
at the Orange Pi, that comes up by itself after a power cut and never asks
anybody for a password.

**Live since 2026-09-10.** Panel `smarthome@192.168.0.176`, Debian 13 (trixie),
labwc/Wayland, HDMI-A-1, Chromium 148.

```
Raspberry Pi 4 (192.168.0.176)                Orange Pi 6 Plus (192.168.0.234)
┌──────────────────────────────┐              ┌─────────────────────────────┐
│ lightdm autologin            │              │ dashboard  :8000            │
│   └ labwc session            │  ──────────► │   trusted_hosts: .176       │
│       └ xdg autostart        │              │                             │
│           └ smart-home-kiosk │              │ Home Assistant :8123        │
│               └ chromium     │  ──────────► │   trusted_networks: .176/32 │
│                   --kiosk    │  (iframe)    │                             │
└──────────────────────────────┘              └─────────────────────────────┘
```

## Install

Two halves, because they touch two different machines. Run both from the
workstation, in this order:

```bash
scripts/setup-kiosk-display.sh                                  # the panel
scripts/enable-kiosk-autologin.py --kiosk-ip 192.168.0.176      # the board
sudo reboot                                                     # on the panel
```

The first installs the launcher, the autostart entry, and turns off screen
blanking. The second opens both login doors for that one address, validates the
Home Assistant config before restarting anything, and is safe to re-run — it
updates its managed block in place rather than appending a second one. Add
`--dry-run` to see what it would do.

Both scripts are the source of truth. Nothing is left on the panel or the board
to hand-edit: `enable-kiosk-autologin.py` pipes its payload over ssh and
`setup-kiosk-display.sh` re-copies the launcher every run.

### Pin the address first

The panel's IP **is** its credential, at both doors. Give `192.168.0.176` a
static DHCP lease in the router before relying on this. If DHCP moves the panel,
it is locked out of both logins; if DHCP hands that address to something else,
that thing inherits the panel's access. This is the same trade Home Assistant's
own `trusted_networks` provider makes, and there is no token-shaped alternative:
the HA *frontend* keeps its refresh token in the browser's localStorage, so no
header we could set will log it in.

## What each half actually changed

| Where | What |
| --- | --- |
| `configs/devices.local.yaml` on the board | `dashboard_auth.trusted_hosts: [192.168.0.176]` |
| `configuration.yaml` on the board | a delimited `homeassistant: auth_providers:` block |
| `~/.local/bin/smart-home-kiosk` on the panel | the launcher, from `scripts/kiosk/kiosk-launch.sh` |
| `~/.config/smart-home-kiosk.env` on the panel | `DASHBOARD_URL` |
| `~/.config/autostart/smart-home-kiosk.desktop` on the panel | what starts it |

Both config files are backed up as `*.bak-kiosk-<timestamp>` before every edit.

The dashboard side is [`web_app.py`](../src/python/web_app.py)'s auth
middleware: a listed address skips the session-cookie check outright, and a
trusted host that lands on `/login` is redirected to `/` instead of being shown
a form it cannot fill in. Everyone else is challenged exactly as before —
including this workstation, which is the check worth running after any change:

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://192.168.0.234:8000/api/health   # 401
ssh smarthome@192.168.0.176 'curl -s -o /dev/null -w "%{http_code}\n" http://192.168.0.234:8000/api/health'  # 200
```

## A screen shows a camera on motion

A camera paired with a motion sensor in `configs/devices.local.yaml` can take
over the Home card by itself:

```yaml
cameras:
  - name: Front door camera
    # ...
    motion_entity: binary_sensor.0xa4c138f3061bad8d_presence
    motion_linger_seconds: 300
```

Pairing only *offers* the behaviour. Each screen turns it on for itself with the
**Auto on motion** checkbox on the camera card, which is off until someone ticks
it — so the wall panel and a laptop can each opt in without agreeing with each
other, and a phone that never opts in is unaffected. Once ticked, the card
switches to the camera while the sensor reads motion; five minutes after it
reads clear, the stream stops and the card goes back to the camera you chose.

Live on this house since build #199, front door camera paired with *Motion
sensor and TH front door*.

Three rules shape how it behaves around people, and each is there for a reason:

- **Every screen decides for itself, and starts out saying no.** A dashboard
  left open on a phone would otherwise pull a video stream over cellular because
  a cat crossed the doorstep. The preference is this browser's `localStorage`,
  so it survives reloads and needs no account, server config, or per-device
  setup — and the switch hides itself entirely when no camera is paired, rather
  than offering a control that cannot do anything.
- **Your saved camera choice is never overwritten.** The episode sets an
  override that the card prefers, rather than writing the door camera into
  `localStorage`; a badly timed reload during an episode would otherwise leave
  the door camera as your permanent choice.
- **A person beats the automation.** Touching the play/stop button or the camera
  dropdown releases the episode — it stops managing the card and will not yank
  the picture away five minutes later. The next time motion rises, it starts
  fresh.

The checkbox persists; an episode does not. A reload mid-episode re-derives it
from the sensor: still moving, the camera comes back; already clear, it does
not.

### Following somebody along a route

Cameras can also be chained, so the card follows a person instead of sitting on
one view. `camera_paths` lists them in the order somebody crosses them:

```yaml
camera_paths:
  - name: Front approach
    linger_seconds: 300
    cameras: [Garage camera, Frontyard camera, Front door camera]
```

Each camera still needs its own `motion_entity` — that is what announces
somebody reaching it. Live on this house since build #204, driven by the NPU
person detector on the two outdoor cameras and the Zigbee PIR at the door.

There is no re-identification model and there should not be. The geometry
already says it is the same person walking, and matching people between views
would mean a second graph on an NPU where a QDQ `Concat` silently zeroed the
last one's outputs for days. What the route needs is an order, and you know it.

Four things carry it, and each was measured rather than assumed:

- **The next camera is opened before they reach it.** A WebRTC stream takes a
  few seconds to come up, and by then they have walked out of frame — so the
  card holds the camera on screen *and* the one they are heading for.
- **Only those two.** Holding all three put the Pi 4 at 80% CPU with two
  Chromium processes pegged at ~85% of a core each, and none of the streams
  finished connecting. Only the next one has to be ready.
- **Slots are DOM nodes, not markup.** Re-creating an `<iframe>` reloads it, so
  rebuilding the card to add the next camera would drop the stream currently on
  screen — a black gap at the exact moment somebody walks into view. The card is
  managed node by node during an episode, which is why it bypasses `renderHtml`
  and clears that function's cache on the way in and out.
- **Advancing is one-way.** `NPU_PRESENCE_HOLD` keeps the garage sensor true for
  a minute after somebody has left it, so the rule is "the furthest camera that
  has seen them". Anything else retreats to a view they have already left.

To watch it work without standing at the door, nudge the sensor in Home
Assistant. The real Zigbee device reasserts its own state on its next report, so
this is a nudge rather than an edit — but pass the attributes back or the entity
loses its `device_class` and the dashboard stops recognising it as occupancy:

```bash
ssh orangepi@192.168.0.234 'cd smart_home_AI && set -a && . ./.env && set +a && curl -s -X POST -H "Authorization: Bearer $HOME_ASSISTANT_TOKEN" -H "Content-Type: application/json" -d "{\"state\":\"on\",\"attributes\":{\"device_class\":\"occupancy\",\"friendly_name\":\"Motion sensor and TH front door Occupancy\"}}" http://127.0.0.1:8123/api/states/binary_sensor.0xa4c138f3061bad8d_presence'
```

## Deploys reach the panel on their own

A deploy replaces `app.js` on the board but not the copy Chromium is already
running, and nothing tells it to look again. Since build #197 the dashboard
polls `/static/build_info.json` once a minute and reloads when the number
differs from the one the page loaded with, so the panel picks up a deploy within
about a minute without anyone touching it. The reload waits for `/api/health` to
answer first, because `deploy-dashboard.sh` restarts the service *after* copying
the files — reloading into that gap would swap a working panel for a Chromium
error page.

To push a deploy through immediately, kill Chromium; the launcher has it back in
five seconds:

```bash
ssh smarthome@192.168.0.176 'pkill -f chromium-kiosk'
```

That is also how you bootstrap a panel still running a build from before the
watch existed — it cannot reload itself into the version that knows how to.

## Verify

```bash
ssh smarthome@192.168.0.176 'tail -5 ~/.local/state/smart-home-kiosk.log'
ssh smarthome@192.168.0.176 'curl -s http://192.168.0.234:8123/auth/providers'
```

The providers list seen **from the panel** must have `trusted_networks` first
and `homeassistant` second. Seen from anywhere else it must contain only
`homeassistant` — Home Assistant computes that list per client address, which is
why the panel's shortcut costs no one else anything.

For a picture of what is actually on the screen, the panel has `grim`:

```bash
ssh smarthome@192.168.0.176 'XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-0 grim /tmp/panel.png'
scp smarthome@192.168.0.176:/tmp/panel.png .
```

## The traps

Most of these cost an hour each. They are listed in the order they bite.

- **`--ozone-platform-hint=auto` guesses X11 and dies.** The hint reads
  `XDG_SESSION_TYPE`, which is `tty` over ssh — so Chromium picks X11, fails with
  *"Missing X server or $DISPLAY"*, and the launcher respawns it for ever. The
  launcher now finds the compositor socket in `XDG_RUNTIME_DIR` itself and passes
  `--ozone-platform=wayland` explicitly. This only shows up when testing a panel
  over ssh, which is exactly how you will test a panel that is already on a wall.
- **`trusted_networks` must be the first auth provider.** The frontend renders
  `providers[0]` as the login form and pushes the rest under *"Or log in with"*.
  With `homeassistant` first, `allow_bypass_login` looks broken: the panel gets a
  password box and a "Trusted Networks" link nobody is there to tap. Ordering it
  first is invisible to every other client, because the list is per-address.
- **Listing `auth_providers` at all replaces Home Assistant's implicit default.**
  The `- type: homeassistant` entry is what keeps password login working
  everywhere else. Delete it and nothing can log in with a password again.
- **`trusted_users` pins the panel to one user.** Without it a trusted client
  gets a user picker instead of a session. The configurator asks Home Assistant
  who owns `HOME_ASSISTANT_TOKEN` (`auth/current_user` over the WebSocket API)
  and pins that user, so the panel logs in as whoever the board already acts as.
- **`yaml.safe_load` cannot read Home Assistant's `configuration.yaml`.** It dies
  on `!include` and `!secret`. Validating the edit needs a loader with
  `add_multi_constructor("!", ...)`, or every config looks broken.
- **Screen blanking on labwc is one line in `~/.config/labwc/autostart`** — a
  `swayidle` invocation. That is all `raspi-config nonint do_blanking 1` writes
  there, so removing the line needs no sudo, which matters when the panel's user
  has a sudo password. The launcher also re-kills stray `swayidle` every 60s,
  because the session can start one after the autostart entry has run.
- **Chromium thinks a power cut is a crash** and parks a *"Restore pages?"* bar
  over the dashboard that nobody is there to dismiss. The flags help; rewriting
  `exit_type` in the profile's `Preferences` before each launch is what actually
  stops it.
- **A systemd `--user` unit is the wrong tool here.** It starts outside the
  Wayland session and has no `WAYLAND_DISPLAY` to draw on. The Pi's labwc session
  runs `lxsession-xdg-autostart`, so `~/.config/autostart/*.desktop` is the hook
  that works.
- **The dashboard rewrites `devices.local.yaml` itself** when devices are added,
  with plain `yaml.dump` — comments there do not survive. Keep the explanation in
  `configs/devices.example.yaml`, which is only ever edited by hand.
- **Camera tiles are the expensive part, and hardware decode is already on.**
  Measured 2026-09-12: Chromium holds `/dev/video10` (the `bcm2835-codec` H.264
  decoder) open on both the WebRTC and MSE paths, with no flags. What costs the
  CPU is everything around the decode — scaling to the card, compositing in the
  browser and again in labwc, WebRTC's own work. So the lever is **pixels, not
  the decoder**:

  | Stream | CPU | fps |
  | --- | --- | --- |
  | 1920×1080 over WebRTC | 72% of one core | 20.4 |
  | 640×352 over WebRTC | 33% of one core | 12.5 |

  The camera card is ~520 px wide, so a 1080p stream means decoding 13× more
  pixels than the screen ever shows. Prefer the camera's own substream.
- **Do not "enable" hardware decode with Chromium flags — it is already on, and
  the flags break it.** `--enable-features=V4L2FlatStatefulVideoDecoder` looks
  like the fix and drops CPU to 46%, which looks like a win until you count
  frames: playback collapses from 20 fps to **3.85 fps**. Adding
  `AcceleratedVideoDecodeLinuxZeroCopyGL` produces `Context lost during
  MakeCurrent` and a fallback; adding `--use-gl=egl` costs 92% of a core.
  Measure frames decoded, never CPU alone — a player showing a black rectangle
  is the cheapest configuration there is, which is exactly how the HEVC camera
  fooled this measurement once already.

## Undo

Remove the `trusted_hosts` line from `configs/devices.local.yaml` and the block
between the `smart-home kiosk autologin` markers in `configuration.yaml`, then
restart both services. On the panel, delete
`~/.config/autostart/smart-home-kiosk.desktop`. The `*.bak-kiosk-*` files next to
each config are the state before the first run.
