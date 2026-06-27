# Matter Bridge Design

**Date:** 2026-06-26
**Status:** Approved

## Goal

Make the Raspberry Pi 4 act as a Matter Bridge so all dashboard devices (TP-Link switches, Tuya sensors, scenes, and custom virtual switches) appear natively in Apple Home on iPhone.

---

## Architecture

Three layers:

```
Apple Home ──Matter/BLE/mDNS──► C++ Matter Bridge Daemon
                                        │  HTTP localhost:8000
                                        ▼
                              Python Bridge Sync API  (bridge_sync.py)
                                        │
                              ┌─────────┴─────────┐
                           Kasa SDK           Tuya SDK
                           (TP-Link)          (sensors)
```

### Components

**1. `src/cpp/matter_bridge/` — C++ Matter Bridge Daemon**

Built on the connectedhomeip SDK (CHIP SDK). Registers with Apple Home as a Matter Bridge device type. Dynamically creates one Matter endpoint per dashboard device at startup. Handles commands from Apple Home, relays them to Python, and reports state changes back to Apple Home.

**2. `src/python/bridge_sync.py` — Python Bridge Sync API**

New FastAPI router mounted into `web_app.py`. Mounts its router at the `/bridge` prefix on the same web app (port 8000). The bridge endpoints are on the same port as the dashboard — no separate port — but are intended for localhost-only access from the C++ daemon. The C++ bridge calls these to query the device list, send commands, and receive state updates. The Python poller already running for the dashboard detects state changes and POSTs them to the bridge.

**3. `third_party/connectedhomeip/` — CHIP SDK**

Git submodule pinned to a stable release tag. Cross-compiled in the Docker dev container to an aarch64 Linux binary. Not built on the Pi.

**4. Matter Bridge service in `docker-compose.pi.yml`**

New service alongside the existing dashboard, matter-server, and go2rtc services. Uses `network_mode: host` (required for mDNS announcement and BLE commissioning).

---

## Data Flow

### Apple Home → Device (command path)

```
1. User taps switch in Apple Home
2. Apple Home sends Matter OnOff command to C++ bridge endpoint
3. C++ bridge POSTs to Python:
   POST localhost:8000/bridge/command
   {"device_id": "kasa_living_room", "command": "on"}
4. Python calls existing Kasa/Tuya SDK (same code dashboard already uses)
5. Python responds 200 OK
6. C++ bridge updates Matter attribute immediately (optimistic update)
7. Next state poll confirms and corrects if needed
```

### Device → Apple Home (state sync path)

```
1. Python poller runs every 10s (same interval dashboard uses today)
2. Poller detects state change (e.g. physical toggle of switch)
3. Python POSTs to C++ bridge:
   POST localhost:8000/bridge/state
   {"device_id": "kasa_living_room", "state": {"on": false}}
4. C++ bridge updates Matter attribute → Apple Home reflects new state
```

### Startup sequence

```
1. Python dashboard starts (existing)
2. C++ bridge starts, calls GET localhost:8000/bridge/devices
3. Python returns full device list with types and current state
4. C++ bridge registers one Matter endpoint per device
5. Bridge announces via mDNS — Apple Home can commission it
```

**IPC transport:** HTTP on `localhost:8000` (the same port as the main dashboard). The `/bridge` router is mounted directly on the web app — no separate process or port. Easy to test with curl, negligible latency on loopback with `network_mode: host`.

---

## Device Type Mapping

| Dashboard category | Matter device type | Matter cluster | Notes |
|---|---|---|---|
| `light_switch` (on/off) | On/Off Light | OnOff | TP-Link basic switches |
| `light_switch` (dimmable) | Dimmable Light | OnOff + LevelControl | If brightness supported |
| `outlet` / plug | On/Off Plugin Unit | OnOff | TP-Link outlet switches |
| Tuya temperature sensor | Temperature Sensor | TemperatureMeasurement | Read-only |
| Tuya humidity sensor | Humidity Sensor | RelativeHumidityMeasurement | Read-only |
| Scene | On/Off Light (virtual) | OnOff | ON triggers scene; OFF is no-op |
| Custom action switch | On/Off Light (virtual) | OnOff | User-defined action on ON |

