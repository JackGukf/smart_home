# Smart Home AI (Orange Pi 6 Plus) — Claude Code Context

> **⚠️ ACTIVE INCIDENT (2026-09-03): the board is bare and nothing is running.**
> It was re-flashed to SD after repeated resets traced to the NVMe. The stack —
> Home Assistant, Zigbee2MQTT, dashboard, go2rtc — is **not installed** on the
> current system, and the SSH host key has changed. A verified backup exists.
> **Read `docs/handoff-2026-09-03-recovery.md` before touching the board.**

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

`deploy-dashboard.sh` increments `BUILD_COUNT`, rewrites static cache-busting versions and `web_static/build_info.json`. It mutates the source tree; review the resulting diff.

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
| `ollama.service` (system) | `127.0.0.1:11434` | Qwen3-4B Q4_K_M, Ollama API. Unloads when idle. |
| `llama-server.service` (user) | `127.0.0.1:8081` | Qwen3-4B Q4_0, OpenAI API. ~3x faster prompts, holds 5GB always. |
| `npu-detector.service` (user) | → MQTT `smarthome/vision/<camera>` | YOLOv8n on the Zhouyi NPU |

Reach the LLMs with an SSH tunnel, not by widening the bind address:

```bash
ssh -N -L 11434:127.0.0.1:11434 orangepi@192.168.0.234
```

Treat model output as untrusted input: validate schema, enforce an allow-list, and keep device control deterministic. Never put the model in a trigger path — it is slower and less reliable than the rule it would replace. The useful shape is *LLM authors, rules execute*.

Three things that will waste a day if you do not know them:

- **`-mcpu=native` silently produces a baseline binary.** GCC 13 cannot identify this A720+A520 CPU and emits zero ARM feature macros. Always pass `-DGGML_CPU_ARM_ARCH=armv9-a+i8mm+dotprod+sve+bf16`. Worth 3x on prompt processing.
- **The A720 cores are interleaved**: `0,1,6,7,8,9,10,11`. CIX's documented taskset list is wrong for this board and costs 31% of generation throughput.
- **On the NPU, a model that runs is not proof it ran on the NPU.** Unsupported ops fall back to CPU silently — set `session.disable_cpu_ep_fallback` or you are measuring the CPU. SiLU crashes the execution provider outright, which is why stock YOLOv8 cannot run.

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
- `docs/matter-bridge.md` — Matter bridge design and deployment (our devices → Apple Home)
- `docs/matter-controller.md` — Matter controller setup (third-party Matter devices → dashboard)
- `docs/handoff-2026-09-03-recovery.md` — **current incident**: NVMe resets, what was ruled out, the backup, and the recovery plan
- `docs/local-ai.md` — the LLM and NPU stack: services, build flags, NPU op support, benchmarks
- `docs/architecture.md` — architecture notes
- `docs/superpowers/` — dated plans and specs; historical records, do not retrofit

## Git Remote

`git@github.com:JackGukf/smart_home.git` — branch `main`
