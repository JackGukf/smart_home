#!/usr/bin/env bash
# Deploy the Matter bridge binary and Docker image to the Raspberry Pi.
#
# Requires:
#   PI_HOST env var — Pi IP address or hostname (default: raspberrypi.local)
#   PI_USER env var — SSH username (default: smarthome, matching deploy-to-pi.sh)
#
# Usage:
#   PI_HOST=192.168.1.5 bash scripts/deploy-matter-bridge.sh
#   PI_HOST=192.168.1.5 SKIP_BUILD=1 bash scripts/deploy-matter-bridge.sh
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PI_HOST="${PI_HOST:-raspberrypi.local}"
PI_USER="${PI_USER:-smarthome}"
REMOTE="${PI_USER}@${PI_HOST}"
REMOTE_DIR="${REMOTE_PATH:-/home/${PI_USER}/smart-home-rpi4}"
SKIP_BUILD="${SKIP_BUILD:-0}"
BINARY="$PROJECT_ROOT/build/matter-bridge/chip-bridge-app"

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
# 2. Sync the binary + Docker assets to the Pi
# --------------------------------------------------------------------------- #
echo "==> Syncing project files to ${REMOTE}:${REMOTE_DIR} ..."
rsync -avz --progress \
    --exclude='.git' \
    --exclude='third_party/' \
    --exclude='build/docker-debug' \
    --exclude='build/rpi4-release' \
    --exclude='build/dev-check' \
    --exclude='build/matter-bridge' \
    "$PROJECT_ROOT/" \
    "${REMOTE}:${REMOTE_DIR}/"

# Sync only the Matter bridge binary to avoid sending hundreds of MB of CHIP SDK artifacts
echo "==> Syncing Matter bridge binary..."
rsync -avz --progress \
    "$BINARY" \
    "${REMOTE}:${REMOTE_DIR}/build/matter-bridge/"

# --------------------------------------------------------------------------- #
# 3. Build Docker image on the Pi and (re)start the container
# --------------------------------------------------------------------------- #
echo "==> Building and starting matter-bridge container on Pi..."
ssh "${REMOTE}" bash -s <<EOF
set -euo pipefail
cd "${REMOTE_DIR}"
docker compose -f docker-compose.pi.yml build matter-bridge
docker compose -f docker-compose.pi.yml up -d matter-bridge
EOF

# --------------------------------------------------------------------------- #
# 4. Tail logs to confirm startup
# --------------------------------------------------------------------------- #
echo "==> Done. Recent logs:"
ssh "${REMOTE}" "docker logs --tail=20 matter-bridge"
