# Matter Bridge — Implementation Status

**Status:** Working. Apple Home commissioning confirmed on 2026-06-27.
**Deployment:** systemd user unit since 2026-07-08 (the original Docker deployment was retired — the published image was amd64 and failed on the Pi with `exec format error`).

> This is the bridge (our devices *out* to Apple Home). For pairing third-party
> Matter devices *into* the dashboard, see [`matter-controller.md`](matter-controller.md).

---

## What Was Built

A C++ daemon (`chip-bridge-app`) running on the Orange Pi 6 Plus that bridges all dashboard devices (TP-Link switches, Tuya sensors) into Apple Home via the Matter protocol.

```
Apple Home ──Matter/mDNS──► C++ chip-bridge-app  (systemd user unit, host network)
                                     │  HTTP localhost:8000
                                     ▼
                           Python /bridge/* API  (bridge_sync.py)
                                     │
                              Kasa / Tuya SDKs
```

## Files Added

| File | Purpose |
|------|---------|
| `src/cpp/matter_bridge/main.cpp` | Entry point; calls `ChipLinuxAppInit` then runs custom event loop |
| `src/cpp/matter_bridge/BridgeDevice.h/.cpp` | One Matter endpoint per dashboard device |
| `src/cpp/matter_bridge/DeviceMapper.h/.cpp` | Maps dashboard category → Matter device type |
| `src/cpp/matter_bridge/SyncClient.h/.cpp` | HTTP client for `localhost:8000/bridge/*` |
| `src/python/bridge_sync.py` | FastAPI router mounted at `/bridge` on web_app |
| `configs/matter-bridge.service` | systemd user unit installed on the Pi by the deploy script |
| `scripts/build-matter-bridge.sh` | Cross-compiles for arm64 inside Docker dev container |
| `scripts/deploy-matter-bridge.sh` | rsyncs binary + unit to Pi, restarts the user unit |
| `scripts/build-matter-bridge-native.sh` | Builds x86_64 binary for integration tests |
| `scripts/test-matter-commissioning.sh` | Full chip-tool commissioning smoke test |
| `tests/python/test_bridge_sync.py` | Unit tests for `/bridge/*` Python endpoints |
| `tests/python/test_matter_auth_bypass.py` | Regression: `/bridge/*` must not require login |
| `tests/python/test_matter_bridge_integration.py` | Integration tests (need native binary) |
| `third_party/connectedhomeip` | Git submodule pinned to v1.3.0.0 |

**Modified files:** `src/python/web_app.py`, `pyproject.toml`

---

## Deployment (systemd user unit)

The bridge runs on the Pi as the systemd **user** service `matter-bridge.service` under the `smarthome` user (linger enabled via `loginctl enable-linger smarthome`, matching the other Pi services: `matter-server`, `go2rtc`, `smart-home-dashboard`).

Key facts (see `configs/matter-bridge.service`):

- ExecStart: `chip-bridge-app --KVS /home/smarthome/matter-bridge-kvs/kvs --interface wlan0 --discriminator 2861 --passcode 56123489`
- Logs append to `~/matter-bridge.log` on the Pi
- `Restart=always`, `BRIDGE_SYNC_URL=http://localhost:8000`

Deploy (build + rsync + restart) from WSL:

```bash
PI_HOST=192.168.0.176 bash scripts/deploy-matter-bridge.sh
# already built? skip the build step:
PI_HOST=192.168.0.176 SKIP_BUILD=1 bash scripts/deploy-matter-bridge.sh
```

Useful commands on the Pi:

```bash
systemctl --user status matter-bridge.service
systemctl --user restart matter-bridge.service
tail -f ~/matter-bridge.log
```

---

## Commissioning the Bridge (iPhone / Apple Home)

1. Make sure the service is running: `systemctl --user status matter-bridge.service`
2. Read the 11-digit manual pairing code from `~/matter-bridge.log`:
   ```
   CHIP:SVR: Manual pairing code: [34970112332]
   ```
   **Always read this from the logs — do not calculate it manually.**
