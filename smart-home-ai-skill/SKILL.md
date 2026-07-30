---
name: smart-home-ai
description: >
  Expert context for the smart_home_AI project — an Orange Pi 6 Plus smart home
  controller using Python (TP-Link/Kasa, Tuya, FastAPI dashboard) and C++
  (long-running daemon, Matter bridge). Use this skill whenever the user is working
  on or asking about their smart_home_AI project, including writing code, running
  tests, building, deploying to the board, controlling devices, or debugging.
  Trigger on any mention of: smart home, Orange Pi, RPi4, Kasa, TP-Link, Tuya, the
  web dashboard, deploy to Pi, smart_home_controller, tplink_switch, web_app, or
  the smart_home_AI workspace (formerly smart-home-rpi4).
---

# Smart Home AI (Orange Pi 6 Plus) — Project Superpower

## Key Paths

| Context | Path |
|---------|------|
| WSL (preferred for all dev work) | `/home/jackgu/workspace/smart_home_AI` |
| Windows (Cowork file tools) | `\\wsl.localhost\Ubuntu-22.04\home\jackgu\workspace\smart_home_AI` |
| Git remote | `git@github.com:JackGukf/smart_home.git` (SSH — already configured) |
| Orange Pi 6 Plus (primary) | `orangepi@192.168.0.234`, path `/home/orangepi/smart_home_AI` |
| Raspberry Pi 4 (secondary) | `smarthome@192.168.0.176`, path `/home/smarthome/smart-home-rpi4` |

> **Important for Cowork/sandbox:** The bash sandbox cannot mount the WSL workspace
> path. Always provide commands for the user to run in their **Ubuntu WSL terminal**
> rather than trying to execute them in the sandbox.

---

## Repository Layout

```
src/python/          Python modules
  web_app.py           FastAPI dashboard (uvicorn)
  tplink_switch.py     KasaLightSwitchController + CLI
  controller.py        Main controller entry point
src/cpp/             C/C++ daemon source + CMakeLists.txt
tests/python/        pytest test suite
scripts/             Utility scripts (build, deploy, connect, discover)
configs/             Device configs
  devices.example.yaml   Schema reference (committed)
  devices.local.yaml     Real devices (git-ignored — never commit)
cmake/toolchains/    orangepi6-aarch64.cmake (primary), rpi4-aarch64.cmake (secondary)
build/               CMake out-of-tree dirs: docker-debug, orangepi6-release, dev-check
docs/                Architecture notes, WSL setup, setup guides
```

---

## Architecture Conventions

- **One module per vendor**: `tplink`, `tuya`, `camera`, `automation` — keep them isolated behind clear interfaces
- **Prefer local-network control** over cloud where possible
- **Python** for: discovery, scheduled scripts, API calls, web dashboard
- **C/C++** for: long-running services, GPIO, performance-sensitive event handling
- **Event flow**: `sensor/schedule event → automation rule → device adapter command → status logging`
- **Python imports**: always use `src.python.*` (e.g. `from src.python.tplink_switch import ...`). `pyproject.toml` sets `pythonpath = ["."]`

---

## Python Commands

Run all of these from the project root in WSL (`~/workspace/smart_home_AI`):

```bash
# Run tests
python3 -m pytest

# Start web dashboard locally
python3 -m uvicorn src.python.web_app:app --host 0.0.0.0 --port 8000

# Discover TP-Link/Kasa switches on the LAN
python3 scripts/discover_tplink_switches.py

# Control a switch by IP
python3 -m src.python.tplink_switch --host <IP> status|on|off|toggle

# Control a switch by name (from devices.local.yaml)
python3 -m src.python.tplink_switch --name <switch-name> status|on|off|toggle
```

---

## C++ / CMake Commands (Docker preferred)

```bash
# Build and start the dev container
docker compose build dev

# Run dev checks (lint, build, test) inside Docker
docker compose run --rm dev ./scripts/dev-check.sh /workspace/smart_home_AI

# Build C++ in Docker (debug)
docker compose run --rm dev sh -lc \
  "cmake --preset docker-debug && cmake --build --preset docker-debug && \
   ctest --test-dir build/docker-debug --output-on-failure"

# Run Python tests inside Docker
docker compose run --rm dev python3 -m pytest
```

CMake presets: `docker-debug`, `docker-orangepi6-release`, `docker-rpi4-release`, `dev-check`

