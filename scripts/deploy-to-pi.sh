#!/usr/bin/env bash
set -euo pipefail

PI_HOST="${PI_HOST:-192.168.0.176}"
PI_USER="${PI_USER:-smarthome}"
REMOTE_PATH="${REMOTE_PATH:-/home/${PI_USER}/smart-home-rpi4}"
SKIP_BUILD="${SKIP_BUILD:-0}"

usage() {
    cat <<'EOF'
Usage:
  scripts/deploy-to-pi.sh [--host HOST] [--user USER] [--remote-path PATH] [--skip-build]

Environment variables:
  PI_HOST       Raspberry Pi hostname or IP address. Default: 192.168.0.176
  PI_USER       SSH username. Default: smarthome
  REMOTE_PATH   Remote install directory. Default: /home/$PI_USER/smart-home-rpi4
  SKIP_BUILD    Set to 1 to skip cross-compiling before deploy.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --host)
            PI_HOST="$2"
            shift 2
            ;;
        --user)
            PI_USER="$2"
            shift 2
            ;;
        --remote-path)
            REMOTE_PATH="$2"
            shift 2
            ;;
        --skip-build)
            SKIP_BUILD=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown argument: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PI_TARGET="${PI_USER}@${PI_HOST}"
CPP_BINARY="$PROJECT_ROOT/build/rpi4-release/src/cpp/smart_home_controller"

if [[ "$SKIP_BUILD" != "1" ]]; then
    "$PROJECT_ROOT/scripts/build-rpi4.sh"
fi

if [[ ! -x "$CPP_BINARY" ]]; then
    echo "Missing Raspberry Pi binary: $CPP_BINARY" >&2
    echo "Run scripts/build-rpi4.sh first, or deploy without --skip-build." >&2
    exit 1
fi

ssh "$PI_TARGET" "mkdir -p '$REMOTE_PATH/bin' '$REMOTE_PATH/src/python' '$REMOTE_PATH/configs' '$REMOTE_PATH/scripts'"

rsync -av "$CPP_BINARY" "$PI_TARGET:$REMOTE_PATH/bin/smart_home_controller"
rsync -av "$PROJECT_ROOT/src/python/" "$PI_TARGET:$REMOTE_PATH/src/python/"
rsync -av "$PROJECT_ROOT/scripts/run-dashboard.sh" "$PI_TARGET:$REMOTE_PATH/scripts/run-dashboard.sh"
rsync -av "$PROJECT_ROOT/configs/devices.example.yaml" "$PI_TARGET:$REMOTE_PATH/configs/devices.example.yaml"
if [[ -f "$PROJECT_ROOT/tplink_switches.json" ]]; then
    rsync -av "$PROJECT_ROOT/tplink_switches.json" "$PI_TARGET:$REMOTE_PATH/tplink_switches.json"
fi

ssh "$PI_TARGET" "cd '$REMOTE_PATH' && python3 -m venv .venv && .venv/bin/python -m pip install --upgrade pip && if [ -f src/python/requirements.txt ]; then .venv/bin/python -m pip install -r src/python/requirements.txt; fi"

cat <<EOF
Deployment complete.

Target:
  $PI_TARGET:$REMOTE_PATH

Run on Raspberry Pi:
  $REMOTE_PATH/bin/smart_home_controller
  $REMOTE_PATH/.venv/bin/python $REMOTE_PATH/src/python/controller.py
  cd $REMOTE_PATH && .venv/bin/python -m uvicorn src.python.web_app:app --host 0.0.0.0 --port 8000
EOF
