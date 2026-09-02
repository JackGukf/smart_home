#!/usr/bin/env bash
#
# Install the two local AI services on the board.  Run it ON the Orange Pi.
#
#   ssh orangepi@192.168.0.234
#   cd smart_home_AI && ./scripts/install-ai-services.sh
#
#   llama-server.service  Qwen3-4B over HTTP on 127.0.0.1:8081, CPU, pinned to
#                         the A720 cores.  Runs alongside Ollama rather than
#                         replacing it, on its own port, so it is reversible.
#   npu-detector.service  YOLOv8n on the Zhouyi NPU against go2rtc cameras,
#                         publishing detections to MQTT.
#
# Safe to re-run.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_DIR="${HOME}/.config/systemd/user"
NPU_VENV="${NPU_VENV:-${HOME}/npu-venv}"
ZHOUYI_WHEEL_DIR="/usr/share/cix/pypi"

info()  { printf '\n\033[1m%s\033[0m\n' "$*"; }
warn()  { printf '  ! %s\n' "$*" >&2; }
die()   { printf '\nERROR: %s\n' "$*" >&2; exit 1; }

SERVICES=()

# ---------------------------------------------------------------- llama-server

info "Checking the llama.cpp server"
LLAMA_BIN="${HOME}/llama-kleidi/build-kleidi-off/bin/llama-server"
LLAMA_MODEL="${HOME}/Qwen3-4B-Q4_0.gguf"

if [[ -x "${LLAMA_BIN}" && -r "${LLAMA_MODEL}" ]]; then
  echo "  binary and model present"
  SERVICES+=("llama-server.service")
else
  [[ -x "${LLAMA_BIN}" ]]   || warn "missing ${LLAMA_BIN} - run scripts/build-llama-server.sh"
  [[ -r "${LLAMA_MODEL}" ]] || warn "missing ${LLAMA_MODEL} - see scripts/build-llama-server.sh"
  warn "skipping llama-server.service"
fi

# ---------------------------------------------------------------- npu-detector

info "Preparing the NPU detector environment"

# The Zhouyi ONNX Runtime ships as a cp311 wheel and the board runs 3.12, so the
# detector needs its own interpreter. uv installs a standalone CPython without
# root, which is why it is used here rather than a system package.
if ! command -v uv >/dev/null 2>&1; then
  export PATH="${HOME}/.local/bin:${PATH}"
fi
if ! command -v uv >/dev/null 2>&1; then
  echo "  installing uv"
  curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1 || die "could not install uv"
  export PATH="${HOME}/.local/bin:${PATH}"
fi

WHEEL="$(ls "${ZHOUYI_WHEEL_DIR}"/onnxruntime_zhouyi-*-cp311-*.whl 2>/dev/null | head -n 1 || true)"
if [[ -z "${WHEEL}" ]]; then
  warn "No onnxruntime-zhouyi cp311 wheel in ${ZHOUYI_WHEEL_DIR}."
  warn "Is cix-npu-onnxruntime installed?  Skipping npu-detector.service."
else
  if [[ ! -x "${NPU_VENV}/bin/python" ]]; then
    echo "  creating ${NPU_VENV} on Python 3.11"
    uv python install 3.11 >/dev/null
    uv venv --python 3.11 "${NPU_VENV}" >/dev/null
  fi
  echo "  installing onnxruntime-zhouyi and dependencies"
  uv pip install --quiet --python "${NPU_VENV}/bin/python" \
    "${WHEEL}" numpy opencv-python-headless paho-mqtt requests pyyaml

  if "${NPU_VENV}/bin/python" - <<'PY'
import sys
import onnxruntime as ort
sys.exit(0 if "ZhouyiExecutionProvider" in ort.get_available_providers() else 1)
PY
  then
    echo "  ZhouyiExecutionProvider available"
    SERVICES+=("npu-detector.service")
  else
    warn "ZhouyiExecutionProvider not available in ${NPU_VENV}; skipping npu-detector.service"
  fi
fi

# The detector needs somewhere the Compass runtime can find ./operator.
mkdir -p "${PROJECT_ROOT}/deploy/npu"
ln -sfn /usr/share/cix/lib/onnxruntime/operator "${PROJECT_ROOT}/deploy/npu/operator"

if ! grep -q '^NPU_CAMERAS=' "${PROJECT_ROOT}/.env" 2>/dev/null; then
  warn "NPU_CAMERAS is not set in .env - the detector will exit until it is."
  warn "Set it to go2rtc stream names, e.g. NPU_CAMERAS=front_door_camera,family_room_camera"
fi

# --------------------------------------------------------------------- install

info "Installing user units"
mkdir -p "${UNIT_DIR}"
for service in "${SERVICES[@]}"; do
  install -m 644 "${PROJECT_ROOT}/deploy/systemd/user/${service}" "${UNIT_DIR}/${service}"
  echo "  ${service}"
done
chmod +x "${PROJECT_ROOT}/scripts/run-llama-server.sh" "${PROJECT_ROOT}/scripts/run-npu-detector.sh"

systemctl --user daemon-reload
for service in "${SERVICES[@]}"; do
  systemctl --user enable "${service}" >/dev/null 2>&1 || true
  systemctl --user restart "${service}"
  printf '  %-24s %s\n' "${service}" "$(systemctl --user is-active "${service}")"
done

# A user unit only starts at boot when the account lingers.
if [[ "$(loginctl show-user "$(id -un)" --property=Linger --value 2>/dev/null)" != "yes" ]]; then
  warn "User lingering is off, so these will not start at boot."
  warn "Enable it with: sudo loginctl enable-linger $(id -un)"
fi

cat <<EOF

Done.

  llama-server   curl http://127.0.0.1:8081/v1/models
  npu-detector   journalctl --user -u npu-detector -f
                 mosquitto_sub -t 'smarthome/vision/#' -v

Ollama is untouched on 11434. Both hold their own copy of a ~2.3GB model when
loaded, so watch memory if you keep all of them warm.
EOF
