#!/usr/bin/env bash
# One-time setup for a new Pi using Docker deployment.
# Run from the repository root after cloning and copying configs.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$REPO_ROOT"

echo "==> Checking prerequisites..."
if ! command -v docker &>/dev/null; then
  echo "ERROR: docker is not installed."
  echo "Install it with: curl -fsSL https://get.docker.com | sh"
  echo "Then add yourself to the docker group: sudo usermod -aG docker \$USER"
  exit 1
fi
if ! docker compose version &>/dev/null; then
  echo "==> Installing docker compose plugin (no sudo required)..."
  DOCKER_CONFIG="${DOCKER_CONFIG:-$HOME/.docker}"
  mkdir -p "$DOCKER_CONFIG/cli-plugins"
  curl -fsSL "https://github.com/docker/compose/releases/download/v2.29.7/docker-compose-linux-aarch64" \
    -o "$DOCKER_CONFIG/cli-plugins/docker-compose"
  chmod +x "$DOCKER_CONFIG/cli-plugins/docker-compose"
  if ! docker compose version &>/dev/null; then
    echo "ERROR: docker compose install failed — check your internet connection."
    exit 1
  fi
  echo "    docker compose $(docker compose version --short) installed."
fi
if [[ ! -f configs/devices.local.yaml ]]; then
  echo "ERROR: configs/devices.local.yaml not found."
  echo "Copy it from your existing Pi:"
  echo "  scp smarthome@<old-pi>:~/smart-home-rpi4/configs/devices.local.yaml configs/"
  exit 1
fi

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example."
  echo "Edit it with your secrets, then re-run this script:"
  echo "  nano .env"
  exit 1
fi

echo "==> Generating go2rtc config..."
python3 scripts/generate-go2rtc-config.py

echo "==> Pulling images..."
docker compose -f docker-compose.pi.yml pull matter-server go2rtc

echo "==> Building dashboard image..."
docker compose -f docker-compose.pi.yml build dashboard

echo "==> Starting services..."
docker compose -f docker-compose.pi.yml up -d

echo ""
echo "==> Done. Services running:"
docker compose -f docker-compose.pi.yml ps

PI_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")
echo ""
echo "Dashboard: http://${PI_IP}:8000"
