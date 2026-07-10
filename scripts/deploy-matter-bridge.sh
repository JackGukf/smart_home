#!/usr/bin/env bash
# Deploy the Matter bridge binary to the Raspberry Pi as a systemd user unit.
#
# The bridge runs as the systemd *user* service matter-bridge.service
# (configs/matter-bridge.service) under the smarthome user with linger
# enabled. The old Docker deployment path was retired 2026-07-08.
#
# Requires:
#   PI_HOST env var — Pi IP address or hostname (default: raspberrypi.local)
#   PI_USER env var — SSH username (default: smarthome, matching deploy-to-pi.sh)
#
# Usage:
#   PI_HOST=192.168.0.176 bash scripts/deploy-matter-bridge.sh
#   PI_HOST=192.168.0.176 SKIP_BUILD=1 bash scripts/deploy-matter-bridge.sh
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PI_HOST="${PI_HOST:-raspberrypi.local}"
PI_USER="${PI_USER:-smarthome}"
REMOTE="${PI_USER}@${PI_HOST}"
REMOTE_DIR="${REMOTE_PATH:-/home/${PI_USER}/smart-home-rpi4}"
SKIP_BUILD="${SKIP_BUILD:-0}"
BINARY="$PROJECT_ROOT/build/matter-bridge/chip-bridge-app"
UNIT_NAME="matter-bridge.service"

# --------------------------------------------------------------------------- #
# 1. Build the aarch64 binary (unless caller already built it)
# --------------------------------------------------------------------------- #
if [[ "$SKIP_BUILD" != "1" ]]; then
    echo "==> Building Matter bridge binary (aarch64)..."
    "$PROJECT_ROOT/scripts/build-matter-bridge.sh"
fi

if [[ ! -f "$BINARY" ]]; then
    echo "ERROR: binary not found at $BINARY" >&2
    echo "Run scripts/build-matter-bridge.sh first, or set SKIP_BUILD=1 if already built." >&2
    exit 1
fi

# --------------------------------------------------------------------------- #
# 2. Sync the binary and unit file to the Pi
# --------------------------------------------------------------------------- #
echo "==> Syncing Matter bridge binary to ${REMOTE}:${REMOTE_DIR} ..."
ssh "${REMOTE}" "mkdir -p '${REMOTE_DIR}/build/matter-bridge' ~/.config/systemd/user"
rsync -az --progress "$BINARY" "${REMOTE}:${REMOTE_DIR}/build/matter-bridge/"
rsync -az "$PROJECT_ROOT/configs/$UNIT_NAME" "${REMOTE}:.config/systemd/user/$UNIT_NAME"

# --------------------------------------------------------------------------- #
# 3. (Re)start the systemd user unit
# --------------------------------------------------------------------------- #
echo "==> Restarting ${UNIT_NAME} on the Pi..."
ssh "${REMOTE}" bash -s <<'EOF'
set -euo pipefail
systemctl --user daemon-reload
systemctl --user enable matter-bridge.service
systemctl --user restart matter-bridge.service
sleep 3
systemctl --user status matter-bridge.service --no-pager | head -8
EOF

# --------------------------------------------------------------------------- #
# 4. Tail the log to confirm startup
# --------------------------------------------------------------------------- #
echo "==> Done. Recent logs:"
ssh "${REMOTE}" "tail -n 20 ~/matter-bridge.log"