---

## Build & Deploy to the Orange Pi 6 Plus

```bash
# Cross-compile for aarch64 (runs inside Docker automatically)
./scripts/build-orangepi6.sh
# Output: build/orangepi6-release/src/cpp/smart_home_controller

# Deploy C++ binary + Python source + configs to the board
./scripts/deploy-to-pi.sh
# Options:
#   --host HOST        Override board IP (default: 192.168.0.234)
#   --user USER        Override SSH user (default: orangepi)
#   --remote-path PATH Override install dir (default: /home/$USER/smart_home_AI)
#   --board BOARD      orangepi6 (default) or rpi4
#   --skip-build       Skip the build (use existing binary)

# Deploy the dashboard + systemd user services
./scripts/deploy-dashboard.sh

# Check connectivity
./scripts/connect-pi.sh --check

# SSH in
./scripts/connect-pi.sh

# Run a command on the board
./scripts/connect-pi.sh -- uname -a
```

The Raspberry Pi 4 is still supported as a secondary target, but never by
default — pass every detail explicitly:

```bash
./scripts/build-orangepi6.sh --board rpi4
./scripts/deploy-to-pi.sh --board rpi4 --host 192.168.0.176 --user smarthome \
    --remote-path /home/smarthome/smart-home-rpi4
```

**What deploy does:** rsync's the binary, Python source, and configs; sets up a venv; installs Python dependencies.

**Run on the board after deploy:**
```bash
# C++ daemon
/home/orangepi/smart_home_AI/bin/smart_home_controller

# Python controller
/home/orangepi/smart_home_AI/.venv/bin/python /home/orangepi/smart_home_AI/src/python/controller.py

# Web dashboard
cd /home/orangepi/smart_home_AI && .venv/bin/python -m uvicorn src.python.web_app:app --host 0.0.0.0 --port 8000
```

**Board gotcha:** Ubuntu uses predictable interface names (`wlp1s0` Wi-Fi,
`enp97s0` Ethernet), not Raspberry Pi OS's `wlan0`/`eth0`. Anything passing
`--interface` — notably the Matter bridge — must use the Ubuntu names.

---

## Device Configuration

Config schema: `configs/devices.example.yaml`
Real config: `configs/devices.local.yaml` (git-ignored — **never commit**)

### TP-Link / Kasa
- `KasaLightSwitchController` in `src/python/tplink_switch.py`
- Async interface: `status()`, `turn_on()`, `turn_off()`, `toggle()`
- Load switches from config: `load_switches_from_config(Path("configs/devices.local.yaml"))`
- Newer Kasa devices need cloud credentials: `TPLINK_USERNAME` / `TPLINK_PASSWORD` env vars (or per-device in config)

### Tuya
- Env vars: `TUYA_ACCESS_ID`, plus any Tuya-specific tokens
- Module: `src/python/tuya.py` (when created, follows same isolation pattern as tplink)

### Other integrations
- Home Assistant token: `HOME_ASSISTANT_TOKEN`
- Ecobee: `ECOBEE_ACCESS_TOKEN`

---

## Secrets Policy

**Never commit** to git:
- `configs/devices.local.yaml`
- API keys, passwords, Wi-Fi credentials, camera credentials

Pass secrets via environment variables at runtime.

---

## Testing Notes

- Tests live in `tests/python/`; run with `python3 -m pytest` from project root
- `pytest-asyncio` handles async tests (tplink controller is async)
- No install needed: `pythonpath = ["."]` in `pyproject.toml`
- When writing new tests, mirror the async patterns in existing tplink tests

---

## Common Workflows

### Add a new device integration
1. Create `src/python/<vendor>.py` with a clean interface class
2. Add config schema to `configs/devices.example.yaml`
3. Add tests in `tests/python/test_<vendor>.py`
4. Update `src/python/controller.py` to wire it in

### Debug a switch that's not responding
```bash
# First, check it's discoverable on the LAN
python3 scripts/discover_tplink_switches.py

# Then test direct control
python3 -m src.python.tplink_switch --host <IP> status
```

### Full deploy workflow
```bash
cd ~/workspace/smart_home_AI
python3 -m pytest                  # make sure tests pass
./scripts/deploy-to-pi.sh          # cross-compile + rsync + venv setup
./scripts/connect-pi.sh --check    # verify the board is reachable
```
