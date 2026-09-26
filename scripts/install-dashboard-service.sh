#!/usr/bin/env bash
set -euo pipefail

# Default to the checkout this script was deployed into, so the install works on
# any board/user without the project path being baked in.
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
RUN_USER="$(id -un)"
USER_HOME="$(getent passwd "${RUN_USER}" | cut -d: -f6)"
SERVICE_NAMES=(
  "go2rtc.service"
  "smart-home-dashboard.service"
  "house-memory.service"
)
# Scheduled jobs: installed and their timers enabled, but never restarted by a
# deploy - that would run the job on every commit.
TIMER_UNITS=(
  "house-learning.service"
  "house-learning.timer"
)
# Installed so the Settings switch can start them, but never enabled or started
# here: they are off until somebody turns them on. A deploy restarts one only if
# it is already running, to pick up new code.
OPTIONAL_UNITS=(
  "dashboard-cast.service"
)

if [[ -z "${USER_HOME}" || ! -d "${USER_HOME}" ]]; then
  echo "ERROR: could not resolve home directory for ${RUN_USER}" >&2
  exit 1
fi

export HOME="${USER_HOME}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"

UNIT_TARGET_DIR="${USER_HOME}/.config/systemd/user"
mkdir -p "${UNIT_TARGET_DIR}"
chmod +x "${PROJECT_ROOT}/scripts/run-dashboard.sh"
chmod +x "${PROJECT_ROOT}/scripts/run-go2rtc.sh"

for service_name in "${SERVICE_NAMES[@]}"; do
  unit_source="${PROJECT_ROOT}/deploy/systemd/user/${service_name}"
  unit_target="${UNIT_TARGET_DIR}/${service_name}"
  if [[ ! -f "${unit_source}" ]]; then
    echo "ERROR: missing ${unit_source}" >&2
    exit 1
  fi
  install -m 0644 "${unit_source}" "${unit_target}"
done

for unit_name in "${TIMER_UNITS[@]}" "${OPTIONAL_UNITS[@]}"; do
  install -m 0644 "${PROJECT_ROOT}/deploy/systemd/user/${unit_name}" "${UNIT_TARGET_DIR}/${unit_name}"
done
chmod +x "${PROJECT_ROOT}/scripts/run-dashboard-cast.sh"
systemctl --user daemon-reload
systemctl --user enable --now house-learning.timer
for service_name in "${SERVICE_NAMES[@]}"; do
  systemctl --user enable "${service_name}"
done

# INSTALL_ONLY=1 (deploy-dashboard.sh --skip-go2rtc, i.e. scripts/deploy.py):
# restarts are the caller's. Restarting all three here on every dashboard deploy
# reconnected every camera (go2rtc) and the house memory for a CSS change -
# found 2026-09-25, after --skip-go2rtc alone left go2rtc restarting anyway.
if [[ "${INSTALL_ONLY:-0}" == "1" ]]; then
  echo "units installed and enabled; restarts left to the caller"
  exit 0
fi

systemctl --user stop smart-home-dashboard.service 2>/dev/null || true
if pgrep -u "$(id -u)" -f "uvicorn src.python.web_app:app.*--port 8000" >/dev/null; then
  pkill -u "$(id -u)" -f "uvicorn src.python.web_app:app.*--port 8000"
fi

for service_name in "${SERVICE_NAMES[@]}"; do
  # The stop above can time out - the dashboard holds SSE streams open - and a
  # unit killed on a timed-out stop is left `failed`. Clear that first: a restart
  # from `failed` is fine, but the state persists otherwise and the next deploy
  # inherits it.
  systemctl --user reset-failed "${service_name}" 2>/dev/null || true
  systemctl --user restart "${service_name}"
  systemctl --user --no-pager --full status "${service_name}"
done

for unit_name in "${OPTIONAL_UNITS[@]}"; do
  systemctl --user try-restart "${unit_name}" || true
done
