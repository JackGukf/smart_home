#!/usr/bin/env bash
set -euo pipefail

PI_USER="${SUDO_USER:-${USER}}"
PI_HOME="$(getent passwd "${PI_USER}" | cut -d: -f6)"
HA_CONFIG_DIR="${PI_HOME}/homeassistant-config"
TZ_VALUE="${TZ:-America/Vancouver}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this script with sudo:"
  echo "  sudo bash $0"
  exit 1
fi

echo "Installing Docker packages..."
apt-get update
apt-get install -y docker.io ca-certificates curl

echo "Enabling Docker service..."
systemctl enable --now docker

echo "Adding ${PI_USER} to docker group..."
usermod -aG docker "${PI_USER}"

echo "Preparing Home Assistant config directory at ${HA_CONFIG_DIR}..."
mkdir -p "${HA_CONFIG_DIR}"
chown -R "${PI_USER}:${PI_USER}" "${HA_CONFIG_DIR}"

echo "Starting Home Assistant container..."
docker rm -f homeassistant >/dev/null 2>&1 || true
docker pull ghcr.io/home-assistant/home-assistant:stable
docker run -d \
  --name homeassistant \
  --privileged \
  --cap-add NET_ADMIN \
  --cap-add NET_RAW \
  --restart unless-stopped \
  --network host \
  -e TZ="${TZ_VALUE}" \
  -v "${HA_CONFIG_DIR}:/config" \
  ghcr.io/home-assistant/home-assistant:stable

echo
echo "Home Assistant is starting. It can take a few minutes on first boot."
echo "Open: http://$(hostname -I | awk '{print $1}'):8123"
echo
echo "Log out and back in, or run 'newgrp docker', before using docker without sudo as ${PI_USER}."
