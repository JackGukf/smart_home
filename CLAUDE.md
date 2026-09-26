# Smart Home AI (Orange Pi 6 Plus) — Claude Code Context

> **Recovered 2026-09-03. The stack is running again**, booted from the NVMe in
> the PCIe slot: dashboard, go2rtc, Home Assistant, Zigbee (5 devices), Matter
> controller, resource-logger — all enabled and surviving a reboot.
>
> **Local AI** — Ollama is live and alone; **run one LLM, not both**, there is no
> swap. The NPU detector is **live since 2026-09-09** on five cameras: the
> detection head is cut off the graph and decoded in numpy. See
> `docs/npu-model-pipeline.md`.
>
> **Voice, in progress (2026-09-13).** Whisper and Piper run on the board and
> Assist answers; the ESP32-S3-Touch-LCD-4B satellite is flashed, plays audio and
> captures from its microphone. Its on-device wake word looked dead but was
> stopped for the first playback and never restarted — fixed and verified the
> same evening; detection by a real voice is the next check.
> Since 2026-09-14 the panel's commands go through a **voice resolver**
> (`configs/homeassistant/custom_components/voice_resolver`): HA's own matcher
> first, then a deterministic fuzzy match with "Did you mean …?" — no model.
> Its logic is `resolver.py`, testable without HA.
> Start here: **`docs/handoff-2026-09-13-voice-satellite.md`**.
>
> **Panel touch screen, finished (2026-09-15).** The 4" LCD runs an app launcher
> under ESPHome (`docs/design/voice-panel-screens.html`, revision 2): Lights,
> Climate, Scenes, Security, Cameras and Wall panel, with swipe-back, sleep after
> 2 minutes and wake on touch or "Okay Nabu". Camera frames come from
> `panel-camera.service` on the board (`src/python/panel_camera.py`): fetching
> snapshots from go2rtc directly blocked the panel's main loop and garbled voice.
> Since 2026-09-15 also Settings as apps (Volume, Sleep, Wi-Fi, Schedule, About -
> firmware 0.2.0, all kept in flash), a night schedule for the screen, launcher
> pages and the weather. The voice-time flicker is fixed
> (`CONFIG_LCD_RGB_RESTART_IN_VSYNC` must stay off), and camera frames no longer
> use internal heap (`SPIRAM_USE_MALLOC`, internal reserve left at its default) -
> see the handoff. Open: the backlight, which is not the ST7701, GPIO4 or
> expander pin 4, cannot be switched off in sleep.
> Start here: **`docs/handoff-2026-09-14-panel-display.md`**.
>
> **Dashboard redesign and house learning (2026-09-16 to 09-18, v0.7.0 build 261).**
> Home, Security (a picture of the house with live pins), Status (small charts,
> Today at a glance, House learning) were rebuilt with the owner. New: the Govee
> H5140 CO2 monitor, Govee cloud fallback for the ambient lights, Tuya IR hubs
> driven locally (learned buttons become HA buttons over MQTT), Quick actions
> that report what they did, and the Voice Panel's wall-panel remote now scrolls
> and steps the Home camera. **`house-memory.service`** keeps every HA event
> (`~/house-memory/events.db`); **`house-learning.timer`** (03:30 Vancouver)
> retrains a routine model and logs unusual moments *silently*. The Tuya IoT
> Core trial has **expired** (cloud calls fail). The hallway wall panel is
> **1920 × 1080**; the owner's iPad Air is the **13-inch** - and Safari before
> iPadOS 16 ignores container queries, so iPad layout rules are media queries.
> Start here: **`docs/handoff-2026-09-18-dashboard-and-learning.md`**.
>
> **Cast to TV, family room lighting, All lights and Energy (2026-09-19, build 286).**
> The dashboard casts to the TV's LLANO-S450 dongle (Settings → Cast to TV, off
> by default; `switch.tv_cast` and a TV cast remote on the Voice Panel). Two IKEA
> cabinet drivers and a TP-Link cabinet plug joined Movie mode; the family room
> accent lights turn on with motion (any time of day) and off late at night (start
> time in Settings → Night lights). **Anything that turns lights on sends "on"
> only to lights that are off** - the owner's rule. All lights on/off follow
> Manage, on the dashboard and the Voice Panel. Home has the owner's layout with
> an Energy card; the Energy view runs on **sample data** until the PowerLync is
> paired. Discovery is one sidebar entry with three apps.
> Start here: **`docs/handoff-2026-09-19-cast-lighting-energy.md`**.
>
> **Energy, ready for the PowerLync (2026-09-19).** `/api/energy` switches to
> live electricity by itself once the PowerLync's sensors appear in Home
> Assistant; pairing is one command, `scripts/setup-ha-powerlync.py --code …
> --apply`. Gas cannot be read locally (FortisBC's FlexNet meter); options and
> the energy "AI mode" plan are in **`docs/energy-monitoring.md`**.
> **Paired 2026-09-23** (`Powerlync-002-004cce`), **reporting since 2026-09-24
> 09:20** - the page is live. Its first reading (0 → 104491.9 kWh) was booked by
> HA as one hour's use; corrected in HA's statistics and guarded in
> `metered_kwh` (see the 2026-09-19 handoff, "Update 2026-09-24").
>
> **Matter bridge live since 2026-09-06** (`matter-bridge.service`, a systemd
> *user* unit), exposing 5 devices and commissioned into three fabrics —
> chip-tool, Home Assistant, and Apple Home. Build or re-commission it with
> `docs/matter-bridge-runbook.md`; do not improvise, the traps are subtle and
> several present as a different problem than they are.
>
> - **To rebuild it: `docs/restore-runbook.md`** — ordered procedure, verification
>   counts, and the traps that do not announce themselves.
> - Why it was rebuilt, and the reset investigation: `docs/handoff-2026-09-03-recovery.md`.
>
> **Memory and logs (2026-09-19):** the NPU driver holds 4 GB of DMA memory from
> boot (4 x 1 GiB, sized by RAM, used or not); the desktop stays on at boot and
> Settings -> Desktop stops it until the next restart; **logs are on the NVMe
> now** (orangepi-ramlog off, journal capped at 1 GB) - before, 25 minutes of
> history and none after a crash. The `arm-smmu-v3 event 0x07` flood is a known
> CIX firmware bug. See `docs/setup-orangepi6.md`, "Memory, logs and the desktop".
>
> **Service watchdog (2026-09-24).** Crashes were always restarted; *hangs*
> were not - on 2026-09-23 the Zigbee coordinator hung for 20 h with every
> container "Up". `service-watchdog.timer` (every 2 min,
> `src/python/service_watchdog.py`) checks that Zigbee devices are talking,
> the broker, Home Assistant's API and its Zigbee link, the dashboard, go2rtc,
> the house memory and the Matter controller actually work, restarts what hung
> (at most 3 times in 6 h, then asks for a person), and reports on the
> dashboard (banners, Status view) and in Home Assistant. **Pause it** before
> re-flashing the dongle or upgrading HA: `touch deploy/watchdog/.paused`.
> Install: `scripts/install-service-watchdog.sh` (+ `sudo … --polkit` to let
> it restart matter-server).
>
> **Never set `RuntimeWatchdogSec` on this board.** Its SBSA watchdog has a fixed
> 10 s timeout that cannot be raised, so a 60 s setting resets the board every
> ~80 s with no kernel panic. That is the prime suspect for the 2026-09-02 reset
> loop. The `orangepi` and root passwords were changed from the image default
> on 2026-09-25; a freshly flashed board is back to `orangepi` until changed.

> **House modes and the armed house (2026-09-24).** `input_select.house_mode`
> (Home / Away / Vacation) drives lights, the alarm and an ecobee vacation, set
> by presence or by hand on the Security view; while armed, an unexpected person
> downstairs sounds the Zigbee alarm speaker (Stop on the dashboard, or the
> bedroom button once; twice = Night arm). The alarm also arms itself at 01:30
> from outside HA until the owner deleted that schedule. Remote access is
> Tailscale. **Front door left open** alerts (2026-09-25) go to the dashboard, the
> iPhone and Telegram (bot Hornby_House, token only on the board). See
> `docs/house-modes.md`, `docs/door-alerts.md` and the 2026-09-19 handoff,
> "Update 2026-09-24 (evening)" and "Update 2026-09-25".
> **Water leak and smoke alerts** (2026-09-25): critical iPhone push, Telegram
> and a red dashboard banner, plus a daily low-battery / not-reporting check -
> `scripts/install-safety-alerts.py`, sensors in `src/python/safety_sensors.py`,
> see `docs/safety-alerts.md`. The dashboard's **disarm PIN** is
> `security.disarm_pin` in `devices.local.yaml`, quoted (`docs/house-modes.md`).
> `/bridge/*` answers loopback only; sessions are signed with a random key
> (`configs/dashboard_secret.key` or `DASHBOARD_SECRET_KEY`), never the password.
> **Night watch** (2026-09-25, `night-watch.service`): at night, outdoor motion
> or an outdoor camera's person -> 20 s clip + snapshot in `~/night-clips/`, photo
> to Telegram; the siren records the indoor cameras day or night. The office
> camera saw false "people" at night (chair/photos), so it now has the motion
> gate; night evidence snapshots show its boxes. See `docs/night-watch.md`.
> The garage camera also counts leaving/arriving (watch-only), `docs/house-modes.md`.

> **AI view and gas from furnace runtime (2026-09-19).** The sidebar's
> Automations is now **AI**: Automations as before, plus **AI data** - upload
> FortisBC bills (PDF) and exports (CSV), type meter readings, and see the gas
> model. Gas cannot be read from the meter, so it is fitted as
> `base x days + rate x furnace hours` from **Ecobee's runtime report**
> (two years back, read-only) and corrected by the readings. In September it
> reports `waiting_for_heating` - the furnace has never run. See
> `docs/energy-monitoring.md`.

> **One thermostat, two integrations (2026-09-20).** The ecobee is in Home
> Assistant twice - HomeKit on the LAN, and the cloud integration that carries
> the room sensors, presets and `equipment_running`. The HomeKit copy is
> *hidden, not disabled* (`scripts/hide-duplicate-ecobee.py`), and the
> dashboard ranks an **answering** thermostat above a richer one, so the card
> falls back to local control by itself when the internet goes and back again
> when it returns.
>
> **Text overlap is testable now:** `scripts/check-card-overlap.py` drives
> Chromium on the board across every view and device size. See the 2026-09-18
> handoff.

## Project Overview

Smart home controller for an **Orange Pi 6 Plus** targeting TP-Link/Kasa switches, Tuya sensors, Govee/Lepro ambient devices, cameras, Home Assistant entities, a Matter bridge, and a web dashboard. Dual-language: Python for fast automation and C/C++ for long-running services.

The workspace was migrated from `smart-home-rpi4` to `smart_home_AI` on 2026-07-29 with Git history intact, and the deployment target moved from the Raspberry Pi 4 to the Orange Pi 6 Plus. Read `PROJECT_CONTEXT.md` for the full handoff.

## Target Hardware

The Orange Pi 6 Plus is the **primary** target. The Raspberry Pi 4 is kept as a **secondary** target so the existing remote install keeps working — it is never the default; select it explicitly.

| | Orange Pi 6 Plus (primary) | Raspberry Pi 4 (secondary) |
| --- | --- | --- |
| OS | Ubuntu 24.04 ARM64 | Raspberry Pi OS 64-bit |
| CPU | Cix P1 / CD8180, 12 cores, Armv9.2-A (Cortex-A720 + A520) | Cortex-A72, Armv8-A |
| SSH | `orangepi@192.168.0.83` | `smarthome@192.168.0.176` |
| Remote path | `/home/orangepi/smart_home_AI` | `/home/smarthome/smart-home-rpi4` |
| Net interfaces | **`enp97s0` (Ethernet, in use)**, `wlp1s0` (Wi-Fi, disconnected) | `wlan0`, `eth0` |
| CMake preset | `docker-orangepi6-release` | `docker-rpi4-release` |
| Toolchain | `cmake/toolchains/orangepi6-aarch64.cmake` | `cmake/toolchains/rpi4-aarch64.cmake` |
| Build dir | `build/orangepi6-release/` | `build/rpi4-release/` |

Since 2026-09-10 the Raspberry Pi 4 is **also the wall panel**: it displays the
dashboard full screen from boot and logs itself into both the dashboard and Home
Assistant by IP address. That makes `192.168.0.176` a credential — see
`docs/kiosk-display.md` before changing it, and before deploying to that host.

Gotchas that have bitten this project:

- **Interface names differ, and a wrong one fails silently.** Ubuntu uses predictable names, so anything passing `--interface` (notably the Matter bridge in `configs/matter-bridge.service`) must use `enp97s0`, not `wlan0`. This is not hypothetical: when the board moved to Ethernet on 2026-09-12, `wlp1s0` stopped existing and **two** services went on reporting `active` while bound to a device that was gone — `matter-bridge.service` (a *user* unit) and `matter-server.service` (a *system* unit, installed to `/etc/systemd/system/` by `scripts/install-matter-server.sh`). The second is the nastier one: `systemctl --user is-active matter-server` answers `not-found`, which reads like "not installed" rather than "look in the other place". Check **both** scopes whenever the network changes. **A third was found on 2026-09-13: Home Assistant's own network adapter setting** (Settings → System → Network) still had discovery on `docker0` only, with `enp97s0` disabled — so LAN discovery silently found nothing (a Govee light that answered the same scan from the board). The change only takes effect after an HA restart.
- **`-mcpu=cortex-a720` is unavailable.** It needs GCC 14+; the dev container ships the Ubuntu 22.04 aarch64 cross-compiler (GCC 11). The Orange Pi toolchain probes for the best `-march` the compiler accepts and falls back to a safe baseline. Override with `-DORANGEPI6_ARCH_FLAGS=...`.
- Both boards are `aarch64`, so a generic arm64 binary (e.g. the Matter bridge from the GN build) runs on either.
- **The board is on Ethernet since 2026-09-12, and that solved the LAN problem.**
  On Wi-Fi, power save cost 333 ms *average* round trip to the router with peaks
  near 2 s and ~5% packet loss — to the router itself, not just to a camera, on
  2 Mbit/s of traffic over a 130 Mbit/s link. It was latency, not bandwidth: the
  adapter slept between beacons, and the NPU detector holding five cameras open
  turned that into loss. On `enp97s0` at 1000 Mb/s the same test is **0.78 ms
  average, 0% loss** — a 426x improvement, measured 2026-09-12. Do not go back to
  Wi-Fi for this board; if you must, `sudo iw dev wlp1s0 set power_save off` plus
  `sudo nmcli connection modify <ssid> 802-11-wireless.powersave 2` is the
  mitigation, not a fix. **The wall panel is still on Wi-Fi** and still shows
  ~50 ms to the board, so latency that survives this change is the panel's link.
- **`192.168.0.83` is a DHCP lease, not a static address.** Everything in this
  repo hardcodes it. If the router hands the board a different address, deploys,
  the wall panel and Home Assistant all break at once. Give it a reservation.
- **Two Bluetooth controllers.** The onboard Intel AX210 (`E0:D5:5D:9D:38:97`) sits alongside the TP-Link UB500 (`20:E1:5D:68:2B:DB`), which is the one BLE should use. Pin it with `BLE_ADAPTER` in `.env` — a MAC, not `hciN`, because the numbering can swap across reboots. bleak returns *zero* devices when given no adapter on this host, so `src/python/ble_adapter.py` always passes one. See `docs/setup-orangepi6.md`.

## Repository Layout

```
src/python/          Python source modules (web_app.py, tplink_switch.py, controller.py)
src/python/web_static/  Dashboard front-end assets
src/cpp/             C/C++ source and CMakeLists.txt
src/cpp/matter_bridge/  Native C++ Matter bridge
tests/python/        pytest test suite
tests/cpp/           GoogleTest suite
scripts/             Utility, build, and deploy scripts
configs/             Device config files (never commit devices.local.yaml)
deploy/systemd/user/ systemd *user* units for the board
cmake/toolchains/    Cross-compile toolchains (orangepi6-aarch64, rpi4-aarch64)
build/               CMake out-of-tree build dirs (docker-debug, orangepi6-release, dev-check)
docs/                Architecture notes and setup guides
third_party/connectedhomeip  Matter/CHIP SDK — large, treat as a dependency
.codex/              Codex-specific config — do not modify
```

## Key Commands

### Python / tests
```bash
# Run tests (from project root)
python3 -m pytest

# Run the web dashboard locally
python3 -m uvicorn src.python.web_app:app --host 0.0.0.0 --port 8000

# Discover TP-Link switches on LAN
python3 scripts/discover_tplink_switches.py

# Control a switch
python3 -m src.python.tplink_switch --host <IP> status|on|off|toggle
```

### Docker (preferred dev environment)
```bash
docker compose build dev
docker compose run --rm dev ./scripts/dev-check.sh /workspace/smart_home_AI

# Run Python tests in Docker
docker compose run --rm dev python3 -m pytest

# Build and test C++ in Docker
docker compose run --rm dev sh -lc \
  "cmake --preset docker-debug && cmake --build --preset docker-debug && \
   ctest --test-dir build/docker-debug --output-on-failure"
```

### Orange Pi 6 Plus cross-compile and deploy
```bash
./scripts/build-orangepi6.sh          # add --board rpi4 for the secondary target
./scripts/deploy-to-pi.sh             # C++ binary + Python source
./scripts/deploy.py                   # what the last commit changed; the post-commit hook runs it
./scripts/deploy.py --dry-run         # its plan: copy, unit files, restarts
./scripts/deploy.py --rollback        # put the board's previous copies back
./scripts/deploy-dashboard.sh         # dashboard + systemd user services
./scripts/connect-pi.sh [--check]
./scripts/backup-smart-home.sh        # Zigbee key, HA config, .env -> ~/orangepi-recovery
```

Deploy scripts default to `orangepi@192.168.0.83` and `/home/orangepi/smart_home_AI`. Override with `--host`/`--user`/`--remote-path` (or `PI_HOST`/`PI_USER`/`REMOTE_PATH`) — always confirm the target before deploying, and never assume a default points at the board you mean.

### Wall panel (Raspberry Pi 4)
```bash
./scripts/setup-kiosk-display.sh                              # panel: chromium, autostart, no blanking
./scripts/enable-kiosk-autologin.py --kiosk-ip 192.168.0.176  # board: both logins, by address
./scripts/enable-kiosk-autologin.py --kiosk-ip 192.168.0.176 --dry-run
```

**Every commit deploys itself** (since 2026-09-25, `scripts/git-hooks/post-commit`, installed by `scripts/install-git-hooks.sh`): `scripts/deploy.py` copies the changed files under `src/python/`, `scripts/` and `deploy/systemd/user/`, and restarts only the running services that use them - worked out from each unit's ExecStart, its run script and the Python imports, not a table. It refuses when a board file is neither the old nor the new version (an edit made on the board), keeps the board's previous copies in `.deploy-backups/` for `--rollback`, never restarts a timer's oneshot job or starts a stopped service, and hands dashboard changes to `deploy-dashboard.sh --skip-go2rtc` (go2rtc restarts only when its own files change: a restart reconnects every camera).

`deploy-dashboard.sh` increments `BUILD_COUNT`, rewrites static cache-busting versions and `web_static/build_info.json`. It mutates the source tree; review the resulting diff. Open browsers pick the new build up by themselves: the dashboard polls `build_info.json` once a minute and reloads when it changes, waiting for `/api/health` first so a reload cannot land mid-restart.

`install-living-room-lighting.py` installs the living room rules through Home Assistant's config API, not by appending to `automations.yaml` — that runs the same validator the UI does and reloads, so a malformed template is refused rather than written and left to fail at 11pm. Two Jinja traps it exists to not repeat: these Zigbee entity ids **start with a digit**, so `states.binary_sensor.0xa4c…` is a syntax error and the subscript form is required; and **`}}` inside a Python f-string collapses to a single `}`**, silently breaking any template built that way.

`backup-smart-home.sh` reads Home Assistant's config through `sudo` — `.storage/auth` is root-owned, and a backup that skips it loses every HA token silently. It verifies the finished archive against a required-members manifest and fails loudly rather than producing a quietly incomplete backup.

## Python Environment

- Python 3, `pyproject.toml` sets `pythonpath = ["."]` so imports use `src.python.*`
- Dependencies listed in `src/python/requirements.txt`; key ones: `python-kasa`, `tinytuya`, `fastapi`, `uvicorn`, `PyYAML`, `pytest`
- Install locally: `pip install -r src/python/requirements.txt`

## C++ / CMake

- Root `CMakeLists.txt` delegates to `src/cpp/CMakeLists.txt`
- Presets in `CMakePresets.json`: `docker-debug`, `wsl-debug`, `wsl-release`, `docker-orangepi6-release`, `docker-rpi4-release`
- Cross-compile toolchains: `cmake/toolchains/orangepi6-aarch64.cmake` (primary), `rpi4-aarch64.cmake` (secondary)
- Matter bridge builds through the CHIP SDK's GN build, not these presets — see `scripts/build-matter-bridge.sh` and `docs/matter-bridge.md`

## Architecture Conventions

- One module per vendor integration (`tplink`, `tuya`, `camera`, `govee`, `automation`)
- Vendor integrations sit behind clear interfaces — keep them isolated
- Prefer local-network control over cloud where possible
- Long-running services → C/C++ daemon; scripts and API calls → Python
- The Home Assistant integration must degrade gracefully when HA is unavailable

## Local AI

Three services, all loopback-only or local-only on purpose. See `docs/local-ai.md` for the full picture — build flags, NPU op support, benchmarks, and the traps.

| Service | Endpoint | What |
| --- | --- | --- |
| `ollama.service` (system) | `127.0.0.1:11434` | Qwen3-4B Q4_K_M, Ollama API. Unloads when idle. **Live** — `scripts/install-ollama.sh`. |
| `npu-detector.service` (user) | → MQTT `smarthome/vision/<camera>` | YOLOv8n on the Zhouyi NPU. **Live since 2026-09-09**, five cameras since 2026-09-11 — mAP50 0.363, person AP50 0.633, 32.4 fps. The detection head is cut off the graph and decoded in numpy; quantising it erases what it computes. Publishes *presence*, not frames: `NPU_PRESENCE_HOLD` (60 s) delays only the falling edge, never a rise. Frames come from a **held-open RTSP consumer** on go2rtc's own `:8554` — one-shot `frame.jpeg` cost 0.6–3.2 s a frame against 64 ms of inference, which is fine for "is anyone in the office" and useless for following somebody up a drive. See `docs/npu-model-pipeline.md`. |
| `llama-server.service` (user) | `127.0.0.1:8081` | Qwen3-4B Q4_0, OpenAI API. ~3x faster prompts, holds 5GB always. **Deferred** — do not run it beside Ollama. |

Reach the LLMs with an SSH tunnel, not by widening the bind address:

```bash
ssh -N -L 11434:127.0.0.1:11434 orangepi@192.168.0.83
```

Treat model output as untrusted input: validate schema, enforce an allow-list, and keep device control deterministic. Never put the model in a trigger path — it is slower and less reliable than the rule it would replace. The useful shape is *LLM authors, rules execute*.

**The LLM is wired into the house since 2026-09-08** — before that it ran and nothing could reach it. Three ways in, all set up by `scripts/setup-ha-ollama.py` (idempotent; `--reconfigure` also updates what already exists):

| | |
| --- | --- |
| **Assist** | `conversation.local_qwen` is the *fallback* on the default pipeline, which has `prefer_local_intents` on. Home Assistant's matcher answers what it knows in ~0.02 s; only what it cannot parse waits ~22 s on the model. `conversation.local_qwen_control` can drive the house but is **not practical** — up to 10 tool iterations, over 5 minutes a question. Opt-in, on its own pipeline. |
| **Dashboard** | The **Automations** view drafts a rule from a sentence, validates it against the real house, and writes a proposal. Installing is a separate press and goes through Home Assistant's own config API, which validates and reloads. |
| **Digest** | `house-digest.timer` at 04:00 writes `house_digest.json`, shown on the Status view. **Python computes the figures and picks the few worth saying** — that list is the briefing. The model's prose is `--prose`, off by default: Qwen3-4B failed the job four different ways (`src/python/house_digest.py`). |

Three settings that are not Home Assistant's defaults, and must not be reverted:

- **`keep_alive` must be finite** (300 s). HA defaults to `-1`, "loaded for ever", which pins ~3.3 GiB and destroys the one property Ollama was chosen for on a swapless board.
- **`think` differs per agent.** On for prose (with it off, Ollama returns the reasoning *as* the answer); off for the controlling agent, which pays it once per tool iteration.
- **Giving a conversation agent `llm_hass_api` makes commands slow**, because HA then narrows local-intent matching to GetState and MediaSearchAndPlay. That is why there are two agents rather than one.

Three things that will waste a day if you do not know them:

- **`-mcpu=native` silently produces a baseline binary.** GCC 13 cannot identify this A720+A520 CPU and emits zero ARM feature macros. Always pass `-DGGML_CPU_ARM_ARCH=armv9-a+i8mm+dotprod+sve+bf16`. Worth 3x on prompt processing.
- **The A720 cores are interleaved**: `0,1,6,7,8,9,10,11`. CIX's documented taskset list is wrong for this board and costs 31% of generation throughput.
- **On the NPU, a model that runs is not proof it ran on the NPU.** Unsupported ops fall back to CPU silently — set `session.disable_cpu_ep_fallback` or you are measuring the CPU. SiLU crashes the execution provider outright, which is why stock YOLOv8 cannot run.
- **A QDQ `Concat` gives all its inputs one shared INT8 scale**, so joining tensors of different magnitude erases the smaller one. This is why quantising YOLOv8's detection head silently zeroed every class score, and it cost days chasing the calibrator instead. The head is now cut off the graph and run in numpy.

## Secrets / Credentials

- **Never commit** passwords, API keys, camera credentials, device IDs, or Wi-Fi details
- Real device config goes in `configs/devices.local.yaml` (git-ignored)
- See `configs/devices.example.yaml` for the schema
- Runtime secrets passed via environment variables (e.g. `TUYA_ACCESS_ID`, `HOME_ASSISTANT_TOKEN`, `ECOBEE_ACCESS_TOKEN`, `DASHBOARD_SECRET_KEY`)

## Testing Notes

- Python tests live in `tests/python/`, C++ tests in `tests/cpp/`
- Tests are importable without installing; `pythonpath = ["."]` in `pyproject.toml` handles this
- Use `pytest-asyncio` for async tests (`tplink_switch` controller is async)
- `tests/python/test_systemd_service.py` asserts the literal paths in `deploy/systemd/user/*.service` — update both together
- Prefer focused tests first; run the full suite when the affected boundary warrants it

## Docs

- **`docs/actions/`** — **the action list** from the 2026-09-25 review, worked one item at a
  time in the order of its README; tick items there as they are done
- `docs/setup-orangepi6.md` — verified board facts and first-time setup
- `docs/orangepi6-cross-compile-deploy.md` — build and deploy workflow (both boards)
- `docs/docker-development.md`, `docs/WSL_DEVELOPMENT.md` — dev environment
- `docs/kiosk-display.md` — **the Raspberry Pi 4 as a wall panel**: full-screen
  dashboard on boot, both logins bypassed by address, camera-on-motion and the
  camera route, and the traps (Chromium guesses X11, `trusted_networks` must be
  the first auth provider, the V4L2 flags that look like a fix and are not)
- `docs/handoff-2026-09-10-wall-panel.md` — **pick the panel work up cold**: what
  was built, the stream-cost measurements, four things that were believed and
  measured wrong, and what still needs a person (Wi-Fi power save, Ethernet, the
  fan that has never been needed)
- `docs/matter-bridge.md` — Matter bridge design and deployment (our devices → Apple Home)
- `docs/matter-bridge-runbook.md` — **build and commission the bridge from scratch**: ordered steps, the values that prove it is conformant, and the twelve traps
- `docs/matter-controller.md` — Matter controller setup (third-party Matter devices → dashboard)
- `docs/restore-runbook.md` — **rebuild the stack from backup**: ordered steps, expected verification counts, and the traps (container DNS, lost Tuya camera patch, docker disabled at boot, the watchdog)
- `docs/handoff-2026-09-03-recovery.md` — the 2026-09-02 reset incident: what was ruled out, the watchdog finding, and what the rebuild turned up
- `docs/local-ai.md` — the LLM and NPU stack: services, build flags, NPU op support, benchmarks
- `docs/npu-model-pipeline.md` — **rebuild the NPU detection model**: the PReLU swap, the
  exact decomposition, INT8 quantisation, and scoring (`scripts/npu-model/`)
- `docs/handoff-2026-09-08-local-ai.md` — **pick the AI work up cold**: what runs,
  the NPU blocker and what it rules out, where the artefacts are, what to try next
- `docs/voice-assistant-proposal.md` — **adding voice**: why the pipeline goes on
  the board and the microphone does not go on the panel, the ESP32-S3-Touch-LCD-4B
  that is already owned, and the four traps (no add-ons in this HA install, the
  panel's browser cannot open a mic over HTTP, the LLM must stay out of the voice
  path, and audio is the next thing the Wi-Fi will break)
- `docs/handoff-2026-09-14-panel-display.md` — **pick the panel screen up cold**:
  the dark-screen bring-up, every verified pin and init step from Waveshare's
  demo, what ESPHome's `mipi_rgb` does differently, the next tests in order, and
  the approved GUI design and decisions
- `docs/handoff-2026-09-18-dashboard-and-learning.md` — **pick the dashboard up
  cold**: every view as it now is, the house memory and nightly learning, CO2,
  the IR hubs and Movie mode, the Voice Panel remote, open items, and the traps
  (a CSS brace, a deploy racing its restart, container queries on old Safari,
  the sidebar's `aside` rule)
- `docs/handoff-2026-09-19-cast-lighting-energy.md` — **pick up this session
  cold**: cast to the TV and its Voice Panel remote, the family room lights and
  automations, All lights following Manage, the IR remotes page, the Energy card
  and view (sample data), Discovery as apps, and what lives only on the board
- `docs/handoff-2026-09-13-voice-satellite.md` — **pick the voice work up cold**:
  what is built and measured, the one open fault (the wake word never runs), the
  evidence that pins it, the next test, and thirteen traps from getting audio
  working on a board whose microphone and speaker share one I2S bus
- `docs/energy-monitoring.md` — **electricity, gas and forecasting**: the PowerLync read
  locally over HomeKit and how to connect it, why the FortisBC gas meter cannot
  be read from the house and the three ways that could work, and the plan for
  the nightly forecast (seasonal median, LightGBM, Chronos-2, picked by a
  backtest, `~/forecast-venv`), and the rest of the energy "AI mode" plan
- `docs/dashboard-cast.md` — **Cast to TV**: the dashboard as live video on the
  LLANO-S450 dongle over DLNA, switched in Settings and off by default (off costs
  nothing); `switch.tv_cast` in Home Assistant and the Voice Panel's TV cast
  remote; what the dongle cannot do, and why Chromium hangs in a user unit
- `docs/house-modes.md` — **Away / Home again / Vacation and night arming**
  (`scripts/install-house-modes.py`, `input_select.house_mode`): the modes, the
  owner's choices, and what the iPhone needs (location *Always*, Tailscale) for them to fire
- `docs/door-alerts.md` — **front door left open**: when it fires (A: last phone leaves,
  B: open 10 min and the house still), the shared dashboard banner, iPhone push, and
  Telegram setup (`scripts/install-door-alerts.py`, `input_boolean.front_door_alert`)
- `docs/night-watch.md` — **night clips and Telegram photos**: triggers and cameras,
  retention, the office camera's false "person" and the motion gate
- `docs/safety-alerts.md` — **water leak and smoke**: the six sensors, the critical
  push / Telegram / red banner, why a Tuya flap does not re-alert but `unknown -> on`
  does, and the daily battery and not-reporting check (`scripts/install-safety-alerts.py`)
- `docs/tailscale.md` — remote access over Tailscale (`scripts/install-tailscale.sh`);
  `--accept-dns=false` is required, because Docker copies the hand-written `/etc/resolv.conf`
- `docs/architecture.md` — architecture notes
- `docs/superpowers/` — dated plans and specs; historical records, do not retrofit

## Git Remote

`git@github.com:JackGukf/smart_home.git` — branch `main`
