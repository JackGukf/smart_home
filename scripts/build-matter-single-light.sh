#!/usr/bin/env bash
# Cross-compile a minimal one-switch Matter On/Off light accessory for Raspberry Pi 4.
set -e

PROJECT_ROOT="$(git rev-parse --show-toplevel)"
CHIP_DIR="$PROJECT_ROOT/third_party/connectedhomeip"
SINGLE_SRC="$PROJECT_ROOT/src/cpp/matter_single_light"
BRIDGE_SRC="$PROJECT_ROOT/src/cpp/matter_bridge"
CHIP_LIGHT_DIR="$CHIP_DIR/examples/lighting-app/linux"
OUT_DIR="${OUT_DIR:-$PROJECT_ROOT/build/matter-bridge}"
TARGET_CPU="${TARGET_CPU:-arm64}"
STRIP_TOOL="${STRIP_TOOL:-aarch64-linux-gnu-strip}"

cleanup() {
  git -C "$CHIP_DIR" checkout -- examples/lighting-app/linux/main.cpp examples/lighting-app/linux/BUILD.gn examples/lighting-app/linux/include/CHIPProjectAppConfig.h examples/lighting-app/lighting-common/lighting-app.zap examples/lighting-app/lighting-common/lighting-app.matter >/dev/null 2>&1 || true
  rm -f "$CHIP_LIGHT_DIR/SyncClient.cpp" "$CHIP_LIGHT_DIR/SyncClient.h"
}
trap cleanup EXIT

echo "==> Activating CHIP SDK tools..."
pushd "$CHIP_DIR" >/dev/null
# shellcheck source=/dev/null
source scripts/activate.sh
popd >/dev/null

export ZAP_INSTALL_PATH="$CHIP_DIR/.environment/cipd/packages/zap"

echo "==> Copying single-light source into CHIP SDK lighting example..."
cp "$SINGLE_SRC/main.cpp" "$CHIP_LIGHT_DIR/main.cpp"
cp "$BRIDGE_SRC/SyncClient.cpp" "$CHIP_LIGHT_DIR/SyncClient.cpp"
cp "$BRIDGE_SRC/SyncClient.h" "$CHIP_LIGHT_DIR/SyncClient.h"
cp "$CHIP_DIR/examples/lighting-app/nxp/zap/lighting-on-off.zap" "$CHIP_DIR/examples/lighting-app/lighting-common/lighting-app.zap"
cp "$CHIP_DIR/examples/lighting-app/nxp/zap/lighting-on-off.matter" "$CHIP_DIR/examples/lighting-app/lighting-common/lighting-app.matter"
python3 - <<'PY'
import json
from pathlib import Path
p = Path("third_party/connectedhomeip/examples/lighting-app/lighting-common/lighting-app.zap")
s = p.read_text().replace("../../../../src/app/zap-templates", "../../../src/app/zap-templates")
data = json.loads(s)
for endpoint_type in data.get("endpointTypes", []):
    if endpoint_type.get("deviceTypeCode") == 256:
        endpoint_type["clusters"] = [cluster for cluster in endpoint_type.get("clusters", []) if cluster.get("code") != 8]
p.write_text(json.dumps(data, indent=2))
PY
CHIP_LIGHT_DIR="$CHIP_LIGHT_DIR" python3 - <<'PY'
import os
from pathlib import Path
p = Path(os.environ["CHIP_LIGHT_DIR"]) / "include" / "CHIPProjectAppConfig.h"
s = p.read_text()
s = s.replace('#define CHIP_DEVICE_CONFIG_DEVICE_NAME "Test Bulb"', '#define CHIP_DEVICE_CONFIG_DEVICE_NAME "Living room light switch 2"')
p.write_text(s)
PY

BUILD_GN="$CHIP_LIGHT_DIR/BUILD.gn"
cat > "$BUILD_GN" <<'BUILDGN'
import("//build_overrides/chip.gni")
import("${chip_root}/build/chip/tools.gni")

assert(chip_build_tools)

executable("chip-lighting-app") {
  libs = [ "curl" ]
  sources = [
    "SyncClient.cpp",
    "include/CHIPProjectAppConfig.h",
    "main.cpp",
  ]

  deps = [
    "${chip_root}/examples/lighting-app/lighting-common",
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
  deps = [ ":chip-lighting-app" ]
}

group("default") {
  deps = [ ":chip-lighting-app" ]
}
BUILDGN

echo "==> Symlinking curl headers into chip-cross include path..."
sudo mkdir -p /usr/local/include/chip-cross/curl
for f in /usr/include/x86_64-linux-gnu/curl/*.h; do
  sudo ln -sf "$f" "/usr/local/include/chip-cross/curl/$(basename "$f")"
done

echo "==> Running GN build for linux-arm64 single-light accessory..."
mkdir -p "$OUT_DIR"
pushd "$CHIP_DIR" >/dev/null
scripts/examples/gn_build_example.sh   "$CHIP_LIGHT_DIR"   "$OUT_DIR"   "target_cpu=\"$TARGET_CPU\""   'chip_mdns="minimal"'   'chip_inet_config_enable_ipv4=true'   'is_debug=false'
popd >/dev/null

echo "==> Installing binary as $OUT_DIR/chip-bridge-app for existing Pi container mount..."
mv "$OUT_DIR/chip-lighting-app" "$OUT_DIR/chip-bridge-app"
"$STRIP_TOOL" "$OUT_DIR/chip-bridge-app"
ls -lh "$OUT_DIR/chip-bridge-app"
