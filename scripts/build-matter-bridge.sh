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
CHIP_REPORTING_ENGINE_CPP="$CHIP_DIR/src/app/reporting/Engine.cpp"

cleanup() {
  git -C "$CHIP_DIR" checkout -- \
    examples/bridge-app/linux/BUILD.gn \
    examples/bridge-app/linux/main.cpp \
    examples/bridge-app/bridge-common/bridge-app.zap \
    src/app/reporting/Engine.cpp >/dev/null 2>&1 || true
  rm -f \
    "$CHIP_BRIDGE_DIR/BridgeDevice.cpp" \
    "$CHIP_BRIDGE_DIR/BridgeDevice.h" \
    "$CHIP_BRIDGE_DIR/CHIPProjectAppConfig.h" \
    "$CHIP_BRIDGE_DIR/include/CHIPProjectAppConfig.h" \
    "$CHIP_BRIDGE_DIR/include/CHIPProjectConfig.h" \
    "$CHIP_BRIDGE_DIR/DeviceMapper.cpp" \
    "$CHIP_BRIDGE_DIR/DeviceMapper.h" \
    "$CHIP_BRIDGE_DIR/SyncClient.cpp" \
    "$CHIP_BRIDGE_DIR/SyncClient.h" \
    "$CHIP_BRIDGE_DIR/include/SystemProjectConfig.h"
}
trap cleanup EXIT

echo "==> Activating CHIP SDK tools..."
# CHIP's activate.sh is a symlink to scripts/setup/bootstrap.sh and expects
# paths relative to the connectedhomeip checkout.
pushd "$CHIP_DIR" >/dev/null
# shellcheck source=/dev/null
source scripts/activate.sh
popd >/dev/null

# zap-cli lives in CIPD; activate.sh doesn't add it to PATH
export ZAP_INSTALL_PATH="$CHIP_DIR/.environment/cipd/packages/zap"

# Temporarily patch the CHIP SDK bridge example to include our sources.
# We restore the original BUILD.gn after the build to keep the submodule clean.
echo "==> Copying bridge source files into CHIP SDK bridge example..."
cp "$BRIDGE_SRC/BridgeDevice.h"      "$CHIP_BRIDGE_DIR/"
cp "$BRIDGE_SRC/BridgeDevice.cpp"    "$CHIP_BRIDGE_DIR/"
cp "$BRIDGE_SRC/DeviceMapper.h"      "$CHIP_BRIDGE_DIR/"
cp "$BRIDGE_SRC/DeviceMapper.cpp"    "$CHIP_BRIDGE_DIR/"
cp "$BRIDGE_SRC/SyncClient.h"        "$CHIP_BRIDGE_DIR/"
cp "$BRIDGE_SRC/SyncClient.cpp"      "$CHIP_BRIDGE_DIR/"
cp "$BRIDGE_SRC/main.cpp"            "$CHIP_BRIDGE_DIR/"
cp "$BRIDGE_SRC/CHIPProjectConfig.h"    "$CHIP_BRIDGE_DIR/include/"
cp "$BRIDGE_SRC/SystemProjectConfig.h" "$CHIP_BRIDGE_DIR/include/"
cp "$BRIDGE_SRC/CHIPProjectAppConfig.h" "$CHIP_BRIDGE_DIR/"
cp "$BRIDGE_SRC/CHIPProjectAppConfig.h" "$CHIP_BRIDGE_DIR/include/"

echo "==> Writing bridge-app BUILD.gn with custom sources, libcurl and -fexceptions..."
BUILD_GN="$CHIP_BRIDGE_DIR/BUILD.gn"
cat > "$BUILD_GN" <<'BUILDGN'
# Copyright (c) 2021 Project CHIP Authors
# Licensed under the Apache License, Version 2.0

import("//build_overrides/chip.gni")
import("${chip_root}/build/chip/tools.gni")

assert(chip_build_tools)

executable("chip-bridge-app") {
  libs = [ "curl" ]
  sources = [
    "BridgeDevice.cpp",
    "DeviceMapper.cpp",
    "SyncClient.cpp",
    "${chip_root}/examples/bridge-app/linux/bridged-actions-stub.cpp",
    "CHIPProjectAppConfig.h",
    "Device.cpp",
    "include/Device.h",
    "include/main.h",
    "main.cpp",
  ]

  deps = [
    "${chip_root}/examples/bridge-app/bridge-common",
    "${chip_root}/examples/platform/linux:app-main",
    "${chip_root}/src/lib",
  ]

  cflags = [ "-Wconversion" ]
  cflags_cc = [ "-fexceptions" ]

  include_dirs = [
    ".",
    "include",
    "/usr/local/include/chip-cross",
  ]

  output_dir = root_out_dir
}

group("linux") {
  deps = [ ":chip-bridge-app" ]
}

group("default") {
  deps = [ ":chip-bridge-app" ]
}
BUILDGN

echo "==> Pruning bridge ZAP model for Apple Home subscription stability..."
python3 - <<'PY'
import json
from pathlib import Path

