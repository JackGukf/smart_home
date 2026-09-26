#!/usr/bin/env bash
# Install the nightly off-site backup on the board (action list B1).
#
# Puts pinned restic and rclone in ~/.local/bin - release binaries, checksums
# verified, no sudo - and installs offsite-backup.service/.timer (02:40). It
# does not set up Google Drive or the encryption passphrase; see
# docs/offsite-backup.md for those one-time steps.
set -euo pipefail

RESTIC_VERSION="0.19.1"
RCLONE_VERSION="1.75.1"
BIN="${HOME}/.local/bin"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT
mkdir -p "${BIN}"

fetch_verified() {   # url, sums-url, file name
    curl -fsSL -o "${WORK}/$3" "$1"
    curl -fsSL -o "${WORK}/$3.sums" "$2"
    (cd "${WORK}" && grep " \*\?$3\$" "$3.sums" | sed 's/ \*/  /' | sha256sum -c -) \
        || { echo "checksum mismatch for $3" >&2; exit 1; }
}

if ! "${BIN}/restic" version 2>/dev/null | grep -q " ${RESTIC_VERSION} "; then
    name="restic_${RESTIC_VERSION}_linux_arm64.bz2"
    fetch_verified "https://github.com/restic/restic/releases/download/v${RESTIC_VERSION}/${name}" \
        "https://github.com/restic/restic/releases/download/v${RESTIC_VERSION}/SHA256SUMS" "${name}"
    bunzip2 -c "${WORK}/${name}" > "${BIN}/restic" && chmod 755 "${BIN}/restic"
fi
if ! "${BIN}/rclone" version 2>/dev/null | grep -q "v${RCLONE_VERSION}"; then
    name="rclone-v${RCLONE_VERSION}-linux-arm64.zip"
    fetch_verified "https://github.com/rclone/rclone/releases/download/v${RCLONE_VERSION}/${name}" \
        "https://github.com/rclone/rclone/releases/download/v${RCLONE_VERSION}/SHA256SUMS" "${name}"
    python3 -m zipfile -e "${WORK}/${name}" "${WORK}/rclone-x"
    install -m 755 "${WORK}"/rclone-x/*/rclone "${BIN}/rclone"
fi
"${BIN}/restic" version
"${BIN}/rclone" version | head -1

install -m 644 "${PROJECT_ROOT}/deploy/systemd/user/offsite-backup.service" \
               "${PROJECT_ROOT}/deploy/systemd/user/offsite-backup.timer" "${HOME}/.config/systemd/user/"
systemctl --user daemon-reload
systemctl --user enable --now offsite-backup.timer
echo "offsite-backup.timer enabled (02:40 nightly)"
