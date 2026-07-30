#!/usr/bin/env bash
set -euo pipefail

PI_HOST="${PI_HOST:-192.168.0.234}"
PI_USER="${PI_USER:-orangepi}"
REMOTE_PATH="${REMOTE_PATH:-/home/${PI_USER}/smart_home_AI}"

usage() {
    cat <<'EOF'
Usage:
  scripts/connect-pi.sh [--host HOST] [--user USER] [--remote-path PATH] [--check] [-- COMMAND...]

Examples:
  scripts/connect-pi.sh
  scripts/connect-pi.sh --check
  scripts/connect-pi.sh -- uname -a
  scripts/connect-pi.sh -- "cd ~/smart_home_AI && ./bin/smart_home_controller"

  # Secondary Raspberry Pi 4 target:
  scripts/connect-pi.sh --host 192.168.0.176 --user smarthome \
      --remote-path /home/smarthome/smart-home-rpi4

Environment variables:
  PI_HOST       Board IP/hostname. Default: 192.168.0.234 (Orange Pi 6 Plus)
  PI_USER       SSH username. Default: orangepi
  REMOTE_PATH   Remote project directory. Default: /home/$PI_USER/smart_home_AI
EOF
}

CHECK_ONLY=0
REMOTE_COMMAND=()

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
        --check)
            CHECK_ONLY=1
            shift
            ;;
        --)
            shift
            REMOTE_COMMAND=("$@")
            break
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            REMOTE_COMMAND=("$@")
            break
            ;;
    esac
done

PI_TARGET="${PI_USER}@${PI_HOST}"
SSH_OPTIONS=(
    -o ServerAliveInterval=30
    -o ServerAliveCountMax=3
)

if [[ "$CHECK_ONLY" == "1" ]]; then
    ssh "${SSH_OPTIONS[@]}" "$PI_TARGET" \
        "printf 'Connected to '; hostname; uname -a; command -v python3; command -v rsync; test -d '$REMOTE_PATH' && echo 'Project directory exists: $REMOTE_PATH' || echo 'Project directory not created yet: $REMOTE_PATH'"
    exit 0
fi

if [[ ${#REMOTE_COMMAND[@]} -gt 0 ]]; then
    ssh "${SSH_OPTIONS[@]}" "$PI_TARGET" "${REMOTE_COMMAND[@]}"
else
    ssh "${SSH_OPTIONS[@]}" "$PI_TARGET"
fi
