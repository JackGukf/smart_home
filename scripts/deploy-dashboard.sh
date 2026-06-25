#!/usr/bin/env bash
# Deploy dashboard files to Raspberry Pi and restart the systemd dashboard service.
# Usage: scripts/deploy-dashboard.sh [--host HOST] [--user USER]
set -euo pipefail

PI_HOST="${PI_HOST:-192.168.0.176}"
PI_USER="${PI_USER:-smarthome}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --host)  PI_HOST="$2"; shift 2 ;;
        --user)  PI_USER="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: scripts/deploy-dashboard.sh [--host HOST] [--user USER]"
            exit 0 ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done

PI_TARGET="${PI_USER}@${PI_HOST}"
REMOTE_HOME="/home/${PI_USER}"
REMOTE_PATH="${REMOTE_HOME}/smart-home-rpi4"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> Deploying dashboard to ${PI_TARGET}..."
ssh "${PI_TARGET}" "mkdir -p ${REMOTE_PATH}/src/python ${REMOTE_PATH}/src/python/web_static ${REMOTE_PATH}/deploy/systemd/user ${REMOTE_PATH}/scripts"

rsync --checksum -av \
    "${PROJECT_ROOT}/src/python/"*.py \
    "${PROJECT_ROOT}/src/python/requirements.txt" \
    "${PI_TARGET}:${REMOTE_PATH}/src/python/"

rsync --checksum -av \
    "${PROJECT_ROOT}/src/python/web_static/" \
    "${PI_TARGET}:${REMOTE_PATH}/src/python/web_static/"

rsync --checksum -av \
    "${PROJECT_ROOT}/deploy/systemd/" \
    "${PI_TARGET}:${REMOTE_PATH}/deploy/systemd/"

rsync --checksum -av \
    "${PROJECT_ROOT}/scripts/run-dashboard.sh" \
    "${PROJECT_ROOT}/scripts/run-go2rtc.sh" \
    "${PROJECT_ROOT}/scripts/generate-go2rtc-config.py" \
    "${PROJECT_ROOT}/scripts/install-dashboard-service.sh" \
    "${PROJECT_ROOT}/scripts/discover-govee-ble.py" \
    "${PI_TARGET}:${REMOTE_PATH}/scripts/"

echo "==> Syncing Python dependencies..."
ssh "${PI_TARGET}" "cd ${REMOTE_PATH} && [ -x .venv/bin/pip ] && .venv/bin/pip install -q -r src/python/requirements.txt || true"

echo "==> Installing and restarting smart-home-dashboard.service..."
ssh "${PI_TARGET}" "cd ${REMOTE_PATH} && HOME=${REMOTE_HOME} XDG_RUNTIME_DIR=/run/user/\$(id -u) bash scripts/install-dashboard-service.sh >/tmp/smart-home-dashboard-install.log 2>&1"
ssh "${PI_TARGET}" "HOME=${REMOTE_HOME} XDG_RUNTIME_DIR=/run/user/\$(id -u) systemctl --user restart go2rtc.service && HOME=${REMOTE_HOME} XDG_RUNTIME_DIR=/run/user/\$(id -u) systemctl --user is-active go2rtc.service"
ssh "${PI_TARGET}" "HOME=${REMOTE_HOME} XDG_RUNTIME_DIR=/run/user/\$(id -u) systemctl --user restart smart-home-dashboard.service && HOME=${REMOTE_HOME} XDG_RUNTIME_DIR=/run/user/\$(id -u) systemctl --user is-active smart-home-dashboard.service"

echo "==> Done. Dashboard live at http://${PI_HOST}:8000"
