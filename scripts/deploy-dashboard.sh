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
    "${PROJECT_ROOT}/scripts/house_digest.py" \
    "${PROJECT_ROOT}/scripts/author_automation.py" \
    "${PROJECT_ROOT}/scripts/install-house-digest.sh" \
    "${PROJECT_ROOT}/scripts/setup-ha-ollama.py" \
    "${PROJECT_ROOT}/scripts/check-assist-routing.py" \
    "${PI_TARGET}:${REMOTE_PATH}/scripts/"

# The dashboard reads the TP-Link device list from the project root on every
# request, so ship it with the dashboard deploy.
rsync --checksum -av \
    "${PROJECT_ROOT}/tplink_switches.json" \
    "${PI_TARGET}:${REMOTE_PATH}/tplink_switches.json"

echo "==> Syncing Python dependencies..."
ssh "${PI_TARGET}" "cd ${REMOTE_PATH} && [ -x .venv/bin/pip ] && .venv/bin/pip install -q -r src/python/requirements.txt || true"

SYSTEMCTL="HOME=${REMOTE_HOME} XDG_RUNTIME_DIR=/run/user/\$(id -u) systemctl --user"

# A restart whose stop times out leaves the unit `failed`, and a failed unit does
# not come back by itself - Restart=always covers a crash, not a stop that never
# finished. Deploys inherited that state and reported success anyway, because
# `restart` returns 0 for a unit it went on to kill. So: clear any failure first,
# then confirm the thing is actually running, and say so plainly if it is not.
restart_unit() {
    local unit="$1"
    ssh "${PI_TARGET}" "${SYSTEMCTL} reset-failed ${unit} >/dev/null 2>&1 || true"
    ssh "${PI_TARGET}" "${SYSTEMCTL} restart ${unit}" || true

    local attempt
    for attempt in 1 2 3; do
        if ssh "${PI_TARGET}" "${SYSTEMCTL} is-active --quiet ${unit}"; then
            echo "    ${unit}: active"
            return 0
        fi
        echo "    ${unit}: not active (attempt ${attempt}), clearing and starting..."
        ssh "${PI_TARGET}" "${SYSTEMCTL} reset-failed ${unit} >/dev/null 2>&1 || true"
        ssh "${PI_TARGET}" "${SYSTEMCTL} start ${unit}" || true
        sleep 5
    done

    echo "ERROR: ${unit} did not come back. Last journal lines:" >&2
    ssh "${PI_TARGET}" "${SYSTEMCTL} status ${unit} --no-pager --lines=20" >&2 || true
    return 1
}

echo "==> Installing and restarting smart-home-dashboard.service..."
ssh "${PI_TARGET}" "cd ${REMOTE_PATH} && HOME=${REMOTE_HOME} XDG_RUNTIME_DIR=/run/user/\$(id -u) bash scripts/install-dashboard-service.sh >/tmp/smart-home-dashboard-install.log 2>&1"
restart_unit go2rtc.service
restart_unit smart-home-dashboard.service

echo "==> Done. Dashboard live at http://${PI_HOST}:8000"
