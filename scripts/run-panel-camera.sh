#!/usr/bin/env bash
#
# Run the Voice Panel's camera relay (src/python/panel_camera.py).
#
# It needs aiohttp, which the project's .venv on the board already has, and the
# system ffmpeg. Settings (PANEL_CAMERA_STREAMS, PANEL_CAMERA_PORT, ...) may be
# set in .env beside the rest; the defaults serve front_door_camera on :1985.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PANEL_CAMERA_PYTHON:-${PROJECT_ROOT}/.venv/bin/python}"

[[ -x "${PYTHON}" ]] || { echo "No Python environment at ${PYTHON}" >&2; exit 1; }
command -v ffmpeg >/dev/null || { echo "ffmpeg is not installed" >&2; exit 1; }

if [[ -r "${PROJECT_ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  . "${PROJECT_ROOT}/.env"
  set +a
fi

cd "${PROJECT_ROOT}"
export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH:-}"
exec "${PYTHON}" -m src.python.panel_camera "$@"
