# Matter Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a C++ Matter bridge daemon that exposes all dashboard devices (TP-Link switches, Tuya sensors, scenes, virtual switches) as native Matter endpoints in Apple Home, communicating with the Python dashboard over a local HTTP sync API.

**Architecture:** The C++ bridge (built on CHIP SDK `connectedhomeip`) registers as a Matter Bridge and creates dynamic Matter endpoints for every dashboard device. A new `bridge_sync.py` FastAPI router gives the bridge local HTTP access to query devices (`GET /bridge/devices`), send commands (`POST /bridge/command`), and poll state (`GET /bridge/state/all`). Both services use `network_mode: host`, so `localhost:8000/bridge/*` is shared.

**Tech Stack:** C++17, connectedhomeip v1.3.0.0, GN+Ninja (SDK's native build system), libcurl, nlohmann/json (bundled in CHIP SDK), Python 3.11 / FastAPI, Docker aarch64 cross-compile

## Global Constraints

- Target platform: Raspberry Pi 4, aarch64 (arm64) Linux
- Cross-compile toolchain: `aarch64-linux-gnu-g++` (already in `Dockerfile`)
- CHIP SDK: git submodule at `third_party/connectedhomeip`, pinned to tag `v1.3.0.0`
- Bridge sync API: FastAPI router mounted at `/bridge` prefix on main web app (port 8000); `localhost` only, no authentication
- Bridge sync API base URL used by C++ bridge: `http://localhost:8000`
- TP-Link switch device_id format: `kasa:{switch.host}` (e.g. `kasa:192.168.1.10`)
- Tuya device_id format: the raw `device_id` field from `devices.local.yaml`
- Matter commissioning storage: `/data/bridge/` inside `matter-data` Docker volume
- C++ standard: C++17 (`-std=c++17`)
- Python: 3.11+
- Never commit credentials; bridge sync API returns no secret data
- CHIP SDK first-time bootstrap takes 30–60 minutes and downloads ~2 GB; run inside Docker

---

## File Map

```
# New files
third_party/connectedhomeip/             git submodule (CHIP SDK v1.3.0.0)
src/python/bridge_sync.py                FastAPI router, /bridge prefix
tests/python/test_bridge_sync.py         pytest tests for bridge sync API
src/cpp/matter_bridge/
  DeviceMapper.h / DeviceMapper.cpp      category string → MatterDeviceType enum
  SyncClient.h / SyncClient.cpp          libcurl HTTP client for /bridge endpoints
  BridgeDevice.h / BridgeDevice.cpp      CHIP SDK dynamic endpoint wrapper
  main.cpp                               bridge init, event loop, poll thread
scripts/setup-matter-sdk.sh              one-time CHIP SDK bootstrap (runs in Docker)
scripts/build-matter-bridge.sh           cross-compile bridge binary (runs in Docker)
scripts/deploy-matter-bridge.sh          rsync binary to Pi
Dockerfile.matter-bridge                 Pi runtime image (copies pre-built binary)

# Modified files
Dockerfile                               add CHIP SDK system deps + libcurl-dev
docker-compose.pi.yml                    add matter-bridge service
src/python/web_app.py                    include bridge_sync router, add helper fns
```

---

### Task 1: CHIP SDK submodule + Docker build environment

**Files:**
- Create: `.gitmodules` (add submodule entry)
- Modify: `Dockerfile` (add CHIP SDK system deps + libcurl)
- Create: `scripts/setup-matter-sdk.sh`
- Create: `scripts/build-matter-bridge.sh`

**Interfaces:**
- Produces: `build/matter-bridge/chip-bridge-app` — stripped aarch64 binary (~8–20 MB)

- [ ] **Step 1: Add CHIP SDK as git submodule**

```bash
git submodule add https://github.com/project-chip/connectedhomeip.git third_party/connectedhomeip
cd third_party/connectedhomeip
git checkout v1.3.0.0
cd ../..
git add .gitmodules third_party/connectedhomeip
git commit -m "chore: add connectedhomeip v1.3.0.0 submodule"
```

- [ ] **Step 2: Add CHIP SDK system deps to Dockerfile**

In `Dockerfile`, add these packages to the existing `apt-get install` block (add after `ninja-build`):

```dockerfile
        libssl-dev \
        libdbus-1-dev \
        libglib2.0-dev \
        libavahi-client-dev \
        libreadline-dev \
        libgirepository1.0-dev \
        libcairo2-dev \
        unzip \
        libcurl4-openssl-dev \
        libcurl4-openssl-dev:arm64 \
```

> **Note:** `libcurl4-openssl-dev:arm64` requires enabling the arm64 architecture in Docker. If the build fails for the arm64 package, install `gcc-aarch64-linux-gnu libcurl4-openssl-dev` and cross-link manually in the build script instead. The simplest fallback: build curl into the binary statically, or install `libcurl4` on the Pi and link dynamically.

- [ ] **Step 3: Rebuild dev container to verify deps**

```bash
docker compose build dev
```

Expected: build succeeds, no apt errors.

- [ ] **Step 4: Create `scripts/setup-matter-sdk.sh`**

This one-time script bootstraps the CHIP SDK inside the Docker dev container. Run it once; it downloads pigweed and additional tools (~1–2 GB). It does NOT need to run on every build.

```bash
#!/usr/bin/env bash
# Run this ONCE inside the Docker dev container to bootstrap the CHIP SDK.
# Takes 30-60 minutes on first run.
# Usage: docker compose run --rm dev bash scripts/setup-matter-sdk.sh
set -e

CHIP_DIR="$(git rev-parse --show-toplevel)/third_party/connectedhomeip"

echo "==> Initialising CHIP SDK submodules (this downloads ~500 MB)..."
cd "$CHIP_DIR"
git submodule update --init --depth 1 \
  third_party/pigweed/repo \
  third_party/nlohmann_json \
  third_party/jsoncpp/repo \
  third_party/mbedtls/repo \
  third_party/boringssl \
  third_party/ot-br-posix \
  third_party/openthread/ot-core

echo "==> Bootstrapping pigweed toolchain (downloads clang, gn, etc.)..."
bash scripts/bootstrap.sh

echo "==> Done. Activate with: source scripts/activate.sh"
```

Make it executable:
```bash
chmod +x scripts/setup-matter-sdk.sh
git add scripts/setup-matter-sdk.sh
git commit -m "chore: add CHIP SDK bootstrap script"
```

- [ ] **Step 5: Create `scripts/build-matter-bridge.sh`**

This script copies our bridge source files into the CHIP SDK bridge-app example, patches its `BUILD.gn` to include them, then builds for aarch64.

```bash
#!/usr/bin/env bash
# Cross-compile the Matter bridge for Raspberry Pi 4 (aarch64).
# Must run inside the Docker dev container after setup-matter-sdk.sh.
# Usage: docker compose run --rm dev bash scripts/build-matter-bridge.sh
set -e

PROJECT_ROOT="$(git rev-parse --show-toplevel)"
CHIP_DIR="$PROJECT_ROOT/third_party/connectedhomeip"
BRIDGE_SRC="$PROJECT_ROOT/src/cpp/matter_bridge"
CHIP_BRIDGE_DIR="$CHIP_DIR/examples/bridge-app/linux"
OUT_DIR="$PROJECT_ROOT/build/matter-bridge"

echo "==> Activating CHIP SDK tools..."
# shellcheck source=/dev/null
source "$CHIP_DIR/scripts/activate.sh"

echo "==> Copying bridge source files into CHIP SDK bridge example..."
cp "$BRIDGE_SRC/BridgeDevice.h"   "$CHIP_BRIDGE_DIR/"
cp "$BRIDGE_SRC/BridgeDevice.cpp" "$CHIP_BRIDGE_DIR/"
cp "$BRIDGE_SRC/DeviceMapper.h"   "$CHIP_BRIDGE_DIR/"
cp "$BRIDGE_SRC/DeviceMapper.cpp" "$CHIP_BRIDGE_DIR/"
cp "$BRIDGE_SRC/SyncClient.h"     "$CHIP_BRIDGE_DIR/"
cp "$BRIDGE_SRC/SyncClient.cpp"   "$CHIP_BRIDGE_DIR/"
cp "$BRIDGE_SRC/main.cpp"         "$CHIP_BRIDGE_DIR/"

echo "==> Patching bridge-app BUILD.gn to include custom sources + libcurl..."
# Adds our .cpp files to the sources list and curl to the libs list.
# Uses sed to insert after the first "sources = [" line.
BUILD_GN="$CHIP_BRIDGE_DIR/BUILD.gn"
if ! grep -q "BridgeDevice.cpp" "$BUILD_GN"; then
  sed -i 's|sources = \[|sources = [\n    "BridgeDevice.cpp",\n    "DeviceMapper.cpp",\n    "SyncClient.cpp",|' "$BUILD_GN"
  sed -i '/^executable/a\  libs = [ "curl" ]' "$BUILD_GN"
fi

echo "==> Running GN build for linux-arm64..."
mkdir -p "$OUT_DIR"
"$CHIP_DIR/scripts/examples/gn_build_example.sh" \
  "$CHIP_BRIDGE_DIR" \
  "$OUT_DIR" \
  'target_cpu="arm64"' \
  'chip_mdns="platform"' \
  'chip_inet_config_enable_ipv4=true' \
  'is_debug=false'

echo "==> Stripping binary..."
aarch64-linux-gnu-strip "$OUT_DIR/chip-bridge-app"

echo "==> Done: $OUT_DIR/chip-bridge-app"
ls -lh "$OUT_DIR/chip-bridge-app"
```

```bash
chmod +x scripts/build-matter-bridge.sh
git add scripts/build-matter-bridge.sh
git commit -m "chore: add Matter bridge build script"
```

- [ ] **Step 6: Verify build script runs (without full build — syntax check only)**

```bash
docker compose run --rm dev bash -n scripts/build-matter-bridge.sh
```

Expected: no syntax errors reported.

---

### Task 2: Python Bridge Sync API

**Files:**
- Create: `src/python/bridge_sync.py`
- Create: `tests/python/test_bridge_sync.py`
- Modify: `src/python/web_app.py` (mount router + add two helper functions)

**Interfaces:**
- Produces:
  - `bridge_sync.router` — FastAPI APIRouter, prefix `/bridge`
  - `bridge_sync.register_handlers(get_devices_fn, execute_command_fn)` — called by web_app at startup to wire device-list and command callbacks without circular import
  - `bridge_sync.update_state_cache(device_id: str, state: dict)` — called by the dashboard's poll loop to keep the state cache current
- Consumes: nothing from earlier tasks

- [ ] **Step 1: Write failing tests**

Create `tests/python/test_bridge_sync.py`:

```python
"""Tests for the Bridge Sync API router."""
from __future__ import annotations
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.python.bridge_sync import router, register_handlers, update_state_cache, _state_cache


@pytest.fixture(autouse=True)
def clear_state():
    _state_cache.clear()
    yield
    _state_cache.clear()


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_state_all_empty(client):
    resp = client.get("/bridge/state/all")
    assert resp.status_code == 200
    assert resp.json() == {}


def test_update_state_cache_visible_in_state_all(client):
    update_state_cache("kasa:192.168.1.10", {"on": True})
    resp = client.get("/bridge/state/all")
    assert resp.status_code == 200
    assert resp.json() == {"kasa:192.168.1.10": {"on": True}}


def test_send_command_unknown_device_returns_404(client):
    async def fake_execute(device_id: str, command: str) -> None:
        raise KeyError(device_id)

    register_handlers(get_devices_fn=None, execute_command_fn=fake_execute)
    resp = client.post("/bridge/command", json={"device_id": "unknown", "command": "on"})
    assert resp.status_code == 404


def test_send_command_device_unreachable_returns_503(client):
    async def fake_execute(device_id: str, command: str) -> None:
        raise RuntimeError("timeout")

    register_handlers(get_devices_fn=None, execute_command_fn=fake_execute)
    resp = client.post("/bridge/command", json={"device_id": "kasa:x", "command": "on"})
    assert resp.status_code == 503


def test_list_devices_returns_bridge_device_list(client):
    async def fake_get() -> list:
        return [
            {
                "device_id": "kasa:192.168.1.10",
                "name": "Living Room",
                "room": "Living Room",
                "category": "light_switch",
                "dimmable": False,
                "state": {"on": False},
            }
        ]

    register_handlers(get_devices_fn=fake_get, execute_command_fn=None)
    resp = client.get("/bridge/devices")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["device_id"] == "kasa:192.168.1.10"
    assert data[0]["category"] == "light_switch"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/python/test_bridge_sync.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.python.bridge_sync'`

- [ ] **Step 3: Create `src/python/bridge_sync.py`**

```python
"""Bridge Sync API — internal FastAPI router for the C++ Matter bridge daemon.

Mounted at /bridge on the main web app (port 8000, localhost only).

Endpoints the C++ bridge calls:
  GET  /bridge/devices      — list all bridgeable devices with current state
  POST /bridge/command      — route a command from Apple Home to a real device
  GET  /bridge/state/all    — poll current state for all devices
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Awaitable
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bridge", tags=["bridge-sync"])

# ── Callbacks registered by web_app at startup ───────────────────────────────
# Using a registry avoids circular imports (bridge_sync ↔ web_app).

_get_devices_fn: Callable[[], Awaitable[list[dict[str, Any]]]] | None = None
_execute_command_fn: Callable[[str, str], Awaitable[None]] | None = None


def register_handlers(
    get_devices_fn: Callable[[], Awaitable[list[dict[str, Any]]]] | None,
    execute_command_fn: Callable[[str, str], Awaitable[None]] | None,
) -> None:
    """Called by web_app.create_app() to wire device-list and command callbacks."""
    global _get_devices_fn, _execute_command_fn
    _get_devices_fn = get_devices_fn
    _execute_command_fn = execute_command_fn


# ── In-memory state cache ─────────────────────────────────────────────────────
# Updated by the dashboard's poll loop via update_state_cache().
# Key: device_id  Value: latest state dict (e.g. {"on": True})

_state_cache: dict[str, dict[str, Any]] = {}


def update_state_cache(device_id: str, state: dict[str, Any]) -> None:
    """Called by the dashboard's poll loop whenever device state changes."""
    _state_cache[device_id] = state


# ── Pydantic models ───────────────────────────────────────────────────────────

class CommandBody(BaseModel):
    device_id: str
    command: str   # "on" | "off" | "toggle" | "brightness:N" (N = 0-100)


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/devices")
async def list_devices() -> list[dict[str, Any]]:
    """Return all bridgeable devices with their current state."""
    if _get_devices_fn is None:
        return []
    return await _get_devices_fn()


@router.get("/state/all")
async def all_states() -> dict[str, dict[str, Any]]:
    """Return the latest cached state for every device."""
    return dict(_state_cache)


@router.post("/command", status_code=200)
async def send_command(body: CommandBody) -> dict[str, str]:
    """Route an Apple Home command to the target device."""
    if _execute_command_fn is None:
        raise HTTPException(status_code=503, detail="Bridge not initialised")
    try:
        await _execute_command_fn(body.device_id, body.command)
        return {"status": "ok"}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown device: {body.device_id}")
    except Exception as exc:
        logger.error("Bridge command %s → %s failed: %s", body.command, body.device_id, exc)
        raise HTTPException(status_code=503, detail="Device unreachable")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/python/test_bridge_sync.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Mount bridge router in `web_app.py` and add helper functions**

Add the import near the top of `web_app.py` (after existing imports):

```python
from src.python import bridge_sync
```

Inside `create_app()`, after the line `app.mount("/static", ...)`, add:

```python
app.include_router(bridge_sync.router)
bridge_sync.register_handlers(
    get_devices_fn=_bridge_device_list,
    execute_command_fn=_bridge_execute_command,
)
```

Then add the two helper functions anywhere below `_device_cards()` (they are module-level async functions, not inside `create_app`):

```python
async def _bridge_device_list() -> list[dict]:
    """Return all bridgeable dashboard devices with current state for the C++ bridge."""
    devices: list[dict] = []
    cfg = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")) or {} if DEFAULT_CONFIG_PATH.exists() else {}

    # TP-Link switches
    controller = KasaLightSwitchController()
    for sw_cfg in (cfg.get("tplink") or {}).get("switches") or []:
        host = str(sw_cfg.get("host") or "")
        name = str(sw_cfg.get("name") or host)
        room = str(sw_cfg.get("room") or _room_from_name(name))
        device_id = f"kasa:{host}"
        on: bool | None = None
        try:
            sw = SwitchDefinition(name=name, host=host, model=str(sw_cfg.get("model") or ""))
            status = await controller.status(sw)
            on = status.is_on if status else None
        except Exception:  # noqa: BLE001
            pass
        bridge_sync.update_state_cache(device_id, {"on": bool(on)})
        devices.append({
            "device_id": device_id,
            "name": name,
            "room": room,
            "category": "light_switch",
            "dimmable": False,
            "state": {"on": bool(on)},
        })

    # Tuya devices
    for tuya_dev in _load_tuya_devices(DEFAULT_CONFIG_PATH):
        category = tuya_dev.category or "tuya_switch"
        bridge_sync.update_state_cache(tuya_dev.device_id, {"on": False})
        devices.append({
            "device_id": tuya_dev.device_id,
            "name": tuya_dev.name,
            "room": tuya_dev.room,
            "category": category,
            "dimmable": False,
            "state": {"on": False},
        })

    return devices


async def _bridge_execute_command(device_id: str, command: str) -> None:
    """Route a command from the C++ bridge to the appropriate device controller."""
    cfg = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")) or {} if DEFAULT_CONFIG_PATH.exists() else {}

    if device_id.startswith("kasa:"):
        host = device_id[len("kasa:"):]
        controller = KasaLightSwitchController()
        sw_cfgs = (cfg.get("tplink") or {}).get("switches") or []
        sw_cfg = next((s for s in sw_cfgs if str(s.get("host")) == host), None)
        if sw_cfg is None:
            raise KeyError(device_id)
        sw = SwitchDefinition(
            name=str(sw_cfg.get("name") or host),
            host=host,
            model=str(sw_cfg.get("model") or ""),
        )
        if command == "on":
            await controller.turn_on(sw)
        elif command == "off":
            await controller.turn_off(sw)
        elif command == "toggle":
            await controller.toggle(sw)
        else:
            raise ValueError(f"Unknown command: {command}")
        return

    # Tuya
    tuya_devices = _load_tuya_devices(DEFAULT_CONFIG_PATH)
    tuya_dev = next((d for d in tuya_devices if d.device_id == device_id), None)
    if tuya_dev is None:
        raise KeyError(device_id)
    if command not in {"on", "off", "toggle"}:
        raise ValueError(f"Unknown command: {command}")
    current = await asyncio.to_thread(_tuya_current_status, tuya_dev)
    current_value = _tuya_power_value(current, tuya_dev.power_dp)
    next_value = not current_value if command == "toggle" else command == "on"
    await asyncio.to_thread(_tuya_set_power, tuya_dev, next_value)
```

- [ ] **Step 6: Verify the full test suite still passes**

```bash
python3 -m pytest -v
```

Expected: all existing tests + 5 new bridge sync tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/python/bridge_sync.py tests/python/test_bridge_sync.py src/python/web_app.py
git commit -m "feat: add Python bridge sync API for Matter bridge daemon"
```

---

### Task 3: C++ DeviceMapper

**Files:**
- Create: `src/cpp/matter_bridge/DeviceMapper.h`
- Create: `src/cpp/matter_bridge/DeviceMapper.cpp`
- Create: `tests/cpp/matter_bridge/test_device_mapper.cpp`
- Modify: `src/cpp/CMakeLists.txt` (add DeviceMapper to a test target)

**Interfaces:**
- Produces:
  - `enum class MatterDeviceType` — OnOffLight, DimmableLight, OnOffPlugInUnit, TemperatureSensor, HumiditySensor, VirtualOnOffLight, Unknown
  - `struct MatterDeviceSpec { MatterDeviceType type; bool read_only; }`
  - `MatterDeviceSpec MapCategoryToMatter(const std::string& category, bool dimmable = false)`
  - `const char* MatterDeviceTypeName(MatterDeviceType)`
- Consumes: nothing from earlier tasks; no CHIP SDK headers required

- [ ] **Step 1: Write failing tests**

Create `tests/cpp/matter_bridge/test_device_mapper.cpp`:

```cpp
#include <gtest/gtest.h>
#include "src/cpp/matter_bridge/DeviceMapper.h"

TEST(DeviceMapper, LightSwitchNonDimmable) {
    auto spec = MapCategoryToMatter("light_switch", false);
    EXPECT_EQ(spec.type, MatterDeviceType::OnOffLight);
    EXPECT_FALSE(spec.read_only);
}

TEST(DeviceMapper, LightSwitchDimmable) {
    auto spec = MapCategoryToMatter("light_switch", true);
    EXPECT_EQ(spec.type, MatterDeviceType::DimmableLight);
    EXPECT_FALSE(spec.read_only);
}

TEST(DeviceMapper, OutletMapsToPlugInUnit) {
    auto spec = MapCategoryToMatter("outlet");
    EXPECT_EQ(spec.type, MatterDeviceType::OnOffPlugInUnit);
    EXPECT_FALSE(spec.read_only);
}

TEST(DeviceMapper, TuyaSwitchMapsToPlugInUnit) {
    auto spec = MapCategoryToMatter("tuya_switch");
    EXPECT_EQ(spec.type, MatterDeviceType::OnOffPlugInUnit);
    EXPECT_FALSE(spec.read_only);
}

TEST(DeviceMapper, TuyaSensorMapsToTempSensor) {
    auto spec = MapCategoryToMatter("tuya_sensor");
    EXPECT_EQ(spec.type, MatterDeviceType::TemperatureSensor);
    EXPECT_TRUE(spec.read_only);
}

TEST(DeviceMapper, SceneMapsToVirtualOnOffLight) {
    auto spec = MapCategoryToMatter("scene");
    EXPECT_EQ(spec.type, MatterDeviceType::VirtualOnOffLight);
    EXPECT_FALSE(spec.read_only);
}

TEST(DeviceMapper, VirtualSwitchMapsToVirtualOnOffLight) {
    auto spec = MapCategoryToMatter("virtual_switch");
    EXPECT_EQ(spec.type, MatterDeviceType::VirtualOnOffLight);
    EXPECT_FALSE(spec.read_only);
}

TEST(DeviceMapper, UnknownCategoryReturnsUnknown) {
    auto spec = MapCategoryToMatter("bogus_category");
    EXPECT_EQ(spec.type, MatterDeviceType::Unknown);
}

TEST(DeviceMapper, DeviceTypeName) {
    EXPECT_STREQ(MatterDeviceTypeName(MatterDeviceType::OnOffLight), "OnOffLight");
    EXPECT_STREQ(MatterDeviceTypeName(MatterDeviceType::Unknown), "Unknown");
}
```

- [ ] **Step 2: Create `src/cpp/matter_bridge/DeviceMapper.h`**

```cpp
#pragma once
#include <string>

enum class MatterDeviceType {
    OnOffLight,
    DimmableLight,
    OnOffPlugInUnit,
    TemperatureSensor,
    HumiditySensor,
    VirtualOnOffLight,
    Unknown,
};

struct MatterDeviceSpec {
    MatterDeviceType type;
    bool read_only;
};

MatterDeviceSpec MapCategoryToMatter(const std::string& category, bool dimmable = false);
const char* MatterDeviceTypeName(MatterDeviceType type);
```

- [ ] **Step 3: Create `src/cpp/matter_bridge/DeviceMapper.cpp`**

```cpp
#include "DeviceMapper.h"

MatterDeviceSpec MapCategoryToMatter(const std::string& category, bool dimmable) {
    if (category == "light_switch") {
        return {dimmable ? MatterDeviceType::DimmableLight : MatterDeviceType::OnOffLight, false};
    }
    if (category == "outlet" || category == "tuya_switch") {
        return {MatterDeviceType::OnOffPlugInUnit, false};
    }
    if (category == "tuya_sensor") {
        return {MatterDeviceType::TemperatureSensor, true};
    }
    if (category == "scene" || category == "virtual_switch") {
        return {MatterDeviceType::VirtualOnOffLight, false};
    }
    return {MatterDeviceType::Unknown, false};
}

const char* MatterDeviceTypeName(MatterDeviceType type) {
    switch (type) {
        case MatterDeviceType::OnOffLight:        return "OnOffLight";
        case MatterDeviceType::DimmableLight:     return "DimmableLight";
        case MatterDeviceType::OnOffPlugInUnit:   return "OnOffPlugInUnit";
        case MatterDeviceType::TemperatureSensor: return "TemperatureSensor";
        case MatterDeviceType::HumiditySensor:    return "HumiditySensor";
        case MatterDeviceType::VirtualOnOffLight: return "VirtualOnOffLight";
        case MatterDeviceType::Unknown:            return "Unknown";
    }
    return "Unknown";
}
```

- [ ] **Step 4: Add DeviceMapper test target to `src/cpp/CMakeLists.txt`**

Add after the existing `if(BUILD_TESTING)` block:

```cmake
if(BUILD_TESTING)
    # existing smart_home_cpp_tests target ...

    add_executable(matter_bridge_mapper_tests
        ../../tests/cpp/matter_bridge/test_device_mapper.cpp
        matter_bridge/DeviceMapper.cpp
    )
    target_include_directories(matter_bridge_mapper_tests PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
    target_link_libraries(matter_bridge_mapper_tests PRIVATE GTest::gtest_main)
    include(GoogleTest)
    gtest_discover_tests(matter_bridge_mapper_tests)
endif()
```

Also create `tests/cpp/matter_bridge/` directory:

```bash
mkdir -p tests/cpp/matter_bridge
```

- [ ] **Step 5: Run tests**

```bash
docker compose run --rm dev sh -lc \
  "cmake --preset docker-debug && cmake --build --preset docker-debug && \
   ctest --test-dir build/docker-debug --output-on-failure"
```

Expected: 9 tests pass in `matter_bridge_mapper_tests`.

- [ ] **Step 6: Commit**

```bash
git add src/cpp/matter_bridge/DeviceMapper.h src/cpp/matter_bridge/DeviceMapper.cpp \
        tests/cpp/matter_bridge/test_device_mapper.cpp src/cpp/CMakeLists.txt
git commit -m "feat: add C++ DeviceMapper for Matter device type mapping"
```

---

### Task 4: C++ SyncClient

**Files:**
- Create: `src/cpp/matter_bridge/SyncClient.h`
- Create: `src/cpp/matter_bridge/SyncClient.cpp`
- Create: `tests/cpp/matter_bridge/test_sync_client.cpp`
- Modify: `src/cpp/CMakeLists.txt` (add SyncClient test target with libcurl)

**Interfaces:**
- Produces:
  - `struct DeviceInfo { std::string device_id; name; room; category; bool dimmable; std::map<std::string,std::string> state; }`
  - `class SyncClient` with virtual `FetchDevices()`, `FetchAllStates()`, `SendCommand()`
  - `class MockSyncClient : public SyncClient` (in test file, for testing higher layers)
- Consumes: nothing from earlier tasks; requires `libcurl`

- [ ] **Step 1: Write failing tests**

Create `tests/cpp/matter_bridge/test_sync_client.cpp`:

```cpp
#include <gtest/gtest.h>
#include "src/cpp/matter_bridge/SyncClient.h"
#include <map>
#include <string>
#include <vector>
#include <stdexcept>

// Testable subclass that overrides the HTTP layer
class FakeSyncClient : public SyncClient {
public:
    FakeSyncClient() : SyncClient("http://localhost:8000") {}
    std::string devices_response;
    std::string states_response;
    std::string last_post_path;
    std::string last_post_body;

protected:
    std::string DoGet(const std::string& path) override {
        if (path == "/bridge/devices") return devices_response;
        if (path == "/bridge/state/all") return states_response;
        throw SyncClientError("unexpected GET: " + path);
    }
    std::string DoPost(const std::string& path, const std::string& body) override {
        last_post_path = path;
        last_post_body = body;
        return R"({"status":"ok"})";
    }
};

TEST(SyncClient, FetchDevicesParsesJson) {
    FakeSyncClient client;
    client.devices_response = R"([
        {"device_id":"kasa:192.168.1.10","name":"Living Room","room":"Living Room",
         "category":"light_switch","dimmable":false,"state":{"on":true}}
    ])";
    auto devices = client.FetchDevices();
    ASSERT_EQ(devices.size(), 1u);
    EXPECT_EQ(devices[0].device_id, "kasa:192.168.1.10");
    EXPECT_EQ(devices[0].category, "light_switch");
    EXPECT_EQ(devices[0].state.at("on"), "true");
    EXPECT_FALSE(devices[0].dimmable);
}

TEST(SyncClient, FetchDevicesEmptyList) {
    FakeSyncClient client;
    client.devices_response = "[]";
    auto devices = client.FetchDevices();
    EXPECT_TRUE(devices.empty());
}

TEST(SyncClient, FetchAllStatesParsesJson) {
    FakeSyncClient client;
    client.states_response = R"({"kasa:192.168.1.10":{"on":"true"}})";
    auto states = client.FetchAllStates();
    ASSERT_EQ(states.count("kasa:192.168.1.10"), 1u);
    EXPECT_EQ(states.at("kasa:192.168.1.10").at("on"), "true");
}

TEST(SyncClient, SendCommandPostsCorrectBody) {
    FakeSyncClient client;
    client.SendCommand("kasa:192.168.1.10", "on");
    EXPECT_EQ(client.last_post_path, "/bridge/command");
    // body must contain device_id and command
    EXPECT_NE(client.last_post_body.find("kasa:192.168.1.10"), std::string::npos);
    EXPECT_NE(client.last_post_body.find("\"on\""), std::string::npos);
}

TEST(SyncClient, FetchDevicesBadJsonThrows) {
    FakeSyncClient client;
    client.devices_response = "not json";
    EXPECT_THROW(client.FetchDevices(), SyncClientError);
}
```

- [ ] **Step 2: Create `src/cpp/matter_bridge/SyncClient.h`**

```cpp
#pragma once
#include <map>
#include <string>
#include <vector>
#include <stdexcept>

struct DeviceInfo {
    std::string device_id;
    std::string name;
    std::string room;
    std::string category;
    bool dimmable = false;
    std::map<std::string, std::string> state;
};

class SyncClientError : public std::runtime_error {
public:
    explicit SyncClientError(const std::string& msg) : std::runtime_error(msg) {}
};

class SyncClient {
public:
    explicit SyncClient(const std::string& base_url);
    virtual ~SyncClient();

    virtual std::vector<DeviceInfo> FetchDevices();
    virtual std::map<std::string, std::map<std::string, std::string>> FetchAllStates();
    virtual void SendCommand(const std::string& device_id, const std::string& command);

protected:
    // Virtual so tests can override the HTTP layer
    virtual std::string DoGet(const std::string& path);
    virtual std::string DoPost(const std::string& path, const std::string& body);

private:
    std::string base_url_;
};
```

- [ ] **Step 3: Create `src/cpp/matter_bridge/SyncClient.cpp`**

```cpp
#include "SyncClient.h"
#include <curl/curl.h>
#include <nlohmann/json.hpp>
#include <sstream>

using json = nlohmann::json;

static size_t WriteCallback(void* contents, size_t size, size_t nmemb, std::string* output) {
    output->append(static_cast<char*>(contents), size * nmemb);
    return size * nmemb;
}

SyncClient::SyncClient(const std::string& base_url) : base_url_(base_url) {
    curl_global_init(CURL_GLOBAL_DEFAULT);
}

SyncClient::~SyncClient() {
    curl_global_cleanup();
}

std::string SyncClient::DoGet(const std::string& path) {
    CURL* curl = curl_easy_init();
    if (!curl) throw SyncClientError("curl_easy_init failed");

    std::string response;
    const std::string url = base_url_ + path;
    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, WriteCallback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 5L);

    const CURLcode res = curl_easy_perform(curl);
    long http_code = 0;
    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);
    curl_easy_cleanup(curl);

    if (res != CURLE_OK) {
        throw SyncClientError(std::string("GET ") + path + " failed: " + curl_easy_strerror(res));
    }
    if (http_code >= 400) {
        throw SyncClientError("GET " + path + " returned HTTP " + std::to_string(http_code));
    }
    return response;
}

std::string SyncClient::DoPost(const std::string& path, const std::string& body) {
    CURL* curl = curl_easy_init();
    if (!curl) throw SyncClientError("curl_easy_init failed");

    std::string response;
    const std::string url = base_url_ + path;
    curl_slist* headers = nullptr;
    headers = curl_slist_append(headers, "Content-Type: application/json");

    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_POSTFIELDS, body.c_str());
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, WriteCallback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 5L);

    const CURLcode res = curl_easy_perform(curl);
    long http_code = 0;
    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);
    curl_slist_free_all(headers);
    curl_easy_cleanup(curl);

    if (res != CURLE_OK) {
        throw SyncClientError(std::string("POST ") + path + " failed: " + curl_easy_strerror(res));
    }
    if (http_code >= 400) {
        throw SyncClientError("POST " + path + " returned HTTP " + std::to_string(http_code));
    }
    return response;
}

std::vector<DeviceInfo> SyncClient::FetchDevices() {
    const std::string body = DoGet("/bridge/devices");
    json j;
    try {
        j = json::parse(body);
    } catch (const json::exception& ex) {
        throw SyncClientError(std::string("FetchDevices parse error: ") + ex.what());
    }
    std::vector<DeviceInfo> devices;
    for (const auto& item : j) {
        DeviceInfo d;
        d.device_id = item.at("device_id").get<std::string>();
        d.name      = item.at("name").get<std::string>();
        d.room      = item.value("room", "");
        d.category  = item.at("category").get<std::string>();
        d.dimmable  = item.value("dimmable", false);
        if (item.contains("state") && item["state"].is_object()) {
            for (const auto& [k, v] : item["state"].items()) {
                d.state[k] = v.is_string() ? v.get<std::string>() : v.dump();
            }
        }
        devices.push_back(std::move(d));
    }
    return devices;
}

std::map<std::string, std::map<std::string, std::string>> SyncClient::FetchAllStates() {
    const std::string body = DoGet("/bridge/state/all");
    json j;
    try {
        j = json::parse(body);
    } catch (const json::exception& ex) {
        throw SyncClientError(std::string("FetchAllStates parse error: ") + ex.what());
    }
    std::map<std::string, std::map<std::string, std::string>> result;
    for (const auto& [device_id, state] : j.items()) {
        for (const auto& [k, v] : state.items()) {
            result[device_id][k] = v.is_string() ? v.get<std::string>() : v.dump();
        }
    }
    return result;
}

void SyncClient::SendCommand(const std::string& device_id, const std::string& command) {
    json body_j;
    body_j["device_id"] = device_id;
    body_j["command"]   = command;
    DoPost("/bridge/command", body_j.dump());
}
```

- [ ] **Step 4: Add SyncClient test target to `src/cpp/CMakeLists.txt`**

`nlohmann/json` is a header-only library. Install it in the Docker dev container or fetch it:

```bash
# In Dockerfile, add to apt-get install:
#   nlohmann-json3-dev
```

Add to `Dockerfile` (in the apt-get block): `nlohmann-json3-dev \`

Then add to `src/cpp/CMakeLists.txt` inside the `if(BUILD_TESTING)` block:

```cmake
    add_executable(matter_bridge_sync_client_tests
        ../../tests/cpp/matter_bridge/test_sync_client.cpp
        matter_bridge/SyncClient.cpp
    )
    target_include_directories(matter_bridge_sync_client_tests
        PRIVATE ${CMAKE_CURRENT_SOURCE_DIR} /usr/include/nlohmann
    )
    target_link_libraries(matter_bridge_sync_client_tests
        PRIVATE GTest::gtest_main curl
    )
    gtest_discover_tests(matter_bridge_sync_client_tests)
```

- [ ] **Step 5: Rebuild dev container and run tests**

```bash
docker compose build dev
docker compose run --rm dev sh -lc \
  "cmake --preset docker-debug && cmake --build --preset docker-debug && \
   ctest --test-dir build/docker-debug --output-on-failure"
```

Expected: 5 `matter_bridge_sync_client_tests` pass, 9 `matter_bridge_mapper_tests` pass.

- [ ] **Step 6: Commit**

```bash
git add src/cpp/matter_bridge/SyncClient.h src/cpp/matter_bridge/SyncClient.cpp \
        tests/cpp/matter_bridge/test_sync_client.cpp \
        src/cpp/CMakeLists.txt Dockerfile
git commit -m "feat: add C++ SyncClient for bridge HTTP communication"
```

---

### Task 5: C++ BridgeDevice (Matter endpoint wrapper)

**Files:**
- Create: `src/cpp/matter_bridge/BridgeDevice.h`
- Create: `src/cpp/matter_bridge/BridgeDevice.cpp`

**Interfaces:**
- Produces:
  - `class BridgeDevice` — wraps one CHIP SDK dynamic endpoint
  - `BridgeDevice(uint8_t dynamic_index, chip::EndpointId id, const DeviceInfo& info)`
  - `void UpdateOnOff(bool on)` — writes OnOff attribute to Matter
  - `void SetReachable(bool reachable)` — writes Reachable attribute
  - `chip::EndpointId GetEndpointId() const`
  - `const std::string& GetDeviceId() const`
  - `MatterDeviceType GetType() const`
  - Global: `void HandleAttributeChanged(chip::EndpointId, chip::ClusterId, chip::AttributeId, uint8_t* value)` — called from CHIP SDK's `MatterPostAttributeChangeCallback`
- Consumes:
  - `MatterDeviceType`, `MatterDeviceSpec`, `MapCategoryToMatter()` from Task 3

> **Important:** This task requires the CHIP SDK headers. It does NOT need to be compiled separately in the Docker debug preset — it will only compile as part of the `build-matter-bridge.sh` script in Task 6. Write and review the code for correctness; the full compile is validated in Task 6.

- [ ] **Step 1: Create `src/cpp/matter_bridge/BridgeDevice.h`**

```cpp
#pragma once
#include "DeviceMapper.h"
#include "SyncClient.h"

// Forward declarations to avoid including all CHIP SDK headers here
#include <cstdint>
#include <string>
#include <functional>

// CHIP SDK headers — only available after CHIP SDK bootstrap (Task 1)
#include <app/clusters/on-off-server/on-off-server.h>
#include <app/util/attribute-storage.h>
#include <app/util/endpoint-config-api.h>
#include <app-common/zap-generated/ids/Attributes.h>
#include <app-common/zap-generated/ids/Clusters.h>

// Matter device type IDs (from the Matter specification)
static constexpr chip::DeviceTypeId kDeviceTypeIdBridgedNode    = 0x0013;
static constexpr chip::DeviceTypeId kDeviceTypeIdOnOffLight     = 0x0100;
static constexpr chip::DeviceTypeId kDeviceTypeIdDimmableLight  = 0x0101;
static constexpr chip::DeviceTypeId kDeviceTypeIdOnOffPlugIn    = 0x010A;
static constexpr chip::DeviceTypeId kDeviceTypeIdTempSensor     = 0x0302;
static constexpr chip::DeviceTypeId kDeviceTypeIdHumiditySensor = 0x0307;

static constexpr uint16_t kNodeLabelMaxSize = 32;
static constexpr uint16_t kDescriptorArraySize = 254;

// Callback invoked by main.cpp's MatterPostAttributeChangeCallback.
// Routes attribute changes (e.g. Apple Home toggling an on/off state) to
// the provided command sender function.
using CommandSenderFn = std::function<void(const std::string& device_id, const std::string& command)>;

class BridgeDevice {
public:
    // dynamic_index: 0-based slot in the dynamic endpoint array (max ~252)
    // endpoint_id:   Matter endpoint ID (must be >= DYNAMIC_ENDPOINT_START, e.g. 2)
    // info:          device metadata from SyncClient::FetchDevices()
    BridgeDevice(uint8_t dynamic_index,
                 chip::EndpointId endpoint_id,
                 const DeviceInfo& info);
    ~BridgeDevice();

    // Disallow copy; allow move
    BridgeDevice(const BridgeDevice&) = delete;
    BridgeDevice& operator=(const BridgeDevice&) = delete;
    BridgeDevice(BridgeDevice&&) = default;

    // Register this device's dynamic endpoint with the CHIP stack.
    // Call from the Matter event loop thread.
    CHIP_ERROR Register();

    // Remove this device's dynamic endpoint from the CHIP stack.
    void Unregister();

    // Update Matter OnOff attribute (endpoint_id_, OnOff cluster, OnOff attribute).
    // Call from Matter event loop thread.
    void UpdateOnOff(bool on);

    // Mark the device as reachable/unreachable in BridgedDeviceBasicInformation.
    void SetReachable(bool reachable);

    const std::string& GetDeviceId() const { return device_id_; }
    chip::EndpointId GetEndpointId() const { return endpoint_id_; }
    MatterDeviceType GetType() const { return spec_.type; }

    // Called by HandleAttributeChanged() when Apple Home writes to this device's endpoint.
    void OnAttributeChanged(chip::ClusterId cluster_id,
                            chip::AttributeId attribute_id,
                            uint8_t* value,
                            const CommandSenderFn& send_command);

private:
    std::string device_id_;
    std::string name_;
    uint8_t dynamic_index_;
    chip::EndpointId endpoint_id_;
    MatterDeviceSpec spec_;

    // Per-instance data versions (one per cluster; arrays must outlive the endpoint)
    static constexpr size_t kMaxClusters = 4;
    chip::DataVersion data_versions_[kMaxClusters] = {};
};

// Global registry: endpoint_id → BridgeDevice*
// Used by MatterPostAttributeChangeCallback to look up the device.
void BridgeDeviceRegisterInstance(chip::EndpointId id, BridgeDevice* dev);
void BridgeDeviceUnregisterInstance(chip::EndpointId id);
BridgeDevice* BridgeDeviceLookup(chip::EndpointId id);
```

- [ ] **Step 2: Create `src/cpp/matter_bridge/BridgeDevice.cpp`**

```cpp
#include "BridgeDevice.h"
#include <app/util/attribute-storage.h>
#include <app/util/endpoint-config-api.h>
#include <app-common/zap-generated/attribute-type.h>
#include <map>
#include <mutex>

// ── Global endpoint registry ──────────────────────────────────────────────────

static std::mutex gRegistryMutex;
static std::map<chip::EndpointId, BridgeDevice*> gEndpointRegistry;

void BridgeDeviceRegisterInstance(chip::EndpointId id, BridgeDevice* dev) {
    std::lock_guard<std::mutex> lock(gRegistryMutex);
    gEndpointRegistry[id] = dev;
}

void BridgeDeviceUnregisterInstance(chip::EndpointId id) {
    std::lock_guard<std::mutex> lock(gRegistryMutex);
    gEndpointRegistry.erase(id);
}

BridgeDevice* BridgeDeviceLookup(chip::EndpointId id) {
    std::lock_guard<std::mutex> lock(gRegistryMutex);
    auto it = gEndpointRegistry.find(id);
    return it != gEndpointRegistry.end() ? it->second : nullptr;
}

// ── Static cluster/attribute tables (shared by all devices of each type) ─────
// These MUST be static (or global) — the CHIP stack holds pointers to them.

DECLARE_DYNAMIC_ATTRIBUTE_LIST_BEGIN(sOnOffAttribs)
    DECLARE_DYNAMIC_ATTRIBUTE(ZCL_ON_OFF_ATTRIBUTE_ID, BOOLEAN, 1, 0),
DECLARE_DYNAMIC_ATTRIBUTE_LIST_END();

DECLARE_DYNAMIC_ATTRIBUTE_LIST_BEGIN(sBridgedBasicAttribs)
    DECLARE_DYNAMIC_ATTRIBUTE(ZCL_NODE_LABEL_ATTRIBUTE_ID, CHAR_STRING, kNodeLabelMaxSize, ZAP_ATTRIBUTE_MASK(WRITABLE)),
    DECLARE_DYNAMIC_ATTRIBUTE(ZCL_REACHABLE_ATTRIBUTE_ID, BOOLEAN, 1, 0),
DECLARE_DYNAMIC_ATTRIBUTE_LIST_END();

DECLARE_DYNAMIC_ATTRIBUTE_LIST_BEGIN(sDescriptorAttribs)
    DECLARE_DYNAMIC_ATTRIBUTE(ZCL_DEVICE_LIST_ATTRIBUTE_ID, ARRAY, kDescriptorArraySize, 0),
    DECLARE_DYNAMIC_ATTRIBUTE(ZCL_SERVER_LIST_ATTRIBUTE_ID, ARRAY, kDescriptorArraySize, 0),
    DECLARE_DYNAMIC_ATTRIBUTE(ZCL_CLIENT_LIST_ATTRIBUTE_ID, ARRAY, kDescriptorArraySize, 0),
    DECLARE_DYNAMIC_ATTRIBUTE(ZCL_PARTS_LIST_ATTRIBUTE_ID, ARRAY, kDescriptorArraySize, 0),
DECLARE_DYNAMIC_ATTRIBUTE_LIST_END();

DECLARE_DYNAMIC_ATTRIBUTE_LIST_BEGIN(sTempAttribs)
    DECLARE_DYNAMIC_ATTRIBUTE(ZCL_TEMP_MEASURED_VALUE_ATTRIBUTE_ID, INT16S, 2, 0),
    DECLARE_DYNAMIC_ATTRIBUTE(ZCL_TEMP_MIN_MEASURED_VALUE_ATTRIBUTE_ID, INT16S, 2, 0),
    DECLARE_DYNAMIC_ATTRIBUTE(ZCL_TEMP_MAX_MEASURED_VALUE_ATTRIBUTE_ID, INT16S, 2, 0),
DECLARE_DYNAMIC_ATTRIBUTE_LIST_END();

// Cluster list: OnOff Light / virtual switch / plug-in unit (all share same clusters)
DECLARE_DYNAMIC_CLUSTER_LIST_BEGIN(sOnOffClusters)
    DECLARE_DYNAMIC_CLUSTER(ZCL_ON_OFF_CLUSTER_ID, sOnOffAttribs, ZAP_CLUSTER_MASK(SERVER), OnOffIncomingCommands, nullptr),
    DECLARE_DYNAMIC_CLUSTER(ZCL_DESCRIPTOR_CLUSTER_ID, sDescriptorAttribs, ZAP_CLUSTER_MASK(SERVER), nullptr, nullptr),
    DECLARE_DYNAMIC_CLUSTER(ZCL_BRIDGED_DEVICE_BASIC_INFORMATION_CLUSTER_ID, sBridgedBasicAttribs, ZAP_CLUSTER_MASK(SERVER), nullptr, nullptr),
DECLARE_DYNAMIC_CLUSTER_LIST_END;

// Cluster list: Temperature Sensor (read-only)
DECLARE_DYNAMIC_CLUSTER_LIST_BEGIN(sTempClusters)
    DECLARE_DYNAMIC_CLUSTER(ZCL_TEMP_MEASUREMENT_CLUSTER_ID, sTempAttribs, ZAP_CLUSTER_MASK(SERVER), nullptr, nullptr),
    DECLARE_DYNAMIC_CLUSTER(ZCL_DESCRIPTOR_CLUSTER_ID, sDescriptorAttribs, ZAP_CLUSTER_MASK(SERVER), nullptr, nullptr),
    DECLARE_DYNAMIC_CLUSTER(ZCL_BRIDGED_DEVICE_BASIC_INFORMATION_CLUSTER_ID, sBridgedBasicAttribs, ZAP_CLUSTER_MASK(SERVER), nullptr, nullptr),
DECLARE_DYNAMIC_CLUSTER_LIST_END;

// Endpoint type descriptors (one per Matter device type we support)
DECLARE_DYNAMIC_ENDPOINT(sOnOffEndpointType, sOnOffClusters);
DECLARE_DYNAMIC_ENDPOINT(sTempEndpointType, sTempClusters);

// ── Device type lists per Matter type ────────────────────────────────────────

static const EmberAfDeviceType kOnOffLightTypes[] = {
    {kDeviceTypeIdOnOffLight, 1}, {kDeviceTypeIdBridgedNode, 1}
};
static const EmberAfDeviceType kPlugInUnitTypes[] = {
    {kDeviceTypeIdOnOffPlugIn, 1}, {kDeviceTypeIdBridgedNode, 1}
};
static const EmberAfDeviceType kTempSensorTypes[] = {
    {kDeviceTypeIdTempSensor, 1}, {kDeviceTypeIdBridgedNode, 1}
};

// ── BridgeDevice implementation ───────────────────────────────────────────────

BridgeDevice::BridgeDevice(uint8_t dynamic_index,
                           chip::EndpointId endpoint_id,
                           const DeviceInfo& info)
    : device_id_(info.device_id),
      name_(info.name),
      dynamic_index_(dynamic_index),
      endpoint_id_(endpoint_id),
      spec_(MapCategoryToMatter(info.category, info.dimmable)) {}

BridgeDevice::~BridgeDevice() {
    Unregister();
}

CHIP_ERROR BridgeDevice::Register() {
    const EmberAfEndpointType* ep_type  = &sOnOffEndpointType;
    const EmberAfDeviceType*   dev_types = kOnOffLightTypes;
    size_t                     dev_types_count = ArraySize(kOnOffLightTypes);

    size_t cluster_count = ArraySize(sOnOffClusters); // 3 for all on/off types

    if (spec_.type == MatterDeviceType::OnOffPlugInUnit) {
        dev_types       = kPlugInUnitTypes;
        dev_types_count = ArraySize(kPlugInUnitTypes);
    } else if (spec_.type == MatterDeviceType::TemperatureSensor) {
        ep_type         = &sTempEndpointType;
        dev_types       = kTempSensorTypes;
        dev_types_count = ArraySize(kTempSensorTypes);
        cluster_count   = ArraySize(sTempClusters); // also 3, but kept explicit
    }
    // VirtualOnOffLight, DimmableLight → treat same as OnOffLight for now

    CHIP_ERROR err = emberAfSetDynamicEndpoint(
        dynamic_index_,
        endpoint_id_,
        ep_type,
        chip::Span<chip::DataVersion>(data_versions_, cluster_count), // one per cluster
        chip::Span<const EmberAfDeviceType>(dev_types, dev_types_count)
    );

    if (err == CHIP_NO_ERROR) {
        BridgeDeviceRegisterInstance(endpoint_id_, this);
    }
    return err;
}

void BridgeDevice::Unregister() {
    BridgeDeviceUnregisterInstance(endpoint_id_);
    emberAfClearDynamicEndpoint(dynamic_index_);
}

void BridgeDevice::UpdateOnOff(bool on) {
    uint8_t value = on ? 1 : 0;
    emberAfWriteAttribute(
        endpoint_id_,
        ZCL_ON_OFF_CLUSTER_ID,
        ZCL_ON_OFF_ATTRIBUTE_ID,
        &value,
        ZCL_BOOLEAN_ATTRIBUTE_TYPE
    );
}

void BridgeDevice::SetReachable(bool reachable) {
    uint8_t value = reachable ? 1 : 0;
    emberAfWriteAttribute(
        endpoint_id_,
        ZCL_BRIDGED_DEVICE_BASIC_INFORMATION_CLUSTER_ID,
        ZCL_REACHABLE_ATTRIBUTE_ID,
        &value,
        ZCL_BOOLEAN_ATTRIBUTE_TYPE
    );
}

void BridgeDevice::OnAttributeChanged(chip::ClusterId cluster_id,
                                      chip::AttributeId attribute_id,
                                      uint8_t* value,
                                      const CommandSenderFn& send_command) {
    if (spec_.read_only) return;
    if (cluster_id == ZCL_ON_OFF_CLUSTER_ID && attribute_id == ZCL_ON_OFF_ATTRIBUTE_ID) {
        bool on = (*value != 0);
        send_command(device_id_, on ? "on" : "off");
    }
}
```

- [ ] **Step 3: Commit (compile-time verified in Task 6)**

```bash
git add src/cpp/matter_bridge/BridgeDevice.h src/cpp/matter_bridge/BridgeDevice.cpp
git commit -m "feat: add C++ BridgeDevice Matter endpoint wrapper"
```

---

### Task 6: C++ main.cpp + GN build integration

**Files:**
- Create: `src/cpp/matter_bridge/main.cpp`
- Modify: `scripts/build-matter-bridge.sh` (verify final patch)

**Interfaces:**
- Consumes:
  - `BridgeDevice::Register()`, `BridgeDevice::UpdateOnOff()`, `SetReachable()` from Task 5
  - `BridgeDeviceLookup()` from Task 5
  - `SyncClient::FetchDevices()`, `FetchAllStates()`, `SendCommand()` from Task 4
  - `MapCategoryToMatter()` from Task 3
- Produces: `build/matter-bridge/chip-bridge-app` — runnable aarch64 binary

- [ ] **Step 1: Create `src/cpp/matter_bridge/main.cpp`**

```cpp
/*
 * Matter Bridge main.cpp
 *
 * Initialises the CHIP stack, fetches devices from the Python bridge sync API,
 * registers them as dynamic Matter endpoints, then runs a background poll loop
 * that keeps Apple Home in sync with real device state.
 *
 * Build: scripts/build-matter-bridge.sh (inside Docker dev container)
 */
#include "BridgeDevice.h"
#include "DeviceMapper.h"
#include "SyncClient.h"

#include <app/server/Server.h>
#include <app/server/CommissioningWindowManager.h>
#include <credentials/DeviceAttestationCredsProvider.h>
#include <credentials/examples/DeviceAttestationCredsExample.h>
#include <lib/core/ErrorStr.h>
#include <platform/CHIPDeviceLayer.h>
#include <platform/Linux/NetworkCommissioningDriver.h>

#include <atomic>
#include <chrono>
#include <memory>
#include <thread>
#include <vector>

using namespace chip;
using namespace chip::app;
using namespace chip::DeviceLayer;

// ── Constants ─────────────────────────────────────────────────────────────────

static constexpr uint16_t kDevicePollIntervalSeconds = 10;
static constexpr uint16_t kDeviceRescanIntervalSeconds = 60;
static constexpr EndpointId kDynamicEndpointStart = 2; // 0=root, 1=aggregator bridge
static constexpr uint8_t kMaxDynamicDevices = 50;

static const char* kBridgeSyncBaseUrl = "http://localhost:8000";

// ── Globals ───────────────────────────────────────────────────────────────────

static SyncClient gSyncClient(kBridgeSyncBaseUrl);
static std::vector<std::unique_ptr<BridgeDevice>> gDevices;
static std::atomic<bool> gRunning{true};

// ── CHIP SDK callbacks ────────────────────────────────────────────────────────

// Called by the CHIP stack when an attribute is written (e.g. Apple Home toggles a switch).
void MatterPostAttributeChangeCallback(const ConcreteAttributePath& path,
                                       uint8_t type,
                                       uint16_t size,
                                       uint8_t* value) {
    BridgeDevice* dev = BridgeDeviceLookup(path.mEndpointId);
    if (!dev) return;
    dev->OnAttributeChanged(
        path.mClusterId, path.mAttributeId, value,
        [](const std::string& device_id, const std::string& command) {
            try {
                gSyncClient.SendCommand(device_id, command);
            } catch (const SyncClientError& e) {
                ChipLogError(AppServer, "SendCommand failed: %s", e.what());
            }
        }
    );
}

// Required CHIP SDK stub
bool emberAfAttributeReadAccessCallback(EndpointId, ClusterId, AttributeId) { return true; }
bool emberAfAttributeWriteAccessCallback(EndpointId, ClusterId, AttributeId) { return true; }

// ── Device management ─────────────────────────────────────────────────────────

static void RegisterDevices(const std::vector<DeviceInfo>& infos) {
    for (uint8_t i = 0; i < infos.size() && i < kMaxDynamicDevices; ++i) {
        const auto& info = infos[i];
        auto spec = MapCategoryToMatter(info.category, info.dimmable);
        if (spec.type == MatterDeviceType::Unknown) {
            ChipLogDetail(AppServer, "Skipping unknown category: %s", info.category.c_str());
            continue;
        }
        EndpointId ep_id = static_cast<EndpointId>(kDynamicEndpointStart + i);
        auto dev = std::make_unique<BridgeDevice>(i, ep_id, info);
        CHIP_ERROR err = dev->Register();
        if (err != CHIP_NO_ERROR) {
            ChipLogError(AppServer, "Register endpoint %u failed: %s",
                         ep_id, ErrorStr(err));
            continue;
        }
        // Apply initial on/off state
        auto it = info.state.find("on");
        if (it != info.state.end()) {
            dev->UpdateOnOff(it->second == "true" || it->second == "1");
        }
        dev->SetReachable(true);
        gDevices.push_back(std::move(dev));
        ChipLogDetail(AppServer, "Registered %s (ep=%u) as %s",
                      info.name.c_str(), ep_id,
                      MatterDeviceTypeName(spec.type));
    }
}

// ── Background poll thread ────────────────────────────────────────────────────

static void PollLoop() {
    uint32_t ticks = 0;
    while (gRunning) {
        std::this_thread::sleep_for(std::chrono::seconds(kDevicePollIntervalSeconds));
        ++ticks;

        // Rescan for new devices every kDeviceRescanIntervalSeconds
        if (ticks % (kDeviceRescanIntervalSeconds / kDevicePollIntervalSeconds) == 0) {
            try {
                auto new_infos = gSyncClient.FetchDevices();
                // Simple strategy: if device count changed, re-register from scratch.
                // A production bridge would diff and add/remove individually.
                if (new_infos.size() != gDevices.size()) {
                    ChipLogDetail(AppServer, "Device list changed (%zu → %zu), re-registering",
                                  gDevices.size(), new_infos.size());
                    gDevices.clear();
                    RegisterDevices(new_infos);
                }
            } catch (const SyncClientError& e) {
                ChipLogError(AppServer, "FetchDevices failed: %s", e.what());
            }
        }

        // Poll current state and push to Matter attributes
        try {
            auto states = gSyncClient.FetchAllStates();
            for (const auto& dev_ptr : gDevices) {
                const auto it = states.find(dev_ptr->GetDeviceId());
                if (it == states.end()) continue;
                const auto& state = it->second;
                auto on_it = state.find("on");
                if (on_it != state.end()) {
                    bool on = (on_it->second == "true" || on_it->second == "1");
                    PlatformMgr().ScheduleWork([](intptr_t ctx) {
                        auto* pair = reinterpret_cast<std::pair<BridgeDevice*, bool>*>(ctx);
                        pair->first->UpdateOnOff(pair->second);
                        delete pair;
                    }, reinterpret_cast<intptr_t>(new std::pair<BridgeDevice*, bool>(dev_ptr.get(), on)));
                }
            }
        } catch (const SyncClientError& e) {
            ChipLogError(AppServer, "FetchAllStates failed: %s", e.what());
        }
    }
}

// ── main ──────────────────────────────────────────────────────────────────────

int main(int argc, char* argv[]) {
    CHIP_ERROR err = CHIP_NO_ERROR;

    err = Platform::MemoryInit();
    VerifyOrDie(err == CHIP_NO_ERROR);

    err = PlatformMgr().InitChipStack();
    VerifyOrDie(err == CHIP_NO_ERROR);

    // Use example DAC provider (replace with a real one for production)
    SetDeviceAttestationCredentialsProvider(
        Credentials::Examples::GetExampleDACProvider());

    static CommonCaseDeviceServerInitParams initParams;
    initParams.InitializeStaticResourcesBeforeServerInit();
    err = Server::GetInstance().Init(initParams);
    VerifyOrDie(err == CHIP_NO_ERROR);

    // Fetch initial device list; retry until Python dashboard is ready
    std::vector<DeviceInfo> device_infos;
    while (device_infos.empty()) {
        try {
            device_infos = gSyncClient.FetchDevices();
        } catch (const SyncClientError& e) {
            ChipLogError(AppServer, "Waiting for bridge sync API: %s", e.what());
            std::this_thread::sleep_for(std::chrono::seconds(5));
        }
    }
    RegisterDevices(device_infos);

    // Start background poll thread
    std::thread poll_thread(PollLoop);

    ChipLogDetail(AppServer, "Matter bridge running. Commission via Apple Home.");
    PlatformMgr().RunEventLoop();

    gRunning = false;
    poll_thread.join();

    Server::GetInstance().Shutdown();
    PlatformMgr().Shutdown();
    return 0;
}
```

- [ ] **Step 2: Run the build script inside Docker (first full compile)**

This will take 30–60 minutes the first time.

```bash
# First time only: bootstrap the SDK (30-60 min)
docker compose run --rm dev bash scripts/setup-matter-sdk.sh

# Then build the bridge (~10-20 min on subsequent runs)
docker compose run --rm dev bash scripts/build-matter-bridge.sh
```

Expected output (last lines):
```
==> Done: /workspace/smart-home-rpi4/build/matter-bridge/chip-bridge-app
-rwxr-xr-x 1 developer developer 14M Jun 26 12:00 build/matter-bridge/chip-bridge-app
```

Expected: binary exists at `build/matter-bridge/chip-bridge-app`, size 8–20 MB.

- [ ] **Step 3: Verify binary is aarch64**

```bash
file build/matter-bridge/chip-bridge-app
```

Expected: `ELF 64-bit LSB executable, ARM aarch64, ...`

- [ ] **Step 4: Commit**

```bash
git add src/cpp/matter_bridge/main.cpp
git commit -m "feat: add Matter bridge main.cpp + verified aarch64 build"
```

---

### Task 7: Docker service + deployment pipeline

**Files:**
- Create: `Dockerfile.matter-bridge`
- Create: `scripts/deploy-matter-bridge.sh`
- Modify: `docker-compose.pi.yml` (add `matter-bridge` service)

**Interfaces:**
- Consumes: `build/matter-bridge/chip-bridge-app` from Task 6
- Produces: running `matter-bridge` container on Pi that registers with Apple Home

- [ ] **Step 1: Create `Dockerfile.matter-bridge`**

This image is for the Pi. It installs `libcurl` runtime (not -dev), copies the pre-built binary, and runs it.

```dockerfile
FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libcurl4 \
        libavahi-client3 \
        libglib2.0-0 \
        libdbus-1-3 \
        libnl-3-200 \
        libnl-route-3-200 \
        iproute2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copied by deploy-matter-bridge.sh or docker build context
COPY build/matter-bridge/chip-bridge-app /app/matter-bridge

RUN useradd -m matter && chown -R matter /app
USER matter

ENV MATTER_KVS_PATH=/data/bridge

CMD ["/app/matter-bridge", "--KVS", "/data/bridge/chip.kvs"]
```

- [ ] **Step 2: Add matter-bridge service to `docker-compose.pi.yml`**

Add after the `go2rtc` service (before the `volumes:` section):

```yaml
  matter-bridge:
    build:
      context: .
      dockerfile: Dockerfile.matter-bridge
    image: smart-home-matter-bridge:latest
    container_name: matter-bridge
    network_mode: host
    restart: unless-stopped
    volumes:
      - matter-data:/data
    environment:
      - MATTER_KVS_PATH=/data/bridge
```

- [ ] **Step 3: Create `scripts/deploy-matter-bridge.sh`**

```bash
#!/usr/bin/env bash
# Deploy the Matter bridge binary and Docker image to the Raspberry Pi.
# Requires: PI_HOST env var set to the Pi's IP or hostname.
# Usage: PI_HOST=192.168.1.5 bash scripts/deploy-matter-bridge.sh
set -e

PROJECT_ROOT="$(git rev-parse --show-toplevel)"
PI_HOST="${PI_HOST:-raspberrypi.local}"
PI_USER="${PI_USER:-pi}"
REMOTE="${PI_USER}@${PI_HOST}"
REMOTE_DIR="/home/${PI_USER}/smart-home-rpi4"

echo "==> Syncing project files (including pre-built binary) to $REMOTE..."
rsync -avz --progress \
  --exclude='.git' \
  --exclude='third_party/' \
  --exclude='build/docker-debug' \
  --exclude='build/rpi4-release' \
  "$PROJECT_ROOT/" \
  "${REMOTE}:${REMOTE_DIR}/"

echo "==> Building and starting matter-bridge container on Pi..."
ssh "${REMOTE}" "cd ${REMOTE_DIR} && docker compose -f docker-compose.pi.yml build matter-bridge && docker compose -f docker-compose.pi.yml up -d matter-bridge"

echo "==> Done. Logs:"
ssh "${REMOTE}" "docker logs --tail=20 matter-bridge"
```

```bash
chmod +x scripts/deploy-matter-bridge.sh
```

- [ ] **Step 4: Test Docker image build locally (x86 simulation)**

```bash
docker build -f Dockerfile.matter-bridge -t smart-home-matter-bridge:test .
```

Expected: build succeeds (the binary exists from Task 6, so the COPY step works).

- [ ] **Step 5: Verify `docker-compose.pi.yml` is valid**

```bash
docker compose -f docker-compose.pi.yml config
```

Expected: valid YAML with five services: dashboard, matter-server, go2rtc, matter-bridge.

- [ ] **Step 6: Commit**

```bash
git add Dockerfile.matter-bridge scripts/deploy-matter-bridge.sh docker-compose.pi.yml
git commit -m "feat: add Matter bridge Docker service and deploy script"
```

---

### Integration Test Checklist (Manual — run after deploying to Pi)

- [ ] **1. Deploy**

```bash
PI_HOST=<pi-ip> bash scripts/deploy-matter-bridge.sh
```

- [ ] **2. Verify bridge started**

```bash
ssh pi@<pi-ip> "docker logs matter-bridge --tail=30"
```

Expected: `Matter bridge running. Commission via Apple Home.`

- [ ] **3. Commission with iPhone**

- Open **Home** app → tap **+** → **Add Accessory** → **More options...**
- Select the `SmartHomeBridge` accessory
- Follow pairing prompts

Expected: bridge appears in Apple Home and all dashboard devices appear as accessories.

- [ ] **4. Command round-trip**

- Toggle a switch in Apple Home
- Verify the physical switch toggles
- Expected latency: < 500 ms

- [ ] **5. State sync round-trip**

- Physically toggle a switch
- Wait up to 15 seconds
- Verify Apple Home reflects the new state

- [ ] **6. Dynamic device addition**

- Add a new switch entry to `configs/devices.local.yaml`, restart dashboard
- Wait up to 60 seconds
- Verify the new device appears in Apple Home without restarting the bridge
