#!/usr/bin/env bash
#
# Install the morning digest timer on the board.  Run it ON the Orange Pi.
#
#   ssh orangepi@192.168.0.234
#   cd smart_home_AI && ./scripts/install-house-digest.sh
#
# house-digest.timer fires house-digest.service at 04:00.  The service computes
# the previous day's figures from the motion log, Home Assistant's states and
# resource-history.log, then asks the local model to turn them into a few
# sentences.  The dashboard serves the result at /api/digest and shows it on the
# Status view.
#
# The model is the optional part: if Ollama is unreachable or too slow the
# digest is still written, with the figures and no prose.
#
# Safe to re-run.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_DIR="${HOME}/.config/systemd/user"

info() { printf '\n\033[1m%s\033[0m\n' "$*"; }
die()  { printf '\nERROR: %s\n' "$*" >&2; exit 1; }

[[ -r "${PROJECT_ROOT}/.env" ]] || die "no .env - the digest needs HOME_ASSISTANT_TOKEN"
grep -q '^HOME_ASSISTANT_TOKEN=' "${PROJECT_ROOT}/.env" \
  || die "HOME_ASSISTANT_TOKEN is not set in .env"

# The units run the dashboard virtualenv's interpreter, because that is the one
# with the project's dependencies. Without it the service fails at import time,
# hours later, in a log nobody is watching.
[[ -x "${PROJECT_ROOT}/.venv/bin/python" ]] \
  || die "no ${PROJECT_ROOT}/.venv/bin/python - deploy the dashboard first"

info "Checking the digest runs at all"
# No model call, so this takes a second rather than minutes: the point here is
# that the inputs are readable and the code imports.
"${PROJECT_ROOT}/.venv/bin/python" "${PROJECT_ROOT}/scripts/house_digest.py" \
  --out /tmp/house-digest-check.json --history /dev/null \
  >/dev/null || die "the digest could not be produced - fix that before scheduling it"
echo "  ok"

info "Installing the units"
mkdir -p "${UNIT_DIR}"
install -m 644 "${PROJECT_ROOT}/deploy/systemd/user/house-digest.service" "${UNIT_DIR}/"
install -m 644 "${PROJECT_ROOT}/deploy/systemd/user/house-digest.timer"   "${UNIT_DIR}/"
systemctl --user daemon-reload

# The timer is enabled, not the service: enabling a oneshot service would run it
# at every login as well as on the schedule.
systemctl --user enable --now house-digest.timer

# Without lingering, user units stop when the last session ends - so the 04:00
# timer would only fire on a night somebody happened to be logged in.
if ! loginctl show-user "$(id -un)" -p Linger --value 2>/dev/null | grep -q yes; then
  echo "  enabling lingering so the timer survives logout"
  sudo loginctl enable-linger "$(id -un)" || die "could not enable lingering"
fi

info "Installed"
systemctl --user list-timers house-digest.timer --no-pager || true
echo
echo "Run it now without waiting for 04:00:"
echo "  systemctl --user start house-digest.service && journalctl --user -u house-digest -n 20"