p = Path("third_party/connectedhomeip/examples/bridge-app/bridge-common/bridge-app.zap")
data = json.loads(p.read_text())

ROOT_CLUSTERS = {29, 31, 40, 48, 49, 60, 62, 63}
AGGREGATOR_CLUSTERS = {3, 29}
BASIC_ATTRS = {
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10,
    65528, 65529, 65531, 65532, 65533,
}
OPCREDS_ATTRS = {
    # Exclude NOCs, Fabrics, and TrustedRootCertificates from wildcard reports;
    # Apple Home can otherwise exceed the packet buffer once multiple fabrics exist.
    2, 3, 5,
    65528, 65529, 65531, 65532, 65533,
}

for endpoint_type in data.get("endpointTypes", []):
    device_type = endpoint_type.get("deviceTypeCode")
    clusters = []
    for cluster in endpoint_type.get("clusters", []):
        code = cluster.get("code")
        side = cluster.get("side")
        if device_type == 22:
            if code not in ROOT_CLUSTERS or side != "server":
                continue
            if code == 40:
                cluster = dict(cluster)
                cluster["attributes"] = [
                    attr for attr in cluster.get("attributes", [])
                    if not attr.get("included") or attr.get("code") in BASIC_ATTRS
                ]
            if code == 62:
                cluster = dict(cluster)
                cluster["attributes"] = [
                    attr for attr in cluster.get("attributes", [])
                    if not attr.get("included") or attr.get("code") in OPCREDS_ATTRS
                ]
        elif device_type == 14:
            if code not in AGGREGATOR_CLUSTERS or side != "server":
                continue
        elif device_type == 257:
            continue
        clusters.append(cluster)
    endpoint_type["clusters"] = clusters

data["endpointTypes"] = [
    endpoint_type for endpoint_type in data.get("endpointTypes", [])
    if endpoint_type.get("deviceTypeCode") in (22, 14)
]
data["endpoints"] = [
    endpoint for endpoint in data.get("endpoints", [])
    if endpoint.get("endpointId") in (0, 1)
]

p.write_text(json.dumps(data, indent=2))
PY

echo "==> Bounding CHIP report chunks for Apple Home wildcard subscriptions..."
python3 - <<'PY'
from pathlib import Path

p = Path("third_party/connectedhomeip/src/app/reporting/Engine.cpp")
s = p.read_text()
s = s.replace(
    """#if CONFIG_BUILD_FOR_HOST_UNIT_TEST
        uint32_t attributesRead = 0;
#endif
""",
    """        // Apple Home's bridge wildcard subscription can include large list
        // attributes. Keep ReportData chunks bounded so an oversized wildcard
        // response resumes in the next chunk without turning every attribute
        // into a separate report.
        constexpr uint32_t kMaxAttributesPerReportChunk = 8;
        uint32_t attributesRead = 0;
""",
)
s = s.replace(
    """#if CONFIG_BUILD_FOR_HOST_UNIT_TEST
            attributesRead++;
            if (attributesRead > mMaxAttributesPerChunk)
            {
                ExitNow(err = CHIP_ERROR_BUFFER_TOO_SMALL);
            }
#endif
""",
    """            attributesRead++;
            if (attributesRead > kMaxAttributesPerReportChunk)
            {
                ExitNow(err = CHIP_ERROR_BUFFER_TOO_SMALL);
            }
""",
)
p.write_text(s)
PY

echo "==> Symlinking curl headers into chip-cross include path..."
sudo mkdir -p /usr/local/include/chip-cross/curl
for f in /usr/include/x86_64-linux-gnu/curl/*.h; do
  sudo ln -sf "$f" "/usr/local/include/chip-cross/curl/$(basename "$f")"
done

# CHIPProjectConfig.h is already copied to $CHIP_BRIDGE_DIR above.
# Pass chip_project_config_include so it reaches ALL compilation units
# including src/system (where CHIP_SYSTEM_CONFIG_PACKETBUFFER_POOL_SIZE lives).
# Patching CHIPProjectAppConfig.h does NOT work — that file is app-layer only
# and never included by the system library.

echo "==> Running GN build for linux-arm64..."
mkdir -p "$OUT_DIR"
pushd "$CHIP_DIR" >/dev/null
scripts/examples/gn_build_example.sh \
  "$CHIP_BRIDGE_DIR" \
  "$OUT_DIR" \
  'target_cpu="arm64"' \
  'chip_mdns="minimal"' \
  'chip_inet_config_enable_ipv4=true' \
  'is_debug=false' \
  'chip_project_config_include="<CHIPProjectConfig.h>"' \
  'chip_project_config_include_dirs=["//include"]'
popd >/dev/null

echo "==> Stripping binary..."
aarch64-linux-gnu-strip "$OUT_DIR/chip-bridge-app"

# Restore CHIP SDK to clean state before returning to the workspace.
cleanup
trap - EXIT

echo "==> Done: $OUT_DIR/chip-bridge-app"
ls -lh "$OUT_DIR/chip-bridge-app"
