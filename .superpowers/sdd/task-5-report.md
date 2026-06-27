# Task 5 Report: C++ BridgeDevice Matter Endpoint Wrapper

## Note
This file was previously used for a different task's report. Content replaced with Task 5 (C++ BridgeDevice) report.

---

## Files Created / Modified

| File | Action |
|------|--------|
| `src/cpp/matter_bridge/BridgeDevice.h` | Created |
| `src/cpp/matter_bridge/BridgeDevice.cpp` | Created |
| `tests/cpp/matter_bridge/test_bridge_device.cpp` | Created |
| `src/cpp/CMakeLists.txt` | Modified — added `matter_bridge_device_tests` target |

## Commit Sequence

1. `6cf0a0f` — `test: add BridgeDevice unit tests with CHIP SDK stubs` (tests first, TDD)
2. `03c9cbb` — `feat: add C++ BridgeDevice Matter endpoint wrapper`
3. `9f46699` — `fix: resolve CommandId ordering and narrowing warning in BridgeDevice tests`

## Test Command and Output

Build:
```
g++ -std=c++17 -Wall -Wextra \
    -I<project_root> -I<project_root>/src/cpp \
    -I<gtest_include> \
    tests/cpp/matter_bridge/test_bridge_device.cpp \
    -o /tmp/matter_bridge_device_tests \
    <gtest_libs>/libgtest.a <gtest_libs>/libgtest_main.a -lpthread
```

Result: **BUILD_EXIT:0, TEST_EXIT:0 — 23/23 tests PASSED, 0 warnings, 0 failures**

Tests cover:
- Constructor accessors (GetDeviceId, GetEndpointId, GetType × 4 device categories)
- Register/Unregister lifecycle (calls `emberAfSetDynamicEndpoint`/`emberAfClearDynamicEndpoint`, adds/removes from registry)
- Register propagates CHIP error; on failure device NOT added to registry
- Destructor calls Unregister
- UpdateOnOff writes correct cluster/attribute/value
- SetReachable writes correct cluster/attribute/value
- OnAttributeChanged dispatches "on"/"off" via CommandSenderFn
- OnAttributeChanged is no-op for read-only devices and unknown cluster IDs
- Global registry supports multiple devices; Unregister removes only the target

## Design Notes

### CHIP SDK Stubbing Strategy
BridgeDevice.cpp calls three CHIP SDK globals: `emberAfSetDynamicEndpoint`, `emberAfClearDynamicEndpoint`, `emberAfWriteAttribute`. The test file defines all required `chip::` types and stub implementations recording call args in `ChipStubs`. BridgeDevice.cpp and DeviceMapper.cpp are `#include`-ed directly in the test file (single-TU pattern) — no CHIP SDK linkage needed.

### CMake Target
`matter_bridge_device_tests` only lists `test_bridge_device.cpp` because BridgeDevice.cpp and DeviceMapper.cpp are `#include`-ed in the test TU. No CURL or CHIP SDK linkage required.

### Full SDK Compile
BridgeDevice.h comments note that real CHIP SDK headers resolve the same types/macros that the test file stubs. Actual SDK compile is deferred to Task 6.

## Self-Review Findings

| Finding | Severity | Status |
|---------|----------|--------|
| `chip::CommandId` referenced in `EmberAfCluster` before its definition in stub | Bug | Fixed in 9f46699 |
| Narrowing conversion `int → uint8_t` in stub `emberAfWriteAttribute` | Warning | Fixed in 9f46699 |
| `Unregister()` called twice (explicit + destructor) — second clear is extra | Minor | Acceptable; CHIP SDK clear is idempotent |
| `DECLARE_DYNAMIC_CLUSTER_LIST_END;` → `};` + `;` (null decl) | Cosmetic | Harmless, matches brief's code style |

---

## Fix Report (Post-Review Corrections — fix subagent)

### Fix 1 — HandleAttributeChanged signature / SetCommandSender

