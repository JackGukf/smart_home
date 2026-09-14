#!/usr/bin/env bash
#
# Install and start the Voice Panel's camera relay. Run it ON the Orange Pi:
#
#   cd smart_home_AI && ./scripts/install-panel-camera.sh
#
# Then check it:  curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:1985/camera/front_door_camera.jpg
# (503 on the very first request while ffmpeg starts, 200 a second later.)
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_DIR="${HOME}/.config/systemd/user"
SERVICE="panel-camera.service"

command -v ffmpeg >/dev/null || { echo "ffmpeg is required: sudo apt install ffmpeg" >&2; exit 1; }
"${PROJECT_ROOT}/.venv/bin/python" -c "import aiohttp" 2>/dev/null \
  || { echo "aiohttp is missing from ${PROJECT_ROOT}/.venv" >&2; exit 1; }

mkdir -p "${UNIT_DIR}"
install -m 644 "${PROJECT_ROOT}/deploy/systemd/user/${SERVICE}" "${UNIT_DIR}/${SERVICE}"
chmod +x "${PROJECT_ROOT}/scripts/run-panel-camera.sh"

systemctl --user daemon-reload
systemctl --user enable "${SERVICE}" >/dev/null 2>&1 || true
systemctl --user reset-failed "${SERVICE}" 2>/dev/null || true
systemctl --user restart "${SERVICE}"
printf '  %-22s %s\n' "${SERVICE}" "$(systemctl --user is-active "${SERVICE}")"
