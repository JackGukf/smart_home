#!/usr/bin/env bash
#
# Phase 3 step 1 of the local-AI restore: Ollama, alone.  Run it ON the Orange Pi.
#
#   ssh orangepi@192.168.0.234
#   cd smart_home_AI && ./scripts/install-ollama.sh
#
# Ollama goes back first -- ahead of llama-server, which is faster -- because it
# unloads an idle model and returns the memory.  On a board with 15 GiB, no swap
# and a day job of running the house, that property outranks throughput.
#
# The board has no swap, so memory pressure does not degrade: it hits a wall and
# the kernel kills whichever process asks for memory next, which is very likely
# Home Assistant.  This script therefore installs a drop-in that caps the
# service, and refuses to run a second LLM alongside it.
#
# It also asserts the watchdog is disarmed before and after.  A 60 s
# RuntimeWatchdogSec against this SoC's fixed 10 s SBSA timer is what reset the
# board every ~80 s on 2026-09-02 and cost a full rebuild; nothing here may
# reintroduce it, including anything the vendor installer writes.
#
# Safe to re-run.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DROPIN_SRC="${PROJECT_ROOT}/deploy/systemd/system/ollama.service.d/override.conf"
DROPIN_DIR="/etc/systemd/system/ollama.service.d"
MODEL="${OLLAMA_MODEL:-qwen3:4b}"
INSTALLER_URL="https://ollama.com/install.sh"

# Same sudo resolution as backup-smart-home.sh: passwordless if the host allows
# it, an askpass helper for unattended runs, otherwise prompt on the terminal.
if sudo -n true 2>/dev/null; then
  SUDO="sudo -n"
elif [[ -n "${SUDO_ASKPASS:-}" && -x "${SUDO_ASKPASS}" ]]; then
  SUDO="sudo -A"
else
  SUDO="sudo"
fi

info() { printf '\n\033[1m%s\033[0m\n' "$*"; }
ok()   { printf '  \033[32mok\033[0m   %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m    %s\n' "$*" >&2; }
die()  { printf '\n\033[31mERROR\033[0m: %s\n' "$*" >&2; exit 1; }

# --------------------------------------------------------------- preconditions

info "Checking preconditions"

[[ -r "${DROPIN_SRC}" ]] || die "missing ${DROPIN_SRC} - is this the project root?"

# The watchdog. Checked first because if this is wrong, nothing else matters.
watchdog="$(systemctl show -p RuntimeWatchdogUSec --value)"
if [[ "${watchdog}" != "0" && "${watchdog}" != "off" ]]; then
  die "RuntimeWatchdogUSec=${watchdog}, expected 0.

This board's SBSA watchdog has a FIXED 10-second timeout that SETTIMEOUT cannot
raise, so any non-zero setting resets the board roughly every 80 seconds with no
kernel panic and an empty pstore.  That is the 2026-09-02 reset loop.
Fix it before installing anything:

  sudo sed -i 's/^RuntimeWatchdogSec=.*/#&/' /etc/systemd/system.conf
  sudo systemctl daemon-reexec

See docs/handoff-2026-09-03-recovery.md, 'Best current theory (revised)'."
fi
ok "RuntimeWatchdogUSec=0"

# One LLM, not both.  llama-server holds ~5.0 GiB for the life of the process
# and Ollama wants ~3.5 GiB more; together they leave ~0.4 GiB for Home
# Assistant, Zigbee2MQTT, go2rtc, matter-server and the dashboard.
if systemctl --user is-active --quiet llama-server.service 2>/dev/null; then
  die "llama-server.service is running.

Run one LLM, not both -- llama-server holds ~5.0 GiB permanently and Ollama
loading a model is ~3.5 GiB more, which does not fit beside the house services
on a board with no swap.  Stop it first if you mean to switch:

  systemctl --user disable --now llama-server.service"
fi
ok "no second LLM running"

# Persistent logs, so the next unexplained event is diagnosable.  Not fatal.
if [[ ! -d /var/log/journal ]]; then
  warn "journald is not persistent - the next incident loses its evidence."
  warn "  sudo mkdir -p /var/log/journal && sudo systemctl restart systemd-journald"
else
  ok "journald persistent"
fi

# The evidence trail that made the last incident solvable at all.
if systemctl --user is-active --quiet resource-logger.service 2>/dev/null; then
  ok "resource-logger running"
else
  warn "resource-logger.service is not running - start it before the soak:"
  warn "  systemctl --user enable --now resource-logger.service"
fi

avail_mb="$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)"
if (( avail_mb < 5000 )); then
  die "only ${avail_mb} MiB available; ${MODEL} needs ~3.5 GiB with room to spare"
fi
ok "${avail_mb} MiB available"

# --------------------------------------------------------------------- install

