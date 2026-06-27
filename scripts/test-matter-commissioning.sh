#!/usr/bin/env bash
# Full Matter commissioning integration test using chip-tool.
#
# Starts the native bridge binary, commissions it with chip-tool,
# reads a BasicInformation attribute to confirm commissioning succeeded,
# then cleans up.
#
# Prerequisites (inside dev container after setup-matter-sdk.sh):
#   1. Native bridge binary: build/matter-bridge-native/chip-bridge-app
#      Build it first: bash scripts/build-matter-bridge-native.sh
#   2. chip-tool binary on PATH or at CHIP_TOOL path
#      Build: cd third_party/connectedhomeip && scripts/examples/gn_build_example.sh \
#               examples/chip-tool build/chip-tool
#
# Usage:
#   bash scripts/test-matter-commissioning.sh
#
# Exit code: 0 = pass, 1 = fail
set -euo pipefail

PROJECT_ROOT="$(git rev-parse --show-toplevel)"
BINARY="$PROJECT_ROOT/build/matter-bridge-native/chip-bridge-app"
CHIP_TOOL="${CHIP_TOOL:-$PROJECT_ROOT/build/chip-tool/chip-tool}"
PASSCODE=20202021
DISCRIMINATOR=3840
NODE_ID=1
KVS_DIR="$(mktemp -d)"
CHIP_TOOL_STORAGE="$(mktemp -d)"
BRIDGE_PID=""

cleanup() {
    [[ -n "$BRIDGE_PID" ]] && kill "$BRIDGE_PID" 2>/dev/null || true
    rm -rf "$KVS_DIR" "$CHIP_TOOL_STORAGE"
}
trap cleanup EXIT

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# ── Preflight checks ──────────────────────────────────────────────────────────

[[ -x "$BINARY" ]] || fail "Native bridge binary not found: $BINARY
Run: bash scripts/build-matter-bridge-native.sh"

[[ -x "$CHIP_TOOL" ]] || fail "chip-tool not found at: $CHIP_TOOL
Build it or set CHIP_TOOL env var."

# ── Start bridge ──────────────────────────────────────────────────────────────

echo "==> Starting bridge binary..."
"$BINARY" --KVS "$KVS_DIR/kvs" \
    --passcode "$PASSCODE" \
    --discriminator "$DISCRIMINATOR" \
    > "$KVS_DIR/bridge.log" 2>&1 &
BRIDGE_PID=$!

# Wait for bridge to become commissionable (up to 15s)
for i in $(seq 1 15); do
    if grep -q "Server Listening\|bridge running" "$KVS_DIR/bridge.log" 2>/dev/null; then
        break
    fi
    sleep 1
done
grep -q "Server Listening\|bridge running" "$KVS_DIR/bridge.log" \
    || fail "Bridge did not start within 15 s. Log:
$(cat "$KVS_DIR/bridge.log")"
pass "Bridge started"

# ── Verify no DAC regression ──────────────────────────────────────────────────

if grep -q "CertificateChainRequest.*Not Implemented" "$KVS_DIR/bridge.log"; then
    fail "DAC provider regression: CertificateChainRequest returned Not Implemented at startup.
SetDeviceAttestationCredentialsProvider() must be called in main() after ChipLinuxAppInit()."
fi
pass "DAC provider initialised (no Not-Implemented at startup)"

# ── Commission via chip-tool ──────────────────────────────────────────────────

echo "==> Commissioning with chip-tool (discriminator=$DISCRIMINATOR passcode=$PASSCODE)..."
CHIP_TOOL_CONFIG="$CHIP_TOOL_STORAGE" "$CHIP_TOOL" pairing code "$NODE_ID" \
    "${DISCRIMINATOR}${PASSCODE}" \
    --paa-trust-store-path "$PROJECT_ROOT/third_party/connectedhomeip/credentials/development/paa-root-certs" \
    > "$KVS_DIR/chip-tool.log" 2>&1 \
    || fail "chip-tool commissioning failed. Log:
$(cat "$KVS_DIR/chip-tool.log")"
pass "Commissioned successfully (node $NODE_ID)"

# ── Read BasicInformation attribute to confirm session works ──────────────────

echo "==> Reading VendorID attribute..."
CHIP_TOOL_CONFIG="$CHIP_TOOL_STORAGE" "$CHIP_TOOL" basicinformation read vendor-id "$NODE_ID" 0 \
    > "$KVS_DIR/read.log" 2>&1 \
    || fail "Failed to read VendorID after commissioning. Log:
$(cat "$KVS_DIR/read.log")"
grep -q "0xFFF1\|65521" "$KVS_DIR/read.log" \
    || fail "VendorID response did not contain expected value 0xFFF1 (65521). Log:
$(cat "$KVS_DIR/read.log")"
pass "VendorID = 0xFFF1 — commissioning and attribute read confirmed"

echo ""
echo "All Matter commissioning tests passed."
