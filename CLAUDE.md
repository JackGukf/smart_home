# Smart Home Raspberry Pi 4 — Claude Code Context

## Project Overview

Smart home controller for a Raspberry Pi 4 targeting TP-Link/Kasa switches, Tuya sensors, cameras, and a web dashboard. Dual-language: Python for fast automation and C/C++ for long-running services.

## Repository Layout

```
src/python/          Python source modules (web_app.py, tplink_switch.py, controller.py)
src/cpp/             C/C++ source and CMakeLists.txt
tests/python/        pytest test suite
scripts/             Utility and one-off scripts
configs/             Device config files (never commit devices.local.yaml)
cmake/toolchains/    Cross-compile toolchain for RPi4 aarch64
build/               CMake out-of-tree build dirs (docker-debug, rpi4-release, dev-check)
docs/                Architecture notes and setup guides
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
docker compose run --rm dev ./scripts/dev-check.sh /workspace/smart-home-rpi4

# Run Python tests in Docker
docker compose run --rm dev python3 -m pytest

# Build and test C++ in Docker
docker compose run --rm dev sh -lc \
  "cmake --preset docker-debug && cmake --build --preset docker-debug && \
   ctest --test-dir build/docker-debug --output-on-failure"
```

### RPi4 cross-compile and deploy
```bash
./scripts/build-rpi4.sh
./scripts/deploy-to-pi.sh
./scripts/connect-pi.sh [--check]
```

## Python Environment

- Python 3, `pyproject.toml` sets `pythonpath = ["."]` so imports use `src.python.*`
- Dependencies listed in `src/python/requirements.txt`; key ones: `python-kasa`, `tinytuya`, `fastapi`, `uvicorn`, `PyYAML`, `pytest`
- Install locally: `pip install -r src/python/requirements.txt`

## C++ / CMake

- Root `CMakeLists.txt` delegates to `src/cpp/CMakeLists.txt`
- Presets defined in `CMakePresets.json`: `docker-debug`, `rpi4-release`, `dev-check`
- Cross-compile toolchain: `cmake/toolchains/rpi4-aarch64.cmake`

## Architecture Conventions

- One module per vendor integration (`tplink`, `tuya`, `camera`, `automation`)
- Vendor integrations sit behind clear interfaces — keep them isolated
- Prefer local-network control over cloud where possible
- Long-running services → C/C++ daemon; scripts and API calls → Python

## Secrets / Credentials

- **Never commit** passwords, API keys, camera credentials, or Wi-Fi details
- Real device config goes in `configs/devices.local.yaml` (git-ignored)
- See `configs/devices.example.yaml` for the schema
- Runtime secrets passed via environment variables (e.g. `TUYA_ACCESS_ID`, `HOME_ASSISTANT_TOKEN`, `ECOBEE_ACCESS_TOKEN`)

## Testing Notes

- Test files live in `tests/python/`
- Tests are importable without installing; `pythonpath = ["."]` in `pyproject.toml` handles this
- Use `pytest-asyncio` for async tests (`tplink_switch` controller is async)

## Git Remote

`git@github.com:JackGukf/smart_home.git` — branch `main`
