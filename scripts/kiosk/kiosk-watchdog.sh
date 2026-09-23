#!/usr/bin/env bash
# Restart the kiosk browser if the visible dashboard clock stops advancing.
# Chromium can keep its main process alive while its renderer or media stack
# hangs, so the launcher's wait/restart loop alone cannot detect this.
set -uo pipefail

browser_pid="${1:?browser PID required}"
dashboard_url="${2:?dashboard URL required}"
log_file="${3:?log file required}"
interval="${WATCHDOG_INTERVAL_SECONDS:-45}"
stale_after="${WATCHDOG_STALE_SECONDS:-180}"
runtime_dir="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
frame="$(mktemp "${runtime_dir}/smart-home-clock.XXXXXX.png")" || exit 1
trap 'rm -f "${frame}"' EXIT

log() { printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "${log_file}"; }

# The clock sits in the shared dashboard header, 160 pixels from the right
# edge. Capture only those pixels: camera video may move while the page clock
# and controls are frozen.
screen_width="$(wlr-randr 2>/dev/null | awk '/current/ {split($1, dimensions, "x"); print dimensions[1]; exit}')"
if [[ ! "${screen_width}" =~ ^[0-9]+$ ]] || (( screen_width < 320 )); then
    log "WARN: watchdog cannot determine display width"
    exit 1
fi
clock_region="$((screen_width - 160)),0 100x55"
last_hash=""
unchanged_since=0
log "watchdog started for browser ${browser_pid}"

while kill -0 "${browser_pid}" 2>/dev/null; do
    sleep "${interval}"
    kill -0 "${browser_pid}" 2>/dev/null || break

    # A board outage must not make the panel churn through browser restarts.
    if ! curl -fsS -o /dev/null --max-time 5 "${dashboard_url}"; then
        last_hash=""
        continue
    fi
    if ! timeout 8 grim -g "${clock_region}" "${frame}" 2>/dev/null; then
        last_hash=""
        continue
    fi
    current_hash="$(sha256sum "${frame}" | cut -d' ' -f1)"
    if [[ "${current_hash}" != "${last_hash}" ]]; then
        last_hash="${current_hash}"
        unchanged_since=${SECONDS}
        continue
    fi
    if (( SECONDS - unchanged_since < stale_after )); then
        continue
    fi

    # Check again just before acting, to avoid a stale sample taken during a
    # dashboard restart. The launcher will relaunch Chromium after it exits.
    if curl -fsS -o /dev/null --max-time 5 "${dashboard_url}"; then
        log "watchdog: visible dashboard clock unchanged for ${stale_after}s; restarting browser ${browser_pid}"
        kill -TERM "${browser_pid}" 2>/dev/null || true
        sleep 10
        if kill -0 "${browser_pid}" 2>/dev/null; then
            log "watchdog: browser did not exit after TERM; forcing exit"
            kill -KILL "${browser_pid}" 2>/dev/null || true
        fi
    fi
    break
done
