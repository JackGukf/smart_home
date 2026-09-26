#!/usr/bin/env bash
# The nightly off-site backup (action list B1; offsite-backup.timer, 02:40).
#
#  1. scripts/backup-smart-home.sh --local: the verified archive, as by hand -
#     unattended, Home Assistant's config comes out through Docker (no sudo).
#  2. restic backs up its unpacked contents to Google Drive through rclone:
#     encrypted on the board (Google sees only restic's scrambled packs) and
#     deduplicated, so a night uploads what changed, not 40 MB.
#  3. Keeps 14 daily, 8 weekly and 12 monthly snapshots; prunes on Sundays.
#  4. Writes ~/backups/offsite-status.json. The heartbeat (heartbeat.py) fails
#     its ping when the last success is over 36 h old, so a failing backup
#     reaches the owner through healthchecks.io's Telegram bot.
#
# Needs in .env: RESTIC_PASSWORD, RESTIC_REPOSITORY (rclone:gdrive:smart-home-backup),
# and an rclone remote "gdrive" (docs/offsite-backup.md).
set -uo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUPS="${HOME}/backups"
STATUS="${BACKUPS}/offsite-status.json"
export PATH="${HOME}/.local/bin:${PATH}"
mkdir -p "${BACKUPS}" && chmod 700 "${BACKUPS}"

set -a
# shellcheck disable=SC1091
. "${PROJECT_ROOT}/.env"
set +a

status() {   # ok(true|false), message
    python3 - "$1" "$2" "${STATUS}" <<'PY'
import json, sys, time
from pathlib import Path
ok, message, path = sys.argv[1] == "true", sys.argv[2], Path(sys.argv[3])
try:
    doc = json.loads(path.read_text())
except (OSError, ValueError):
    doc = {}
doc.update({"checked_at": time.time(), "ok": ok, "message": message})
if ok:
    doc["last_ok"] = time.time()
path.write_text(json.dumps(doc, indent=1))
PY
}

fail() { echo "offsite backup FAILED: $1" >&2; status false "$1"; exit 1; }

[[ -n "${RESTIC_PASSWORD:-}" && -n "${RESTIC_REPOSITORY:-}" ]] || fail "RESTIC_PASSWORD / RESTIC_REPOSITORY not in .env"

bash "${PROJECT_ROOT}/scripts/backup-smart-home.sh" --local --out "${BACKUPS}" </dev/null \
    || fail "the local archive failed (backup-smart-home.sh)"
ARCHIVE="$(ls -1t "${BACKUPS}"/smart-home-backup-*.tgz | head -1)"
# Three archives stay on the board for a quick restore without the internet.
ls -1t "${BACKUPS}"/smart-home-backup-*.tgz | tail -n +4 | xargs -r rm -f

UNPACKED="$(mktemp -d)"
trap 'rm -rf "${UNPACKED}"' EXIT
tar xzf "${ARCHIVE}" -C "${UNPACKED}" || fail "could not unpack ${ARCHIVE}"

restic backup --quiet --host orangepi6plus --tag nightly "${UNPACKED}" \
    || fail "restic backup to ${RESTIC_REPOSITORY} failed"
KEEP=(--keep-daily 14 --keep-weekly 8 --keep-monthly 12)
if [[ "$(date +%u)" == "7" ]]; then
    restic forget --quiet --host orangepi6plus "${KEEP[@]}" --prune || fail "restic forget/prune failed"
else
    restic forget --quiet --host orangepi6plus "${KEEP[@]}" || fail "restic forget failed"
fi
status true "$(basename "${ARCHIVE}") -> ${RESTIC_REPOSITORY}"
echo "offsite backup ok: $(basename "${ARCHIVE}")"
