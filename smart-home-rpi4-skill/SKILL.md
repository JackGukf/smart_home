---
name: smart-home-rpi4
description: >
  Expert context for the smart-home-rpi4 project — a Raspberry Pi 4 smart home
  controller using Python (TP-Link/Kasa, Tuya, FastAPI dashboard) and C++
  (long-running daemon). Use this skill whenever the user is working on or asking
  about their smart-home-rpi4 project, including writing code, running tests,
  building, deploying to the Pi, controlling devices, or debugging. Trigger on any
  mention of: smart home, RPi4, Kasa, TP-Link, Tuya, the web dashboard, deploy to
  Pi, smart_home_controller, tplink_switch, web_app, or the smart-home-rpi4 workspace.
---

# Smart Home RPi4 — Project Superpower

## Key Paths

| Context | Path |
|---------|------|
| WSL (preferred for all dev work) | `/home/jackgu/workspace/smart-home-rpi4` |
| Windows (Cowork file tools) | `\\wsl.localhost\Ubuntu-22.04\home\jackgu\workspace\smart-home-rpi4` |
| Git remote | `git@github.com:JackGukf/smart_home.git` (SSH — already configured) |
| Raspberry Pi | `smarthome@192.168.0.176` (default) |

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
cmake/toolchains/    rpi4-aarch64.cmake cross-compile toolchain
build/               CMake out-of-tree dirs: docker-debug, rpi4-release, dev-check
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

Run all of these from the project root in WSL (`~/workspace/smart-home-rpi4`):

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
docker compose run --rm dev ./scripts/dev-check.sh /workspace/smart-home-rpi4

# Build C++ in Docker (debug)
docker compose run --rm dev sh -lc \
  "cmake --preset docker-debug && cmake --build --preset docker-debug && \
   ctest --test-dir build/docker-debug --output-on-failure"

# Run Python tests inside Docker
docker compose run --rm dev python3 -m pytest
```

CMake presets: `docker-debug`, `rpi4-release`, `dev-check`

---

## Build & Deploy to Raspberry Pi

```bash
# Cross-compile for RPi4 aarch64 (runs inside Docker automatically)
./scripts/build-rpi4.sh
# Output: build/rpi4-release/src/cpp/smart_home_controller

# Deploy C++ binary + Python source + configs to Pi
./scripts/deploy-to-pi.sh
# Options:
#   --host HOST        Override Pi IP (default: 192.168.0.176)
#   --user USER        Override SSH user (default: smarthome)
#   --skip-build       Skip build-rpi4.sh (use existing binary)

# Check Pi connectivity
./scripts/connect-pi.sh --check

# SSH into Pi
./scripts/connect-pi.sh

# Run a command on Pi
./scripts/connect-pi.sh -- uname -a
```

**What deploy does:** rsync's the binary, Python source, and configs; sets up a venv; installs Python dependencies.

**Run on Pi after deploy:**
```bash
# C++ daemon
/home/smarthome/smart-home-rpi4/bin/smart_home_controller

# Python controller
/home/smarthome/smart-home-rpi4/.venv/bin/python /home/smarthome/smart-home-rpi4/src/python/controller.py

# Web dashboard
cd /home/smarthome/smart-home-rpi4 && .venv/bin/python -m uvicorn src.python.web_app:app --host 0.0.0.0 --port 8000
```

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
cd ~/workspace/smart-home-rpi4
python3 -m pytest                  # make sure tests pass
./scripts/deploy-to-pi.sh          # cross-compile + rsync + venv setup
./scripts/connect-pi.sh --check    # verify Pi is reachable
```
