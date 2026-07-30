#!/usr/bin/env bash
# Restart the Matter bridge on the board with a fresh KVS so it opens the
# commissioning window, then print the manual pairing code from the log.
#
# The bridge runs as the systemd user unit matter-bridge.service under
# the orangepi user (see configs/matter-bridge.service).
#
# Requires:
#   PI_HOST env var — board IP address or hostname (default: 192.168.0.234)
#   PI_USER env var — SSH username (default: orangepi)
#
# Usage:
#   bash scripts/recommission-matter-bridge.sh
#   KEEP_KVS=1 bash scripts/recommission-matter-bridge.sh   # restart only, keep fabrics
set -euo pipefail

PI_HOST="${PI_HOST:-192.168.0.234}"
PI_USER="${PI_USER:-orangepi}"
REMOTE="${PI_USER}@${PI_HOST}"
KEEP_KVS="${KEEP_KVS:-0}"

ssh "${REMOTE}" KEEP_KVS="$KEEP_KVS" bash -s <<'EOF'
set -euo pipefail
KVS=~/matter-bridge-kvs/kvs
LOG=~/matter-bridge.log

echo "==> Stopping matter-bridge.service..."
systemctl --user stop matter-bridge.service

if [[ "$KEEP_KVS" != "1" && -f "$KVS" ]]; then
    BAK="$KVS.bak-$(date +%m%d-%H%M)"
    echo "==> Backing up KVS to $BAK (bridge will start uncommissioned)"
    mv "$KVS" "$BAK"
fi

# Note where the log ends so we only search output from this boot
MARK=$(wc -l < "$LOG" 2>/dev/null || echo 0)

echo "==> Starting matter-bridge.service..."
systemctl --user start matter-bridge.service
sleep 5

if ! systemctl --user is-active --quiet matter-bridge.service; then
    echo "ERROR: service failed to start:" >&2
    systemctl --user status matter-bridge.service --no-pager | head -15 >&2
    exit 1
fi

echo "==> Service is running. Commissioning info from this boot:"
tail -n +$((MARK + 1)) "$LOG" | grep -E "Manual pairing code|SetupQRCode|commissioning mode" | head -5 || {
    echo "WARNING: no pairing code in log yet; check: tail ~/matter-bridge.log" >&2
}
EOF

echo
echo "In Apple Home: Add Accessory -> \"More options...\" -> enter the manual pairing code above."
