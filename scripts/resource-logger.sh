#!/usr/bin/env bash
#
# Append a one-line resource snapshot to a file that survives a reboot.
#
# Why this exists: on 2026-09-02 the board became unreachable after several
# hours and had to be power-cycled, and the cause could not be determined
# because journald on this image is Storage=volatile - the previous boot's logs
# are discarded. rsyslog keeps /var/log/syslog, but only root can read it.
#
# This writes somewhere the login user can always read afterwards, so the next
# occurrence leaves evidence: what memory looked like in the minutes before, and
# whether temperature was climbing.
#
# It is deliberately tiny - no dependencies, one append per interval - because a
# monitor that contributes to the problem it is watching for is worse than none.
set -uo pipefail

LOG_FILE="${RESOURCE_LOG:-${HOME}/resource-history.log}"
INTERVAL="${RESOURCE_INTERVAL:-30}"
MAX_BYTES="${RESOURCE_LOG_MAX_BYTES:-20000000}"   # ~20MB, weeks of history

hottest() {
    local max=0 t
    for t in /sys/class/thermal/thermal_zone*/temp; do
        [[ -r "$t" ]] || continue
        read -r v < "$t" 2>/dev/null || continue
        (( v > max )) && max=$v
    done
    echo $(( max / 1000 ))
}

# Mark the boundary so a reboot is obvious when reading the file back.
printf '%s BOOT uptime=%s\n' "$(date -Is)" "$(cut -d. -f1 /proc/uptime)" >> "${LOG_FILE}"

while true; do
    # Rotate by truncating rather than deleting: keeps the file handle valid and
    # cannot fill the disk, which would itself take the board down.
    if [[ -f "${LOG_FILE}" ]] && (( $(stat -c %s "${LOG_FILE}" 2>/dev/null || echo 0) > MAX_BYTES )); then
        tail -c $(( MAX_BYTES / 2 )) "${LOG_FILE}" > "${LOG_FILE}.tmp" && mv "${LOG_FILE}.tmp" "${LOG_FILE}"
    fi

    read -r _ total used free shared buffcache available < <(free -m | sed -n 2p)
    read -r load1 load5 _ < /proc/loadavg
    # Top three by resident size - enough to see which process was growing.
    top3="$(ps -eo rss,comm --sort=-rss --no-headers 2>/dev/null | head -3 |
            awk '{printf "%s=%dM ", $2, $1/1024}')"

    printf '%s mem_used=%sM avail=%sM load=%s/%s temp=%sC %s\n' \
        "$(date -Is)" "${used}" "${available}" "${load1}" "${load5}" "$(hottest)" "${top3}" \
        >> "${LOG_FILE}"

    sleep "${INTERVAL}"
done
