#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -f /.dockerenv ]]; then
    cmake --preset docker-rpi4-release
    cmake --build --preset docker-rpi4-release
else
    docker compose -f "$PROJECT_ROOT/docker-compose.yml" build dev
    docker compose -f "$PROJECT_ROOT/docker-compose.yml" run --rm dev ./scripts/build-rpi4.sh
fi

echo "Raspberry Pi 4 binary:"
echo "$PROJECT_ROOT/build/rpi4-release/src/cpp/smart_home_controller"
