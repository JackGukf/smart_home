#!/usr/bin/env bash
# Smart home wall panel: hold Chromium on the dashboard, full screen, for ever.
#
# This runs on the Raspberry Pi 4 inside its labwc (Wayland) desktop session,
# started by ~/.config/autostart/smart-home-kiosk.desktop. It is installed by
# scripts/setup-kiosk-display.sh - edit it here in the repo and re-run that,
# do not hand-edit the copy on the panel.
#
# Deliberately NOT `set -e`. The whole point of this script is to outlive the
# things that go wrong at 3am - a router reboot, the Orange Pi coming back
# slower than the panel, Chromium dying on a bad GPU frame.
set -uo pipefail

CONFIG_FILE="${HOME}/.config/smart-home-kiosk.env"
# shellcheck source=/dev/null
[[ -r "${CONFIG_FILE}" ]] && source "${CONFIG_FILE}"

DASHBOARD_URL="${DASHBOARD_URL:-http://192.168.0.234:8000/}"
CHROMIUM_BIN="${CHROMIUM_BIN:-$(command -v chromium || command -v chromium-browser || true)}"
PROFILE_DIR="${PROFILE_DIR:-${HOME}/.config/chromium-kiosk}"
LOG_FILE="${LOG_FILE:-${HOME}/.local/state/smart-home-kiosk.log}"
# How long to wait for the dashboard before opening Chromium anyway. The panel
# showing an error page is better than the panel showing nothing at all.
WAIT_SECONDS="${WAIT_SECONDS:-120}"

mkdir -p "$(dirname "${LOG_FILE}")" "${PROFILE_DIR}"

log() { printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "${LOG_FILE}"; }

# Keep the log from growing without bound on a board that never reboots.
if [[ -f "${LOG_FILE}" ]] && (( $(stat -c %s "${LOG_FILE}" 2>/dev/null || echo 0) > 1048576 )); then
    tail -n 500 "${LOG_FILE}" > "${LOG_FILE}.tmp" && mv "${LOG_FILE}.tmp" "${LOG_FILE}"
fi

log "=== kiosk starting: ${DASHBOARD_URL}"

if [[ -z "${CHROMIUM_BIN}" ]]; then
    log "FATAL: no chromium binary found (looked for chromium, chromium-browser)"
    exit 1
fi

# ── Find the compositor ──────────────────────────────────────────────────────
# Started from the autostart entry, WAYLAND_DISPLAY is already in the
# environment. Started over ssh - which is how you test a panel that is already
# on the wall - it is not, and Chromium's --ozone-platform-hint=auto reads
# XDG_SESSION_TYPE, sees "tty", guesses X11 and dies on "Missing $DISPLAY".
if [[ -z "${WAYLAND_DISPLAY:-}" ]]; then
    runtime_dir="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
    socket="$(find "${runtime_dir}" -maxdepth 1 -name 'wayland-[0-9]*' ! -name '*.lock' \
              -printf '%f\n' 2>/dev/null | sort | head -1)"
    if [[ -n "${socket}" ]]; then
        export XDG_RUNTIME_DIR="${runtime_dir}"
        export WAYLAND_DISPLAY="${socket}"
        log "found compositor socket ${socket}"
    fi
fi

if [[ -n "${WAYLAND_DISPLAY:-}" ]]; then
    PLATFORM_ARGS=(--ozone-platform=wayland)
else
    PLATFORM_ARGS=(--ozone-platform-hint=auto)
    log "WARN: no Wayland socket found, letting Chromium guess the platform"
fi

# ── Keep the panel awake ─────────────────────────────────────────────────────
# raspi-config's blanking switch covers the compositor's own idle timer, but a
# stray swayidle from an earlier session will still blank the screen behind it.
keep_display_awake() {
    pkill -u "$(id -u)" -x swayidle 2>/dev/null && log "stopped a leftover swayidle"
    command -v wlopm >/dev/null 2>&1 && wlopm --on '*' >/dev/null 2>&1
    # X11 fallback, in case the panel is ever run under the rpd-x session.
    if [[ -n "${DISPLAY:-}" ]] && command -v xset >/dev/null 2>&1; then
        xset s off -dpms 2>/dev/null
    fi
}

# ── Wait for the dashboard ───────────────────────────────────────────────────
# Chromium caches its failure: if it opens before the Orange Pi is up it shows
# a dead error page and never retries on its own.
wait_for_dashboard() {
    local deadline=$(( SECONDS + WAIT_SECONDS ))
    while (( SECONDS < deadline )); do
        if curl -fsS -o /dev/null --max-time 5 "${DASHBOARD_URL}"; then
            log "dashboard answered"
            return 0
        fi
        sleep 3
    done
    log "WARN: dashboard did not answer within ${WAIT_SECONDS}s, opening anyway"
    return 1
}

# ── Suppress the "Restore pages?" bar ────────────────────────────────────────
# A wall panel loses power without being shut down, so Chromium thinks it
# crashed and parks a dialog over the dashboard that nobody is there to dismiss.
# The flags below hide most of it; rewriting exit_type is what actually stops it.
clear_crash_flag() {
    local prefs="${PROFILE_DIR}/Default/Preferences"
    [[ -f "${prefs}" ]] || return 0
    sed -i 's/"exit_type":"[^"]*"/"exit_type":"Normal"/; s/"exited_cleanly":false/"exited_cleanly":true/' \
        "${prefs}" 2>/dev/null
}

# ── Run ──────────────────────────────────────────────────────────────────────
keep_display_awake

# The session can start its own swayidle after this script does, so one kill at
# startup is a race. Re-check quietly for the life of the session instead.
( while true; do sleep 60; keep_display_awake; done ) &

wait_for_dashboard

failures=0
window_start=${SECONDS}

while true; do
    clear_crash_flag
    log "launching chromium"

    "${CHROMIUM_BIN}" \
        --kiosk \
        --user-data-dir="${PROFILE_DIR}" \
        "${PLATFORM_ARGS[@]}" \
        --start-maximized \
        --noerrdialogs \
        --disable-infobars \
        --disable-session-crashed-bubble \
        --hide-crash-restore-bubble \
        --no-first-run \
        --no-default-browser-check \
        --disable-features=Translate,TranslateUI \
        --disable-component-update \
        --check-for-update-interval=31536000 \
        --password-store=basic \
        --autoplay-policy=no-user-gesture-required \
        --overscroll-history-navigation=0 \
        "${DASHBOARD_URL}" >> "${LOG_FILE}" 2>&1

    status=$?
    log "chromium exited (status ${status})"

    # Five deaths inside a minute is a real fault, not a blip. Back off so the
    # panel is not spinning a relaunch loop that keeps the CPU hot all night.
    if (( SECONDS - window_start > 60 )); then
        failures=0
        window_start=${SECONDS}
    fi
    failures=$(( failures + 1 ))
    if (( failures >= 5 )); then
        log "WARN: 5 exits in under a minute, backing off for 60s"
        sleep 60
        failures=0
        window_start=${SECONDS}
    else
        sleep 5
    fi

    keep_display_awake
done
