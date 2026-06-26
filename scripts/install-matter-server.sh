#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

echo "==> Installing python-matter-server on the Pi..."
pip install --user --break-system-packages "python-matter-server[server]"

echo "==> Creating Matter storage directory..."
sudo mkdir -p /var/lib/matter
sudo chown smarthome:smarthome /var/lib/matter

echo "==> Creating /data directory required by CHIP SDK..."
sudo mkdir -p /data
sudo chown smarthome:smarthome /data

echo "==> Installing systemd service..."
sudo cp "$REPO_ROOT/configs/matter-server.service" /etc/systemd/system/matter-server.service
sudo systemctl daemon-reload
sudo systemctl enable matter-server
sudo systemctl start matter-server

echo "==> Waiting for Matter server to start..."
sleep 3
if systemctl is-active --quiet matter-server; then
  echo "==> Matter server is running at ws://localhost:5580/ws"
else
  echo "ERROR: Matter server failed to start."
  echo "Check logs: sudo journalctl -u matter-server -n 50"
  exit 1
fi