3. In Apple Home on iPhone: Add Accessory → "More options" → enter the 11-digit code.
4. Passcode `56123489`, discriminator `2861` (set in the unit's ExecStart).

To re-commission from scratch (wipe the KVS):
```bash
systemctl --user stop matter-bridge.service
mv ~/matter-bridge-kvs/kvs ~/matter-bridge-kvs/kvs.bak-$(date +%m%d-%H%M)
systemctl --user start matter-bridge.service   # opens the commissioning window
```

---

## Bugs Found and Fixed During Implementation

### Bug 1 — mDNS advertising the docker0 IP (historical, Docker era)

**Symptom:** iPhone showed "Unable to connect to accessory" after entering the pairing code.

**Root cause:** CHIP's minimal mDNS stack sends multicast announcements on **all** network interfaces, including docker0 (172.17.0.1). `--interface wlan0` only selects which IP is used for some A records; it does not restrict which interfaces multicast is sent on. iPhone received the 172.x A record last, cached it, and tried to connect to an unreachable address.

**Fix (at the time):** Bring docker0 down at container startup (`ip link set docker0 down`) via the container entrypoint with `cap_add: [NET_ADMIN]`. Note: the bridge now runs directly on the host via systemd, and docker0 still exists on the Pi (Home Assistant runs in Docker) — if the 172.x A-record problem resurfaces, the longer-term fix is building the bridge with `chip_mdns="platform"` and running avahi-daemon.

**Regression test:** `test_bridge_mdns_no_docker_bridge_ip` in `test_matter_bridge_integration.py`

---

### Bug 2 — Wrong manual pairing code

**Symptom:** "Incorrect code" error in Apple Home.

**Root cause:** The 11-digit manual pairing code is computed by the SDK's `ManualSetupPayloadGenerator` and includes a check digit — it is NOT simply derived from the passcode alone.

**Fix:** Always read the code from the bridge log line: `CHIP:SVR: Manual pairing code: [...]`

---

### Bug 3 — DAC provider "Not Implemented" (attestation failure)

**Symptom:** PASE (pairing) succeeded but commissioning failed with "Pairing failed" on iPhone. Bridge logs showed `CertificateChainRequest` returning `CHIP_ERROR_NOT_IMPLEMENTED`.

**Root cause:** `SetDeviceAttestationCredentialsProvider()` is called at line ~588 of `AppMain.cpp` inside `ChipLinuxAppMainLoop()`. Our `main.cpp` calls `ChipLinuxAppInit()` but runs its own event loop (not `ChipLinuxAppMainLoop()`), so the DAC provider was never set up.

**Fix:** In `main.cpp`, call this explicitly after `ChipLinuxAppInit()` and before `Server::GetInstance().Init()`:
```cpp
#include <credentials/examples/DeviceAttestationCredsExample.h>

chip::Credentials::SetDeviceAttestationCredentialsProvider(
    chip::Credentials::Examples::GetExampleDACProvider());
```

This uses the example test DAC (VID=0xFFF1) which Apple Home accepts for development.

**Regression test:** `test_bridge_dac_provider_not_not_implemented` in `test_matter_bridge_integration.py`

---

### Bug 4 — Auth middleware blocking `/bridge/*` endpoints

**Symptom:** C++ bridge always received an empty device list on startup.

**Root cause:** The auth middleware in `web_app.py` redirected all unauthenticated requests to `/login`, including calls from the local C++ bridge daemon.

**Fix:** Added `path.startswith("/bridge/")` to the auth skip list in the middleware.

**Regression test:** All tests in `test_matter_auth_bypass.py`

---

## Building the Bridge Binary

### Production (arm64, for Pi)
```bash
# Inside Docker dev container:
bash scripts/build-matter-bridge.sh
# Output: build/matter-bridge/chip-bridge-app  (~10 MB stripped)

PI_HOST=192.168.0.176 SKIP_BUILD=1 bash scripts/deploy-matter-bridge.sh
```
The deploy script rsyncs the binary to the Pi and restarts `matter-bridge.service`, which picks up the new binary immediately.

### Native x86_64 (for integration tests)
```bash
# Inside Docker dev container, after setup-matter-sdk.sh:
bash scripts/build-matter-bridge-native.sh
# Output: build/matter-bridge-native/chip-bridge-app
```

### Running integration tests
```bash
python3 -m pytest -m matter_integration -v
```
Tests auto-skip if the native binary is absent. Set `MATTER_SKIP_BUILD=1` to suppress the build attempt.

---

## Python Bridge Sync API (`/bridge/*`)

Mounted on `web_app.py`. Auth middleware bypasses these routes. All responses are JSON.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/bridge/devices` | GET | Full device list with type, state, and Matter category |
| `/bridge/state/all` | GET | Current state cache (last poll result) |
| `/bridge/state` | POST | C++ bridge POSTs state updates here (Python caches them) |
| `/bridge/command` | POST | C++ bridge sends `{device_id, command}` to control a device |

---

## Device Type Mapping

| Dashboard category | Matter device type | Notes |
|---|---|---|
| `light_switch` | On/Off Light | TP-Link basic switches |
| `outlet` / plug | On/Off Plugin Unit | TP-Link outlet switches |
| `tuya_sensor` (temp) | Temperature Sensor | Read-only |
| `tuya_sensor` (humidity) | Humidity Sensor | Read-only |
| Scene | On/Off Light (virtual) | ON triggers scene; OFF is no-op |

---

## Adding More Features

Things to build next on top of the Matter bridge:

- **Fix poll thread endpoint re-registration loop** — track registered endpoint IDs and skip `emberAfSetDynamicEndpoint()` for already-registered ones.
- **Dimmable lights** — extend `DeviceMapper` and `BridgeDevice` to handle `LevelControl` cluster for TP-Link dimmable switches.
- **State push from Python to bridge** — currently the bridge polls every 60 s; add a POST from the Python poller to push state changes immediately.
- **Tuya sensors with real values** — bridge currently maps sensors to on/off; should use `TemperatureMeasurement` / `RelativeHumidityMeasurement` clusters with actual readings.
- **Production DAC** — replace `GetExampleDACProvider()` with a real Device Attestation Certificate for App Store / commercial use (requires Matter certification).
