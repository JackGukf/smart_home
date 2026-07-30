#!/usr/bin/env bash
# Cross-compile the C++ controller for the Orange Pi 6 Plus (primary target).
# Pass --board rpi4 to build for the secondary Raspberry Pi 4 target instead.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BOARD="${BOARD:-orangepi6}"

usage() {
    cat <<'EOF'
Usage:
  scripts/build-orangepi6.sh [--board orangepi6|rpi4]

Environment variables:
  BOARD   Target board. Default: orangepi6
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --board)
            BOARD="$2"
            shift 2
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

case "$BOARD" in
    orangepi6)
        BOARD_LABEL="Orange Pi 6 Plus"
        ;;
    rpi4)
        BOARD_LABEL="Raspberry Pi 4 (secondary target)"
        ;;
    *)
        echo "Unknown board: $BOARD (expected orangepi6 or rpi4)" >&2
        exit 2
        ;;
esac

PRESET="docker-${BOARD}-release"

if [[ -f /.dockerenv ]]; then
    cmake --preset "$PRESET"
    cmake --build --preset "$PRESET"
else
    docker compose -f "$PROJECT_ROOT/docker-compose.yml" build dev
    docker compose -f "$PROJECT_ROOT/docker-compose.yml" run --rm dev \
        ./scripts/build-orangepi6.sh --board "$BOARD"
fi

echo "${BOARD_LABEL} binary:"
echo "$PROJECT_ROOT/build/${BOARD}-release/src/cpp/smart_home_controller"
