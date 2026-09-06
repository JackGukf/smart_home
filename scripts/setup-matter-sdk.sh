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

echo "==> Initialising platform submodules for linux (uses official checkout script)..."
python3 scripts/checkout_submodules.py --platform linux --shallow

# Work around an upstream pigweed bug that stops the bootstrap dead.
#
# pw_env_setup/cipd_setup/update.py:check_auth() probes each CIPD package for
# access before installing, but first strips any "${...}" segment:
#
#     parts = entry['path'].split('/')
#     while '${' in parts[-1]:
#         parts.pop(-1)
#
# zap.json's path is "fuchsia/third_party/zap/${platform}", so the probe runs
# against "fuchsia/third_party/zap" -- a prefix, not a package. `cipd ls` on it
# returns "No matching packages" (anonymous users cannot list that prefix) and
# `cipd instances` errors (it is not a package), so pigweed concludes there is
# no anonymous access and attempts an interactive login, which cannot work
# without a TTY. The bootstrap then dies with "CIPD login failed".
#
# The packages themselves are anonymously readable -- `cipd resolve
# fuchsia/third_party/zap/linux-amd64` succeeds. So name each platform's package
# explicitly instead of via the placeholder: identical installation behaviour,
# nothing left for the probe to mangle. Idempotent.
echo "==> Naming zap CIPD packages explicitly (upstream check_auth bug)..."
python3 "$(git rev-parse --show-toplevel)/scripts/fix_zap_cipd_paths.py" \
    "$CHIP_DIR/scripts/setup/zap.json"

echo "==> Bootstrapping pigweed toolchain (downloads clang, gn, etc.)..."
bash scripts/bootstrap.sh

echo "==> Done. Activate with: source scripts/activate.sh"
