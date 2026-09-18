#!/usr/bin/env bash
#
# Cast the dashboard to the TV (src/python/dashboard_cast.py).
#
# Started and stopped by the Cast to TV switch in the dashboard's Settings,
# never by a deploy. It needs the project's .venv (aiohttp, itsdangerous, PyYAML),
# chromium and ffmpeg. Settings (DASHBOARD_CAST_RENDERER, DASHBOARD_CAST_FPS, ...)
# may be set in .env beside the rest.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${DASHBOARD_CAST_PYTHON:-${PROJECT_ROOT}/.venv/bin/python}"

[[ -x "${PYTHON}" ]] || { echo "No Python environment at ${PYTHON}" >&2; exit 1; }
command -v ffmpeg >/dev/null || { echo "ffmpeg is not installed" >&2; exit 1; }
command -v chromium >/dev/null || { echo "chromium is not installed" >&2; exit 1; }

if [[ -r "${PROJECT_ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  . "${PROJECT_ROOT}/.env"
  set +a
fi

cd "${PROJECT_ROOT}"
export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH:-}"
exec "${PYTHON}" -m src.python.dashboard_cast "$@"