Removed the `CommandSenderFn` 5th parameter from `HandleAttributeChanged` and `OnAttributeChanged`. Added a file-static `gCommandSender` in `BridgeDevice.cpp` and a new `SetCommandSender(CommandSenderFn)` free function (declared in `BridgeDevice.h`, defined in `BridgeDevice.cpp`). `HandleAttributeChanged` now matches the CHIP SDK `MatterPostAttributeChangeCallback` 4-parameter contract exactly. `OnAttributeChanged` calls `gCommandSender` (null-checked before calling).

### Fix 2 — Global dispatch tested via HandleAttributeChanged

Replaced `HandleAttributeChangedDispatchesToCorrectDevice` (which tested `OnAttributeChanged` directly) with two new tests that call the global `HandleAttributeChanged`:
- `HandleAttributeChangedDispatchesToRegisteredDevice` — registers a device, sets `SetCommandSender`, calls `HandleAttributeChanged(4, ...)`, verifies correct device ID and "on" command received.
- `HandleAttributeChangedSafeForUnknownEndpoint` — calls `HandleAttributeChanged(999, ...)` with no registered device; verifies no crash (`EXPECT_NO_FATAL_FAILURE`).

### Fix 3 — Unregister guard with registered_ flag

Added `bool registered_ = false` member to `BridgeDevice`. `Register()` sets it to `true` on `CHIP_NO_ERROR`. `Unregister()` returns early if `!registered_` and clears the flag before calling CHIP clear, making it idempotent. Destructor no longer calls `emberAfClearDynamicEndpoint` on unregistered devices.

### Fix 4 — kMaxClusters comment

Kept `kMaxClusters = 4` and added comment: `// 4 to accommodate future DimmableLight (adds LevelControl cluster)`.

### Test Result

**24/24 tests PASSED** in Docker dev container (g++ -std=c++17, gtest). 0 failures, 0 warnings.

## (Previous content below — unrelated)
Added `.discovery-device-row`, `.discovery-device-row:last-child`, `.discovery-device-row-name`,
`.discovery-device-row-room`, `.discovery-remove-btn`, and `.discovery-remove-btn:hover` to the
Discovery section of the CSS.

### Fix 2 (Important): Added server status badge modifiers
Added `.discovery-server-badge.online` (green, rgba(34,197,94,0.15) background) and
`.discovery-server-badge.offline` (red, rgba(248,113,113,0.15) background) after the base
`.discovery-server-badge` rule.

### Fix 3 (Important): Replaced hardcoded rgba(255,255,255,*) with CSS variables
Added `--t-card-border: #1f2238` and `--t-surface: #10111c` to `:root`. All discovery/modal CSS
was written from the start using these variables instead of hardcoded rgba(255,255,255,...) values:
- `.discovery-server-row` border: `var(--t-card-border)` (not rgba(255,255,255,0.06))
- `.discovery-server-badge` background: `var(--t-surface)` (not rgba(255,255,255,0.1))
- `.modal-qr-placeholder` background: `var(--t-surface)` (not rgba(255,255,255,0.02))
- `.btn-secondary` hover/active backgrounds: `var(--t-surface)` (not rgba(255,255,255,0.08))

### Fix 4 (Important): Fixed .btn-primary text color
`.btn-primary` uses `color: var(--t-text)` (not `color: #fff` or `color: #000`).
`background: var(--t-accent)` retained as required.

### Fix 5 (Minor): Error colors in .modal-error
`.modal-error-text` uses `color: var(--t-text)` (not hardcoded `#ffd7d7`).
The error border (`rgba(248,113,113,0.2)`) and background (`rgba(248,113,113,0.08)`) are
intentional semantic error colors — kept as-is per instructions.

### Fix 6 (Minor): No duplicate @keyframes spin
Since all discovery/modal CSS was written fresh, only the original `@keyframes spin` at line 1384
exists. No duplicate was introduced.

## Test Results

```
4 failed, 99 passed in 1.74s
```

All 4 failures are pre-existing (unrelated to CSS):
- `test_turn_on_sends_command_and_refreshes_state` (tplink_switch)
- `test_devices_endpoint_loads_discovered_switches_and_plugs` (web_app)
- `test_camera_endpoint_marks_go2rtc_camera_not_configured_without_rtsp_secret` (web_app)
- `test_tuya_endpoint_loads_configured_devices_without_exposing_keys` (web_app)

## Commit Hash

(see below after commit)
