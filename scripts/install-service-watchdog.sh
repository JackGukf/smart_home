#!/usr/bin/env bash
#
# Install the service watchdog on the board.  Run it ON the Orange Pi.
#
#   ./scripts/install-service-watchdog.sh              # the timer (as orangepi)
#   sudo ./scripts/install-service-watchdog.sh --polkit  # also: may restart matter-server
#
# service-watchdog.timer runs src/python/service_watchdog.py every two minutes.
# It restarts what hangs - running but not working - and reports every action
# on the dashboard and in Home Assistant. See the module for the checks.
#
# Pause it (e.g. while re-flashing the Zigbee dongle): touch deploy/watchdog/.paused
# Remove it:  systemctl --user disable --now service-watchdog.timer
#
# Safe to re-run.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ "${1:-}" == "--polkit" ]]; then
    [[ $EUID -eq 0 ]] || { echo "run with sudo: sudo $0 --polkit" >&2; exit 1; }
    install -m 0644 -o root -g root "${PROJECT_ROOT}/deploy/polkit/51-smart-home-watchdog.rules" \
        /etc/polkit-1/rules.d/51-smart-home-watchdog.rules
    echo "installed /etc/polkit-1/rules.d/51-smart-home-watchdog.rules"
    exit 0
fi
[[ $EUID -ne 0 ]] || { echo "run the timer install as orangepi, not root" >&2; exit 1; }

grep -q '^HOME_ASSISTANT_TOKEN=' "${PROJECT_ROOT}/.env" 2>/dev/null \
  || { echo "HOME_ASSISTANT_TOKEN is not set in .env - the Home Assistant checks need it" >&2; exit 1; }

UNIT_DIR="${HOME}/.config/systemd/user"
mkdir -p "${UNIT_DIR}" "${PROJECT_ROOT}/deploy/watchdog"
install -m 0644 "${PROJECT_ROOT}/deploy/systemd/user/service-watchdog.service" "${UNIT_DIR}/"
install -m 0644 "${PROJECT_ROOT}/deploy/systemd/user/service-watchdog.timer" "${UNIT_DIR}/"
systemctl --user daemon-reload

echo "a dry run first - it probes and reports, and changes nothing:"
"${PROJECT_ROOT}/.venv/bin/python" -m src.python.service_watchdog --dry-run

# User timers stop when the last session ends, unless the user lingers.
loginctl show-user "$USER" -p Linger | grep -q yes \
  || echo "note: lingering is off - run 'sudo loginctl enable-linger $USER' or the timer stops at logout" >&2
systemctl --user enable --now service-watchdog.timer
systemctl --user list-timers service-watchdog.timer --no-pager
