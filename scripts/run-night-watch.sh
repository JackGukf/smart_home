#!/usr/bin/env bash
#
# Run the night watch (src/python/night_watch.py): a clip and a Telegram photo
# when something moves outside at night.
#
# It runs in the NPU detector's Python 3.11 environment, which already has
# OpenCV (to draw the detector's boxes on the photo) and paho-mqtt. MQTT
# credentials come from the Zigbee stack's secret.yaml, like the detector's;
# TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_IDS from .env.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NPU_VENV="${NPU_VENV:-${HOME}/npu-venv}"
SECRET_FILE="${PROJECT_ROOT}/deploy/zigbee/zigbee2mqtt/secret.yaml"
PYTHON="${NPU_VENV}/bin/python"

[[ -x "${PYTHON}" ]] || {
  echo "No Python environment at ${NPU_VENV} (scripts/install-ai-services.sh makes it)." >&2
  exit 1
}

if [[ -r "${PROJECT_ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  . "${PROJECT_ROOT}/.env"
  set +a
fi

if [[ -z "${MQTT_USER:-}" && -r "${SECRET_FILE}" ]]; then
  MQTT_USER="$(sed -n 's/^mqtt_user:[[:space:]]*//p' "${SECRET_FILE}" | tail -n 1 | tr -d '"'"'")"
  MQTT_PASSWORD="$(sed -n 's/^mqtt_password:[[:space:]]*//p' "${SECRET_FILE}" | tail -n 1 | tr -d '"'"'")"
  export MQTT_USER MQTT_PASSWORD
fi

cd "${PROJECT_ROOT}"
export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH:-}"
exec "${PYTHON}" -m src.python.night_watch "$@"