if command -v ollama >/dev/null 2>&1; then
  info "Ollama already installed"
  ok "$(ollama --version 2>&1 | head -n 1)"
else
  info "Installing Ollama"
  # Downloaded and inspected rather than piped straight into a root shell, so
  # there is a copy of exactly what ran on this board.
  installer="$(mktemp /tmp/ollama-install.XXXXXX.sh)"
  curl -fsSL "${INSTALLER_URL}" -o "${installer}" || die "could not download ${INSTALLER_URL}"
  printf '  downloaded %s (%s bytes, sha256 %s)\n' \
    "${installer}" "$(stat -c%s "${installer}")" "$(sha256sum "${installer}" | cut -c1-16)"
  ${SUDO} sh "${installer}" || die "the Ollama installer failed"
  command -v ollama >/dev/null 2>&1 || die "ollama is still not on PATH after install"
  ok "installed $(ollama --version 2>&1 | head -n 1)"
fi

# ---------------------------------------------------------------- the drop-in

info "Installing the systemd drop-in"
${SUDO} mkdir -p "${DROPIN_DIR}"
${SUDO} install -m 644 "${DROPIN_SRC}" "${DROPIN_DIR}/override.conf"
ok "${DROPIN_DIR}/override.conf"
${SUDO} systemctl daemon-reload
${SUDO} systemctl enable ollama.service >/dev/null 2>&1 || true
${SUDO} systemctl restart ollama.service

# ---------------------------------------------------------------- verification

info "Verifying the guards are real, not just written down"

# A setting systemd ignores looks identical to one it enforces, in the file.
# Ask systemd what it actually applied.
mem_max="$(systemctl show ollama.service -p MemoryMax --value)"
[[ "${mem_max}" == "5368709120" ]] || die "MemoryMax is '${mem_max}', expected 5368709120 (5G) - the cap is not in force"
ok "MemoryMax=5G enforced"

oom="$(systemctl show ollama.service -p OOMPolicy --value)"
[[ "${oom}" == "stop" ]] || die "OOMPolicy is '${oom}', expected stop - it would restart into the wall"
ok "OOMPolicy=stop"

affinity="$(systemctl show ollama.service -p CPUAffinity --value)"
[[ -n "${affinity}" ]] || warn "CPUAffinity is empty - generation will be ~31% slower than it needs to be"
[[ -n "${affinity}" ]] && ok "CPUAffinity=${affinity}"

# Loopback only.  A model endpoint reachable from the LAN is a model endpoint
# reachable by anything on the LAN.
if ss -lntp 2>/dev/null | grep -q '127.0.0.1:11434'; then
  ok "listening on 127.0.0.1:11434 only"
elif ss -lnt 2>/dev/null | grep -q '0.0.0.0:11434\|\*:11434'; then
  die "ollama is listening on all interfaces - the drop-in did not take effect"
else
  warn "could not confirm the listen address; check with: ss -lnt | grep 11434"
fi

# The installer writes system units. Confirm it did not arm anything.
watchdog_after="$(systemctl show -p RuntimeWatchdogUSec --value)"
[[ "${watchdog_after}" == "0" || "${watchdog_after}" == "off" ]] \
  || die "RuntimeWatchdogUSec became '${watchdog_after}' during install - disarm it NOW, see the note above"
ok "RuntimeWatchdogUSec still 0"

# ------------------------------------------------------------------- the model

info "Fetching ${MODEL}"
if ollama list 2>/dev/null | awk 'NR>1 {print $1}' | grep -qx "${MODEL}"; then
  ok "${MODEL} already present"
else
  ollama pull "${MODEL}" || die "could not pull ${MODEL}"
  ok "pulled ${MODEL}"
fi

# --------------------------------------------------------------------- summary

cat <<EOF

$(printf '\033[1mDone. Ollama is the only LLM on the board.\033[0m')

Smoke test (thinking off, or a short budget returns an empty reply -- Qwen3
reasons first and the reasoning consumes the token budget):

  curl -s http://127.0.0.1:11434/api/chat -d '{
    "model": "${MODEL}", "stream": false,
    "think": false,
    "messages": [{"role":"user","content":"Reply with the single word: ready"}]
  }' | python3 -c 'import json,sys; print(json.load(sys.stdin)["message"]["content"])'

Then soak it for 24 h before adding anything else.  The one thing to prove is
that an idle model is actually unloaded and the memory comes back:

  ollama ps                                   # empty ~5 min after the last call
  systemctl show ollama.service -p MemoryCurrent
  grep BOOT ~/resource-history.log            # must gain no new entries

Reach it from the workstation over a tunnel, never by widening the bind address:

  ssh -N -L 11434:127.0.0.1:11434 orangepi@192.168.0.234

Rollback is one command:

  sudo systemctl disable --now ollama.service
EOF
