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

# Temporarily patch the CHIP SDK bridge example to include our sources.
# We restore the original BUILD.gn after the build to keep the submodule clean.
echo "==> Copying bridge source files into CHIP SDK bridge example..."
cp "$BRIDGE_SRC/BridgeDevice.h"   "$CHIP_BRIDGE_DIR/"
cp "$BRIDGE_SRC/BridgeDevice.cpp" "$CHIP_BRIDGE_DIR/"
cp "$BRIDGE_SRC/DeviceMapper.h"   "$CHIP_BRIDGE_DIR/"
cp "$BRIDGE_SRC/DeviceMapper.cpp" "$CHIP_BRIDGE_DIR/"
cp "$BRIDGE_SRC/SyncClient.h"     "$CHIP_BRIDGE_DIR/"
cp "$BRIDGE_SRC/SyncClient.cpp"   "$CHIP_BRIDGE_DIR/"
cp "$BRIDGE_SRC/main.cpp"         "$CHIP_BRIDGE_DIR/"

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

echo "==> Symlinking curl headers into chip-cross include path..."
sudo mkdir -p /usr/local/include/chip-cross/curl
for f in /usr/include/x86_64-linux-gnu/curl/*.h; do
  sudo ln -sf "$f" "/usr/local/include/chip-cross/curl/$(basename "$f")"
done

echo "==> Running GN build for linux-arm64..."
mkdir -p "$OUT_DIR"
"$CHIP_DIR/scripts/examples/gn_build_example.sh" \
  "$CHIP_BRIDGE_DIR" \
  "$OUT_DIR" \
  'target_cpu="arm64"' \
  'chip_mdns="minimal"' \
  'chip_inet_config_enable_ipv4=true' \
  'is_debug=false'

echo "==> Stripping binary..."
aarch64-linux-gnu-strip "$OUT_DIR/chip-bridge-app"

# Restore CHIP SDK to clean state (we patched BUILD.gn)
git -C third_party/connectedhomeip checkout -- examples/bridge-app/linux/BUILD.gn

echo "==> Done: $OUT_DIR/chip-bridge-app"
ls -lh "$OUT_DIR/chip-bridge-app"
