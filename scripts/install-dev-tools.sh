#!/usr/bin/env bash
set -euo pipefail

sudo apt update
sudo apt install -y \
  build-essential \
  cmake \
  gdb \
  git \
  make \
  ninja-build \
  pkg-config \
  python3 \
  python3-pip \
  python3-venv \
  python3-dev \
  mosquitto \
  mosquitto-clients

python3 -m venv "$HOME/workspace/smart-home-rpi4/src/python/.venv"
"$HOME/workspace/smart-home-rpi4/src/python/.venv/bin/pip" install --upgrade pip

if [ -f "$HOME/workspace/smart-home-rpi4/src/python/requirements.txt" ]; then
  "$HOME/workspace/smart-home-rpi4/src/python/.venv/bin/pip" install -r "$HOME/workspace/smart-home-rpi4/src/python/requirements.txt"
fi

echo "Development tools installed."
echo "Project path: $HOME/workspace/smart-home-rpi4"
