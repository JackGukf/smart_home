#!/usr/bin/env bash
# Build the Matter bridge for the native host architecture (x86_64).
# Used by integration tests so they can run inside the dev Docker container
# without needing a Raspberry Pi.
#
# Usage (inside dev container):
#   bash scripts/build-matter-bridge-native.sh
#
# Output: build/matter-bridge-native/chip-bridge-app
set -e

PROJECT_ROOT="$(git rev-parse --show-toplevel)"
CHIP_DIR="$PROJECT_ROOT/third_party/connectedhomeip"
BRIDGE_SRC="$PROJECT_ROOT/src/cpp/matter_bridge"
CHIP_BRIDGE_DIR="$CHIP_DIR/examples/bridge-app/linux"
OUT_DIR="$PROJECT_ROOT/build/matter-bridge-native"

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

echo "==> Writing bridge-app BUILD.gn (same as production build)..."
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
    "${chip_root}/examples/tv-app/tv-common/include/CHIPProjectAppConfig.h",
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
    "include",
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

echo "==> Running GN build for native x86_64..."
mkdir -p "$OUT_DIR"
"$CHIP_DIR/scripts/examples/gn_build_example.sh" \
  "$CHIP_BRIDGE_DIR" \
  "$OUT_DIR" \
  'chip_mdns="minimal"' \
  'chip_inet_config_enable_ipv4=true' \
  'is_debug=false'

echo "==> Done: $OUT_DIR/chip-bridge-app"
ls -lh "$OUT_DIR/chip-bridge-app"

# Restore CHIP SDK to clean state
git -C "$PROJECT_ROOT/third_party/connectedhomeip" checkout -- examples/bridge-app/linux/BUILD.gn 2>/dev/null || true
