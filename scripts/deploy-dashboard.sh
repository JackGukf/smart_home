#!/usr/bin/env bash
# Deploy dashboard files to Raspberry Pi and restart uvicorn.
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
REMOTE_PATH="/home/${PI_USER}/smart-home-rpi4"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> Deploying dashboard to ${PI_TARGET}…"

rsync --checksum -av \
    "${PROJECT_ROOT}/src/python/"*.py \
    "${PI_TARGET}:${REMOTE_PATH}/src/python/"

rsync --checksum -av \
    "${PROJECT_ROOT}/src/python/web_static/" \
    "${PI_TARGET}:${REMOTE_PATH}/src/python/web_static/"

echo "==> Restarting uvicorn…"
ssh "${PI_TARGET}" "pkill -f uvicorn; true"
ssh "${PI_TARGET}" \
    "nohup bash -c 'cd ${REMOTE_PATH} && set -a && [ -f .env ] && source .env; set +a && .venv/bin/python -m uvicorn src.python.web_app:app --host 0.0.0.0 --port 8000' \
     </dev/null >/tmp/uvicorn.log 2>&1 &"

echo "==> Done. Dashboard live at http://${PI_HOST}:8000"
