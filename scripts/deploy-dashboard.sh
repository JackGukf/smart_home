#!/usr/bin/env bash
# Deploy dashboard files to the Orange Pi 6 Plus and restart the systemd
# dashboard service. Pass --host/--user to target a different board (e.g. the
# secondary Raspberry Pi 4 install).
# Usage: scripts/deploy-dashboard.sh [--host HOST] [--user USER] [--remote-path PATH]
set -euo pipefail

PI_HOST="${PI_HOST:-192.168.0.234}"
PI_USER="${PI_USER:-orangepi}"
REMOTE_PATH="${REMOTE_PATH:-}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --host)  PI_HOST="$2"; shift 2 ;;
        --user)  PI_USER="$2"; shift 2 ;;
        --remote-path) REMOTE_PATH="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: scripts/deploy-dashboard.sh [--host HOST] [--user USER] [--remote-path PATH]"
            exit 0 ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done

PI_TARGET="${PI_USER}@${PI_HOST}"
REMOTE_HOME="/home/${PI_USER}"
REMOTE_PATH="${REMOTE_PATH:-${REMOTE_HOME}/smart_home_AI}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

BUILD_COUNT_FILE="${PROJECT_ROOT}/BUILD_COUNT"
PREV_BUILD="$(cat "${BUILD_COUNT_FILE}" 2>/dev/null || echo 0)"
BUILD_NUMBER=$((PREV_BUILD + 1))
echo "${BUILD_NUMBER}" > "${BUILD_COUNT_FILE}"
DEPLOYED_AT="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
printf '{"build": %s, "deployed_at": "%s"}\n' "${BUILD_NUMBER}" "${DEPLOYED_AT}" \
    > "${PROJECT_ROOT}/src/python/web_static/build_info.json"
echo "==> Build #${BUILD_NUMBER}"

# Bust browser cache for app.js/styles.css so clients pick up the new build immediately.
INDEX_FILE="${PROJECT_ROOT}/src/python/web_static/index.html"
sed -i -E "s#(app\.js\?v=)[^\"']*#\1build${BUILD_NUMBER}#" "${INDEX_FILE}"
sed -i -E "s#(styles\.css\?v=)[^\"']*#\1build${BUILD_NUMBER}#" "${INDEX_FILE}"

echo "==> Deploying dashboard to ${PI_TARGET}..."
ssh "${PI_TARGET}" "mkdir -p ${REMOTE_PATH}/src/python ${REMOTE_PATH}/src/python/web_static ${REMOTE_PATH}/deploy/systemd/user ${REMOTE_PATH}/scripts"

rsync --checksum -av \
    "${PROJECT_ROOT}/src/python/"*.py \
    "${PROJECT_ROOT}/src/python/requirements.txt" \
    "${PI_TARGET}:${REMOTE_PATH}/src/python/"

# Ship a compiled app.js, not the source: the dashboard is written in modern
# JavaScript that older browsers cannot even parse. Staged after the cache-bust
# rewrite above so index.html carries this build's version.
STAGE_DIR="$(mktemp -d)"
trap 'rm -rf "${STAGE_DIR}"' EXIT
bash "${PROJECT_ROOT}/scripts/build-dashboard-assets.sh" "${STAGE_DIR}"

rsync --checksum -av \
    "${STAGE_DIR}/" \
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
    "${PROJECT_ROOT}/scripts/discover_tplink_switches.py" \
    "${PROJECT_ROOT}/scripts/check-tplink-credentials.py" \
    "${PI_TARGET}:${REMOTE_PATH}/scripts/"

# The dashboard reads the TP-Link device list from the project root on every
# request, so ship it with the dashboard deploy.
rsync --checksum -av \
    "${PROJECT_ROOT}/tplink_switches.json" \
    "${PI_TARGET}:${REMOTE_PATH}/tplink_switches.json"

echo "==> Syncing Python dependencies..."
ssh "${PI_TARGET}" "cd ${REMOTE_PATH} && [ -x .venv/bin/pip ] && .venv/bin/pip install -q -r src/python/requirements.txt || true"

echo "==> Installing and restarting smart-home-dashboard.service..."
ssh "${PI_TARGET}" "cd ${REMOTE_PATH} && HOME=${REMOTE_HOME} XDG_RUNTIME_DIR=/run/user/\$(id -u) bash scripts/install-dashboard-service.sh >/tmp/smart-home-dashboard-install.log 2>&1"
ssh "${PI_TARGET}" "HOME=${REMOTE_HOME} XDG_RUNTIME_DIR=/run/user/\$(id -u) systemctl --user restart go2rtc.service && HOME=${REMOTE_HOME} XDG_RUNTIME_DIR=/run/user/\$(id -u) systemctl --user is-active go2rtc.service"
ssh "${PI_TARGET}" "HOME=${REMOTE_HOME} XDG_RUNTIME_DIR=/run/user/\$(id -u) systemctl --user restart smart-home-dashboard.service && HOME=${REMOTE_HOME} XDG_RUNTIME_DIR=/run/user/\$(id -u) systemctl --user is-active smart-home-dashboard.service"

echo "==> Done. Dashboard live at http://${PI_HOST}:8000"