**Scenes as virtual On/Off Light:** Apple Home has no native scene-trigger Matter device type. Mapping to On/Off Light is the standard workaround used by Home Assistant's Matter bridge and others.

**Dynamic endpoint registration:** When a new device is added to `devices.local.yaml` and the dashboard restarts, `/bridge/devices` returns the updated list. The C++ bridge detects the delta on its 60s poll and registers new endpoints at runtime via `emberAfSetDynamicEndpoint()` — no bridge restart required.

---

## Build Pipeline

### Repository layout changes

```
third_party/connectedhomeip/         ← git submodule, pinned release tag
src/cpp/matter_bridge/
  CMakeLists.txt                     ← wraps GN build
  main.cpp
  BridgeDevice.h / .cpp              ← one Matter endpoint per dashboard device
  DeviceMapper.h / .cpp              ← category → Matter device type table
  SyncClient.h / .cpp                ← HTTP client for localhost:8000
  tests/                             ← GoogleTest unit tests
src/python/bridge_sync.py            ← new FastAPI router
scripts/
  build-matter-bridge.sh             ← GN cross-compile inside Docker dev container
  deploy-matter-bridge.sh            ← rsync binary to Pi
Dockerfile.matter-bridge             ← copies pre-built aarch64 binary
```

### Build flow

```bash
# Cross-compile inside Docker dev container (not on the Pi)
./scripts/build-matter-bridge.sh
# → build/matter-bridge/chip-bridge  (~8–20 MB stripped aarch64 binary)

./scripts/deploy-matter-bridge.sh
```

The CHIP SDK uses GN (Google's Ninja generator) as its primary build system. `build-matter-bridge.sh` invokes `scripts/build/build_examples.py` from the SDK with a Linux aarch64 cross-compile target, then strips the output binary.

### `docker-compose.pi.yml` addition

```yaml
matter-bridge:
  image: smart-home-matter-bridge
  build:
    context: .
    dockerfile: Dockerfile.matter-bridge
  network_mode: host
  restart: unless-stopped
  volumes:
    - matter-data:/data
  environment:
    - BRIDGE_SYNC_URL=http://localhost:8000
    - DASHBOARD_DEVICES_URL=http://localhost:8000
```

`Dockerfile.matter-bridge` copies the pre-built aarch64 binary. The CHIP SDK is not built inside this Dockerfile — it is too large to build on the Pi side.

### Commissioning persistence

`matter-data` volume is already declared for the `matter-server` service. The bridge uses `/data/bridge/` and matter-server uses `/data/server/` within the same volume to avoid collisions.

### Binary size

| Build type | Approximate size |
|---|---|
| Debug (unstripped) | 150–300 MB |
| Release (`-O2`, unstripped) | 50–100 MB |
| Release + stripped | 8–20 MB |

---

## Error Handling

| Failure scenario | Behavior |
|---|---|
| Python dashboard down at bridge startup | Bridge retries `/bridge/devices` every 30s; Matter endpoints not registered until Python is reachable |
| Python dashboard goes down mid-run | Bridge serves last known state; Apple Home stays responsive; logs warning every 60s |
| Device unreachable (Kasa/Tuya offline) | Python returns 503; bridge reports Matter error to Apple Home (device shows "Not Responding") |
| New device added while bridge running | Bridge detects delta on 60s poll, registers new endpoint dynamically — no restart |
| Matter commissioning data lost | Bridge must be re-commissioned in Apple Home; `/data/bridge/` volume protects against accidental loss |

---

## Testing

**1. Python unit tests — `tests/python/test_bridge_sync.py`**

Test the bridge sync API endpoints directly: device list serialization, command routing to Kasa/Tuya, state push format. No real devices required.

**2. C++ unit tests — `src/cpp/matter_bridge/tests/`**

Test `DeviceMapper` (category → Matter type table), `BridgeDevice` attribute update logic, and `SyncClient` HTTP request formatting. Uses GoogleTest (included in CHIP SDK).

**3. Integration test (manual, one-time)**

- Commission the bridge with Apple Home on iPhone
- Verify each device type appears with the correct icon and name
- Toggle a switch from Apple Home → confirm physical device toggles
- Physically toggle a device → confirm Apple Home updates within ~15s
- Add a new device to `devices.local.yaml`, restart dashboard → confirm new device appears in Apple Home within 60s without restarting the bridge
