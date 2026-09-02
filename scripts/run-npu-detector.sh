#!/usr/bin/env bash
#
# Run the NPU camera detector.
#
# Two pieces of setup that are not obvious and are why this wrapper exists:
#
#   * The CIX Compass runtime searches "./operator:./:./lib" for its layer
#     library, relative to the *current working directory*. Without it you get
#     "[ERROR][init:145]Cannot find layerlib" and then heap corruption, so this
#     script runs from a directory holding a symlink to the real one.
#
#   * onnxruntime-zhouyi is a cp311 wheel and the board's system Python is 3.12,
#     so the detector runs from its own 3.11 environment.
#
# MQTT credentials are read from the Zigbee stack's secret.yaml rather than
# duplicated: it is the same broker, and a second copy would drift.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

NPU_VENV="${NPU_VENV:-${HOME}/npu-venv}"
NPU_WORKDIR="${NPU_WORKDIR:-${PROJECT_ROOT}/deploy/npu}"
CIX_OPERATOR_DIR="${CIX_OPERATOR_DIR:-/usr/share/cix/lib/onnxruntime/operator}"
SECRET_FILE="${PROJECT_ROOT}/deploy/zigbee/zigbee2mqtt/secret.yaml"

PYTHON="${NPU_VENV}/bin/python"
[[ -x "${PYTHON}" ]] || {
  echo "No Python 3.11 environment at ${NPU_VENV}." >&2
  echo "Create it with scripts/install-ai-services.sh" >&2
  exit 1
}

[[ -d "${CIX_OPERATOR_DIR}" ]] || {
  echo "CIX operator library missing at ${CIX_OPERATOR_DIR}" >&2
  echo "Is the cix-npu-onnxruntime package installed?" >&2
  exit 1
}

mkdir -p "${NPU_WORKDIR}"
ln -sfn "${CIX_OPERATOR_DIR}" "${NPU_WORKDIR}/operator"

# Project settings (NPU_CAMERAS, NPU_MODEL, ...) live in .env beside the rest.
if [[ -r "${PROJECT_ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  . "${PROJECT_ROOT}/.env"
  set +a
fi

# Reuse the broker credentials the Zigbee installer generated.
if [[ -z "${MQTT_USER:-}" && -r "${SECRET_FILE}" ]]; then
  MQTT_USER="$(sed -n 's/^mqtt_user:[[:space:]]*//p' "${SECRET_FILE}" | tail -n 1 | tr -d '"'"'")"
  MQTT_PASSWORD="$(sed -n 's/^mqtt_password:[[:space:]]*//p' "${SECRET_FILE}" | tail -n 1 | tr -d '"'"'")"
  export MQTT_USER MQTT_PASSWORD
fi

cd "${NPU_WORKDIR}"
export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH:-}"
exec "${PYTHON}" -m src.python.npu_detector "$@"
