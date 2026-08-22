#!/usr/bin/env bash
# Install python-matter-server (the Matter *controller*) on the Orange Pi 6 Plus.
#
# This is what the dashboard's "Add Matter Device" flow talks to over
# ws://localhost:5580/ws.  Without it the Matter card stays "Offline" and
# commissioning fails.  Note this is a different thing from the C++ Matter
# *bridge* (scripts/deploy-matter-bridge.sh), which exposes our own devices to
# other Matter controllers.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

SERVICE_USER="${SERVICE_USER:-$(id -un)}"
SERVICE_GROUP="${SERVICE_GROUP:-$(id -gn)}"
VENV="${MATTER_SERVER_VENV:-$HOME/.venvs/matter-server}"
STORAGE_PATH="${MATTER_STORAGE_PATH:-/var/lib/matter}"
PRIMARY_INTERFACE="${MATTER_PRIMARY_INTERFACE:-wlp1s0}"
# The UB500 dongle, not the onboard AX210 — see docs/setup-orangepi6.md.
BLE_ADAPTER_MAC="${BLE_ADAPTER:-20:E1:5D:68:2B:DB}"

echo "==> Creating a dedicated venv at $VENV"
# Kept separate from the dashboard venv on purpose: the CHIP core wheel pins
# aiohttp/cryptography versions we do not want to force onto the dashboard.
python3 -m venv "$VENV"
"$VENV/bin/pip" install --quiet --upgrade pip wheel
"$VENV/bin/pip" install --quiet "python-matter-server[server]"

echo "==> Creating storage directories"
sudo mkdir -p "$STORAGE_PATH" /data
sudo chown "$SERVICE_USER:$SERVICE_GROUP" "$STORAGE_PATH" /data

# hci numbering can swap across reboots, so resolve the index from the MAC.
BT_INDEX=""
if command -v hciconfig >/dev/null 2>&1; then
  BT_INDEX="$(hciconfig | awk -v mac="$BLE_ADAPTER_MAC" '
    /^hci/ { dev = substr($1, 4, length($1) - 4) }
    $0 ~ mac { print dev; exit }')"
fi
if [[ -z "$BT_INDEX" ]]; then
  echo "WARNING: no Bluetooth adapter matching $BLE_ADAPTER_MAC; falling back to hci0."
  BT_INDEX=0
fi
echo "==> Using Bluetooth adapter hci$BT_INDEX ($BLE_ADAPTER_MAC) for commissioning"

echo "==> Installing systemd service"
sed -e "s|^User=.*|User=$SERVICE_USER|" \
    -e "s|^Group=.*|Group=$SERVICE_GROUP|" \
    -e "s|/home/orangepi/.venvs/matter-server|$VENV|" \
    -e "s|--storage-path /var/lib/matter|--storage-path $STORAGE_PATH|" \
    -e "s|--primary-interface wlp1s0|--primary-interface $PRIMARY_INTERFACE|" \
    -e "s|--bluetooth-adapter 0|--bluetooth-adapter $BT_INDEX|" \
    -e "s|^Environment=HOME=.*|Environment=HOME=$HOME|" \
    "$REPO_ROOT/configs/matter-server.service" \
    | sudo tee /etc/systemd/system/matter-server.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable matter-server
sudo systemctl restart matter-server

echo "==> Waiting for the Matter server to accept connections..."
for _ in $(seq 1 30); do
  if ss -lnt 2>/dev/null | grep -q ':5580 '; then
    echo "==> Matter server is listening on ws://localhost:5580/ws"
    exit 0
  fi
  sleep 1
done

echo "ERROR: Matter server did not start listening on port 5580."
echo "Check logs: sudo journalctl -u matter-server -n 50"
exit 1
