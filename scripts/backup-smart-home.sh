#!/usr/bin/env bash
# Back up everything needed to rebuild the board's smart-home stack.
#
# Captures the git-ignored state that exists nowhere else: the Zigbee network
# key and coordinator database, the Home Assistant config directory, device
# credentials, and the container spec Home Assistant is recreated from.
#
# Two things this script exists to get right, both learned from the
# 2026-09-03 recovery (docs/handoff-2026-09-03-recovery.md):
#
#   1. Home Assistant's .storage is written by the container as root.  A backup
#      running as the normal user reads most of it but silently loses the files
#      it cannot open -- which is how .storage/auth went missing, taking every
#      long-lived token and login session with it.  The HA config is archived
#      through sudo for that reason.
#   2. A backup is only as good as its verification.  The lost archive was
#      "integrity-checked by parsing each file", which cannot catch a file that
#      is not there at all.  This script checks the finished archive against a
#      manifest of REQUIRED members and fails if any is missing.
set -euo pipefail

PI_HOST="${PI_HOST:-192.168.0.234}"
PI_USER="${PI_USER:-orangepi}"
REMOTE_PATH="${REMOTE_PATH:-/home/${PI_USER}/smart_home_AI}"
HA_CONFIG="${HA_CONFIG:-/home/${PI_USER}/homeassistant-config}"
HA_CONTAINER="${HA_CONTAINER:-homeassistant}"
OUT_DIR="${OUT_DIR:-${HOME}/orangepi-recovery}"
LOCAL=0
KEEP_REMOTE=0
ASKPASS=""

usage() {
    cat <<'USAGE'
Usage:
  scripts/backup-smart-home.sh [--host HOST] [--user USER] [--out DIR]
                               [--ha-config PATH] [--container NAME]
                               [--keep-remote] [--local]

Writes <out>/smart-home-backup-<UTC date>.tgz and verifies it.

Options:
  --host HOST       Board IP/hostname.        Default: 192.168.0.234
  --user USER       SSH username.             Default: orangepi
  --out DIR         Local output directory.   Default: ~/orangepi-recovery
  --ha-config PATH  Home Assistant config dir on the board.
  --container NAME  Home Assistant container. Default: homeassistant
  --keep-remote     Leave a copy of the archive on the board as well.
  --local           Run against this machine instead of over SSH.
  --askpass PATH    Path ON THE BOARD to a sudo askpass helper, for unattended
                    runs (cron).  Without it sudo prompts on your terminal.

The archive contains the Zigbee network key, API tokens and camera
credentials.  Treat it as secret; it is written mode 600.
USAGE
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --host) PI_HOST="$2"; shift 2 ;;
        --user) PI_USER="$2"; shift 2 ;;
        --out) OUT_DIR="$2"; shift 2 ;;
        --ha-config) HA_CONFIG="$2"; shift 2 ;;
        --container) HA_CONTAINER="$2"; shift 2 ;;
        --keep-remote) KEEP_REMOTE=1; shift ;;
        --askpass) ASKPASS="$2"; shift 2 ;;
        --local) LOCAL=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown argument: $1" >&2; usage >&2; exit 1 ;;
    esac
done

STAMP="$(date -u +%Y%m%d-%H%M%S)"
ARCHIVE="smart-home-backup-${STAMP}.tgz"
REMOTE_TMP="/tmp/${ARCHIVE}"

run() {
    if [[ "$LOCAL" -eq 1 ]]; then
        bash -c "$1"
    else
        # -t so an interactive sudo password prompt reaches the operator.
        ssh -t "${PI_USER}@${PI_HOST}" "$1"
    fi
}

# Members that must be present in the finished archive.  Anything here that is
# missing is a hard failure: these are the files a restore cannot proceed
# without.  Paths are relative to the archive root.
REQUIRED=(
    "smart_home_AI/.env"
    "smart_home_AI/configs/devices.local.yaml"
    "smart_home_AI/deploy/zigbee/zigbee2mqtt/configuration.yaml"
    "smart_home_AI/deploy/zigbee/zigbee2mqtt/secret.yaml"
    "smart_home_AI/deploy/zigbee/zigbee2mqtt/database.db"
    "smart_home_AI/deploy/zigbee/zigbee2mqtt/coordinator_backup.json"
    "homeassistant-config/.storage/auth"
    "homeassistant-config/.storage/auth_provider.homeassistant"
    "homeassistant-config/.storage/core.config_entries"
    "homeassistant-config/.storage/core.device_registry"
    "homeassistant-config/.storage/core.entity_registry"
    "homeassistant-config/.HA_VERSION"
    "homeassistant-config/configuration.yaml"
    "homeassistant-config/automations.yaml"
    "homeassistant-container-spec.json"
)

echo "==> Collecting on ${PI_HOST} (HA config read as root so .storage is complete)"

