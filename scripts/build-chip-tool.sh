#!/bin/bash
set -e
set -x

CHIP_ROOT=/workspace/smart-home-rpi4/third_party/connectedhomeip
BUILD_DIR=/workspace/smart-home-rpi4/build/chip-tool-x86

source "$CHIP_ROOT/scripts/activate.sh"

# zap-cli lives in CIPD; activate.sh doesn't add it to PATH
export ZAP_INSTALL_PATH="$CHIP_ROOT/.environment/cipd/packages/zap"

gn gen --check --fail-on-unused-args \
    --root="$CHIP_ROOT/examples/chip-tool" \
    "$BUILD_DIR" \
    '--args=chip_mdns="minimal" chip_inet_config_enable_ipv4=true is_debug=false optimize_for_size=true'

ninja -C "$BUILD_DIR" chip-tool

ls -lh "$BUILD_DIR/chip-tool"
echo "==> Done: $BUILD_DIR/chip-tool"
