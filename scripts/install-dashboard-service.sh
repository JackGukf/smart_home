#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/home/smarthome/smart-home-rpi4}"
RUN_USER="$(id -un)"
USER_HOME="$(getent passwd "${RUN_USER}" | cut -d: -f6)"
SERVICE_NAMES=(
  "go2rtc.service"
  "smart-home-dashboard.service"
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

systemctl --user daemon-reload
for service_name in "${SERVICE_NAMES[@]}"; do
  systemctl --user enable "${service_name}"
done

systemctl --user stop smart-home-dashboard.service 2>/dev/null || true
if pgrep -u "$(id -u)" -f "uvicorn src.python.web_app:app.*--port 8000" >/dev/null; then
  pkill -u "$(id -u)" -f "uvicorn src.python.web_app:app.*--port 8000"
fi

for service_name in "${SERVICE_NAMES[@]}"; do
  systemctl --user restart "${service_name}"
  systemctl --user --no-pager --full status "${service_name}"
done
