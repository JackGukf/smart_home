#!/usr/bin/env bash
# The AI data page's dependencies and its Ecobee timer, on the board.
#
#   scripts/install-ai-data.sh              # pypdf, the timer, a status report
#   scripts/install-ai-data.sh --no-timer   # dependencies only
#
# The Ecobee timer fetches yesterday's furnace runtime every morning. It does
# nothing until the account has been authorised once, which is a person's job:
#
#   .venv/bin/python -m src.python.ecobee_runtime --authorize --api-key YOUR_KEY
#   .venv/bin/python -m src.python.ecobee_runtime --fetch --days 730
#
# The API key comes from ecobee.com -> Developer -> Create New Application, with
# the "ecobee PIN" authorisation method. Read-only (smartRead).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="${ROOT}/.venv"
[[ -x "${VENV}/bin/pip" ]] || { echo "no venv at ${VENV}" >&2; exit 1; }

"${VENV}/bin/pip" install -q pypdf
echo "pypdf $("${VENV}/bin/python" -c 'import pypdf; print(pypdf.__version__)') - bills can be read"

mkdir -p "${ROOT}/ai-data/files"

if [[ "${1:-}" != "--no-timer" ]]; then
    install -m 644 "${ROOT}/deploy/systemd/user/ecobee-runtime.service" \
                   "${ROOT}/deploy/systemd/user/ecobee-runtime.timer" "${HOME}/.config/systemd/user/"
    systemctl --user daemon-reload
    systemctl --user enable --now ecobee-runtime.timer
    systemctl --user list-timers ecobee-runtime --no-pager | head -3
fi

if [[ -f "${ROOT}/ai-data/ecobee_tokens.json" ]]; then
    echo "ecobee: authorised"
else
    echo "ecobee: not authorised yet - run --authorize (see the top of this script)"
fi
