#!/usr/bin/env bash
# Run this ONCE inside the Docker dev container to bootstrap the CHIP SDK.
# Takes 30-60 minutes on first run.
# Usage: docker compose run --rm dev bash scripts/setup-matter-sdk.sh
set -e

CHIP_DIR="$(git rev-parse --show-toplevel)/third_party/connectedhomeip"

echo "==> Initialising CHIP SDK submodules (this downloads ~500 MB)..."
cd "$CHIP_DIR"

echo "==> Fetching v1.3.0.0 tag..."
git fetch --depth=1 origin tag v1.3.0.0
git checkout v1.3.0.0

git submodule update --init --depth 1 \
  third_party/pigweed/repo \
  third_party/nlohmann_json \
  third_party/jsoncpp/repo \
  third_party/mbedtls/repo \
  third_party/boringssl \
  third_party/ot-br-posix \
  third_party/openthread/ot-core

echo "==> Bootstrapping pigweed toolchain (downloads clang, gn, etc.)..."
bash scripts/bootstrap.sh

echo "==> Done. Activate with: source scripts/activate.sh"
