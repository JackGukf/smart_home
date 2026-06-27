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