# shellcheck disable=SC2016
COLLECT=$(cat <<EOF
set -euo pipefail
export SUDO_ASKPASS="${ASKPASS}"
if sudo -n true 2>/dev/null; then
    SUDO="sudo -n"
elif [ -n "\${SUDO_ASKPASS:-}" ] && [ -x "\${SUDO_ASKPASS}" ]; then
    SUDO="sudo -A"
else
    SUDO="sudo"
fi
STAGE=\$(mktemp -d /tmp/sh-backup-XXXXXX)
trap 'rm -rf "\$STAGE"' EXIT
mkdir -p "\$STAGE/smart_home_AI"

# Project state that is git-ignored and exists nowhere else.
for rel in .env configs/devices.local.yaml go2rtc/go2rtc.yaml; do
    if [ -e "${REMOTE_PATH}/\$rel" ]; then
        mkdir -p "\$STAGE/smart_home_AI/\$(dirname "\$rel")"
        cp -a "${REMOTE_PATH}/\$rel" "\$STAGE/smart_home_AI/\$rel"
    fi
done

# The Zigbee directory must travel as a unit: the network key in
# configuration.yaml, database.db and coordinator_backup.json only restore
# without re-pairing every device if they stay consistent with each other.
if [ -d "${REMOTE_PATH}/deploy/zigbee" ]; then
    mkdir -p "\$STAGE/smart_home_AI/deploy"
    cp -a "${REMOTE_PATH}/deploy/zigbee" "\$STAGE/smart_home_AI/deploy/zigbee"
fi

# Installed user units, which differ from the repo copies once enabled.
if [ -d "\$HOME/.config/systemd/user" ]; then
    mkdir -p "\$STAGE/systemd-user"
    cp -a "\$HOME/.config/systemd/user/." "\$STAGE/systemd-user/" 2>/dev/null || true
fi

[ -f "\$HOME/resource-history.log" ] && cp -a "\$HOME/resource-history.log" "\$STAGE/" || true

# Home Assistant config, as root.  .storage/auth is mode 600 root-owned; read
# as the login user it is skipped and the restore loses every token.
\$SUDO cp -a "${HA_CONFIG}" "\$STAGE/homeassistant-config"
\$SUDO chown -R "\$(id -u):\$(id -g)" "\$STAGE/homeassistant-config"

# Live container spec, so Home Assistant is recreated on the same image digest
# rather than :latest, which would migrate .storage irreversibly.
if docker inspect "${HA_CONTAINER}" > "\$STAGE/homeassistant-container-spec.json" 2>/dev/null; then
    :
else
    echo "WARNING: container ${HA_CONTAINER} not running; spec not captured" >&2
    rm -f "\$STAGE/homeassistant-container-spec.json"
fi

tar czf "${REMOTE_TMP}" -C "\$STAGE" .
chmod 600 "${REMOTE_TMP}"
echo "staged \$(tar tzf "${REMOTE_TMP}" | wc -l) entries"
EOF
)

run "$COLLECT"

mkdir -p "$OUT_DIR"
chmod 700 "$OUT_DIR"
LOCAL_ARCHIVE="${OUT_DIR}/${ARCHIVE}"

echo "==> Retrieving"
if [[ "$LOCAL" -eq 1 ]]; then
    cp -a "$REMOTE_TMP" "$LOCAL_ARCHIVE"
else
    scp -q "${PI_USER}@${PI_HOST}:${REMOTE_TMP}" "$LOCAL_ARCHIVE"
fi
chmod 600 "$LOCAL_ARCHIVE"

if [[ "$KEEP_REMOTE" -eq 0 ]]; then
    run "rm -f '${REMOTE_TMP}'"
else
    run "mv '${REMOTE_TMP}' '\$HOME/${ARCHIVE}'"
    echo "    kept on board at ~/${ARCHIVE}"
fi

echo "==> Verifying ${LOCAL_ARCHIVE}"
gzip -t "$LOCAL_ARCHIVE" || { echo "FAIL: archive is not readable gzip" >&2; exit 1; }
MEMBERS="$(tar tzf "$LOCAL_ARCHIVE" | sed 's#^\./##')"

missing=0
for want in "${REQUIRED[@]}"; do
    if grep -qxF "$want" <<<"$MEMBERS"; then
        printf '    ok      %s\n' "$want"
    else
        printf '    MISSING %s\n' "$want" >&2
        missing=1
    fi
done

if [[ "$missing" -ne 0 ]]; then
    echo >&2
    echo "FAIL: required files are absent from the archive." >&2
    echo "Do not rely on this backup. If .storage/* is missing, the most likely" >&2
    echo "cause is that sudo did not grant access to the Home Assistant config." >&2
    exit 1
fi

# The Zigbee network key is the one item that makes a restore possible without
# re-pairing every device, so confirm it is actually present rather than
# assuming the file's existence means it carries a key.
if tar xzOf "$LOCAL_ARCHIVE" ./smart_home_AI/deploy/zigbee/zigbee2mqtt/configuration.yaml 2>/dev/null \
        | grep -q "network_key"; then
    echo "    ok      zigbee network_key present in configuration.yaml"
else
    echo "    MISSING zigbee network_key -- devices would need re-pairing" >&2
    exit 1
fi

SIZE=$(stat -c %s "$LOCAL_ARCHIVE")
COUNT=$(wc -l <<<"$MEMBERS")
echo
echo "Backup OK: ${LOCAL_ARCHIVE}"
echo "  ${COUNT} entries, ${SIZE} bytes, mode 600"
echo "  sha256 $(sha256sum "$LOCAL_ARCHIVE" | cut -d' ' -f1)"
echo
echo "Contains the Zigbee network key, API tokens and camera credentials."
echo "Keep a second copy somewhere off this machine."
