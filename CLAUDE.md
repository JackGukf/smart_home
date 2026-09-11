# Smart Home AI (Orange Pi 6 Plus) — Claude Code Context

> **Recovered 2026-09-03. The stack is running again**, booted from the NVMe in
> the PCIe slot: dashboard, go2rtc, Home Assistant, Zigbee (5 devices), Matter
> controller, resource-logger — all enabled and surviving a reboot.
>
> **Local AI, staged** — Ollama is live and alone; **run one LLM, not both**,
> there is no swap. The NPU detector is **blocked**: the model was retrained and
> the graph runs on the device at full speed but computes the wrong answer, and
> `disable_cpu_ep_fallback` proves only *where* a graph ran, not *what* it
> computed. Start here: **`docs/handoff-2026-09-08-local-ai.md`**.
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
> **Never set `RuntimeWatchdogSec` on this board.** Its SBSA watchdog has a fixed
> 10 s timeout that cannot be raised, so a 60 s setting resets the board every
> ~80 s with no kernel panic. That is the prime suspect for the 2026-09-02 reset
> loop. The default password is also still `orangepi`.

## Project Overview

Smart home controller for an **Orange Pi 6 Plus** targeting TP-Link/Kasa switches, Tuya sensors, Govee/Lepro ambient devices, cameras, Home Assistant entities, a Matter bridge, and a web dashboard. Dual-language: Python for fast automation and C/C++ for long-running services.

The workspace was migrated from `smart-home-rpi4` to `smart_home_AI` on 2026-07-29 with Git history intact, and the deployment target moved from the Raspberry Pi 4 to the Orange Pi 6 Plus. Read `PROJECT_CONTEXT.md` for the full handoff.

## Target Hardware

The Orange Pi 6 Plus is the **primary** target. The Raspberry Pi 4 is kept as a **secondary** target so the existing remote install keeps working — it is never the default; select it explicitly.

| | Orange Pi 6 Plus (primary) | Raspberry Pi 4 (secondary) |
| --- | --- | --- |
| OS | Ubuntu 24.04 ARM64 | Raspberry Pi OS 64-bit |
| CPU | Cix P1 / CD8180, 12 cores, Armv9.2-A (Cortex-A720 + A520) | Cortex-A72, Armv8-A |
| SSH | `orangepi@192.168.0.234` | `smarthome@192.168.0.176` |
| Remote path | `/home/orangepi/smart_home_AI` | `/home/smarthome/smart-home-rpi4` |
| Net interfaces | `wlp1s0` (Wi-Fi), `enp97s0` (Ethernet) | `wlan0`, `eth0` |
| CMake preset | `docker-orangepi6-release` | `docker-rpi4-release` |
| Toolchain | `cmake/toolchains/orangepi6-aarch64.cmake` | `cmake/toolchains/rpi4-aarch64.cmake` |
| Build dir | `build/orangepi6-release/` | `build/rpi4-release/` |

Since 2026-09-10 the Raspberry Pi 4 is **also the wall panel**: it displays the
dashboard full screen from boot and logs itself into both the dashboard and Home
Assistant by IP address. That makes `192.168.0.176` a credential — see
`docs/kiosk-display.md` before changing it, and before deploying to that host.

Gotchas that have bitten this project:

- **Interface names differ.** Ubuntu uses predictable names, so anything passing `--interface` (notably the Matter bridge in `configs/matter-bridge.service`) must use `wlp1s0`/`enp97s0`, not `wlan0`. A wrong interface makes Matter commissioning fail quietly.
- **`-mcpu=cortex-a720` is unavailable.** It needs GCC 14+; the dev container ships the Ubuntu 22.04 aarch64 cross-compiler (GCC 11). The Orange Pi toolchain probes for the best `-march` the compiler accepts and falls back to a safe baseline. Override with `-DORANGEPI6_ARCH_FLAGS=...`.
- Both boards are `aarch64`, so a generic arm64 binary (e.g. the Matter bridge from the GN build) runs on either.
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
./scripts/deploy-dashboard.sh         # dashboard + systemd user services
./scripts/connect-pi.sh [--check]
./scripts/backup-smart-home.sh        # Zigbee key, HA config, .env -> ~/orangepi-recovery
```

Deploy scripts default to `orangepi@192.168.0.234` and `/home/orangepi/smart_home_AI`. Override with `--host`/`--user`/`--remote-path` (or `PI_HOST`/`PI_USER`/`REMOTE_PATH`) — always confirm the target before deploying, and never assume a default points at the board you mean.

### Wall panel (Raspberry Pi 4)
```bash
./scripts/setup-kiosk-display.sh                              # panel: chromium, autostart, no blanking
./scripts/enable-kiosk-autologin.py --kiosk-ip 192.168.0.176  # board: both logins, by address
./scripts/enable-kiosk-autologin.py --kiosk-ip 192.168.0.176 --dry-run
```

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
| `npu-detector.service` (user) | → MQTT `smarthome/vision/<camera>` | YOLOv8n on the Zhouyi NPU. **Live since 2026-09-09** — mAP50 0.363, person AP50 0.633, 32.4 fps. The detection head is cut off the graph and decoded in numpy; quantising it erases what it computes. Publishes *presence*, not frames: `NPU_PRESENCE_HOLD` (60 s) delays only the falling edge, never a rise. See `docs/npu-model-pipeline.md`. |
| `llama-server.service` (user) | `127.0.0.1:8081` | Qwen3-4B Q4_0, OpenAI API. ~3x faster prompts, holds 5GB always. **Deferred** — do not run it beside Ollama. |

Reach the LLMs with an SSH tunnel, not by widening the bind address:

```bash
ssh -N -L 11434:127.0.0.1:11434 orangepi@192.168.0.234
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

- `docs/setup-orangepi6.md` — verified board facts and first-time setup
- `docs/orangepi6-cross-compile-deploy.md` — build and deploy workflow (both boards)
- `docs/docker-development.md`, `docs/WSL_DEVELOPMENT.md` — dev environment
- `docs/kiosk-display.md` — **the Raspberry Pi 4 as a wall panel**: full-screen
  dashboard on boot, both logins bypassed by address, and the traps (Chromium
  guesses X11, `trusted_networks` must be the first auth provider)
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
- `docs/architecture.md` — architecture notes
- `docs/superpowers/` — dated plans and specs; historical records, do not retrofit

## Git Remote

`git@github.com:JackGukf/smart_home.git` — branch `main`
