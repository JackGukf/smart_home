#!/usr/bin/env bash
#
# Bring Zigbee2MQTT back after the coordinator is unplugged and re-plugged.
#
# Why this exists.  Three things line up to make an unplug permanent:
#
#   1. Zigbee2MQTT exits on purpose when the adapter goes away
#      ("Adapter disconnected, stopping", exit code 2).  It never retries.
#   2. docker-compose.zigbee.yml maps the dongle by its /dev/serial/by-id
#      path.  While that path is missing, Docker cannot even create the
#      container, so `restart: unless-stopped` fails at the host-config stage
#      instead of retrying the process.
#   3. Nothing re-checks once the device node comes back.
#
# Observed 2026-09-02: a replug left the bridge down for 66 minutes.  This
# watcher closes the gap by starting the container whenever the adapter is
# present and the container is not running.
#
# It runs as a systemd *user* unit (deploy/systemd/user/zigbee-adapter-watch.service)
# because the board's login user is already in the docker group and has
# lingering enabled - no root, and no loosening of the container's device
# isolation.
#
# Escape hatch: create deploy/zigbee/.autostart-disabled to stop this from
# starting the container, e.g. while re-flashing the dongle.

# Deliberately not -e: a failed docker call must not kill the watcher.
set -uo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${PROJECT_ROOT}/.env"
COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.zigbee.yml"
DISABLE_FLAG="${PROJECT_ROOT}/deploy/zigbee/.autostart-disabled"

CONTAINER="${ZIGBEE_CONTAINER:-zigbee2mqtt}"
# How long to wait after the device node appears before touching Docker: the
# by-id symlink shows up a moment before the tty is usable.
SETTLE_SECONDS="${ZIGBEE_SETTLE_SECONDS:-5}"
# Safety net, in case a udev event is missed entirely.
POLL_SECONDS="${ZIGBEE_POLL_SECONDS:-60}"

log() { printf '%s zigbee-adapter-watch: %s\n' "$(date -Is)" "$*"; }

# ZIGBEE_ADAPTER lives in .env next to the broker credentials.  Read only that
# one key rather than sourcing the file, which also holds secrets.
adapter_path() {
  if [[ -n "${ZIGBEE_ADAPTER:-}" ]]; then
    printf '%s\n' "${ZIGBEE_ADAPTER}"
    return
  fi
  [[ -r "${ENV_FILE}" ]] || return 0
  sed -n 's/^[[:space:]]*ZIGBEE_ADAPTER=//p' "${ENV_FILE}" | tail -n 1 | tr -d "\"'"
}

container_state() {
  docker inspect -f '{{.State.Status}}' "${CONTAINER}" 2>/dev/null
}

start_container() {
  # `docker start` keeps the existing container. If it fails - typically
  # because the by-id path changed and the stored device mapping is stale -
  # recreate from compose so the new ZIGBEE_ADAPTER takes effect.
  if docker start "${CONTAINER}" >/dev/null 2>&1; then
    log "started ${CONTAINER}"
    return 0
  fi
  log "docker start failed; recreating from compose"
  if [[ -r "${COMPOSE_FILE}" ]] &&
     (cd "${PROJECT_ROOT}" && docker compose -f "${COMPOSE_FILE}" up -d "${CONTAINER}" >/dev/null 2>&1); then
    log "recreated ${CONTAINER} from ${COMPOSE_FILE##*/}"
    return 0
  fi
  log "ERROR could not start ${CONTAINER}; see 'docker logs ${CONTAINER}'"
  return 1
}

ensure_running() {
  local adapter state
  adapter="$(adapter_path)"

  if [[ -z "${adapter}" ]]; then
    log "ZIGBEE_ADAPTER is not set in ${ENV_FILE}; nothing to watch"
    return 0
  fi
  # No dongle plugged in: nothing to do. This is the normal state mid-replug.
  [[ -e "${adapter}" ]] || return 0

  if [[ -e "${DISABLE_FLAG}" ]]; then
    return 0
  fi

  state="$(container_state)"
  if [[ -z "${state}" ]]; then
    log "container ${CONTAINER} does not exist; run scripts/install-zigbee2mqtt.sh"
    return 0
  fi
  [[ "${state}" == "running" ]] && return 0

  log "adapter present but ${CONTAINER} is ${state}; recovering"
  sleep "${SETTLE_SECONDS}"
  # Re-check: the dongle may have been pulled again during the settle window.
  [[ -e "${adapter}" ]] || { log "adapter vanished during settle; will retry"; return 0; }
  start_container
}

# Block until a tty device is added or removed, or POLL_SECONDS elapses,
# whichever comes first. udevadm monitor needs no privileges.
wait_for_change() {
  local buf=(); command -v stdbuf >/dev/null 2>&1 && buf=(stdbuf -oL)
  timeout "${POLL_SECONDS}" "${buf[@]}" udevadm monitor --udev --subsystem-match=tty 2>/dev/null |
    grep -qm1 -E '(^|[[:space:]])(add|remove|bind|unbind)([[:space:]]|$)'
  return 0
}

log "watching $(adapter_path) for ${CONTAINER} (poll ${POLL_SECONDS}s, settle ${SETTLE_SECONDS}s)"
while true; do
  ensure_running
  wait_for_change
done
