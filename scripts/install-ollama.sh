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
# The tag Ollama pulls, and the tag this board actually serves.  They differ
# because the served one carries a num_thread that MUST match the pinned core
# count -- see "the model" below for what happens when it does not.
BASE_MODEL="${OLLAMA_BASE_MODEL:-qwen3:4b}"
MODEL="${OLLAMA_MODEL:-qwen3:4b-house}"
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

# systemd prints CPUAffinity as ranges, e.g. "0-1 6-11".  Count them, so the
# thread count is derived from the pinning rather than repeated beside it.
cpuset_count() {
  local spec="$1" total=0 part lo hi
  for part in ${spec//,/ }; do
    if [[ "${part}" == *-* ]]; then
      lo="${part%%-*}"; hi="${part##*-}"
      total=$(( total + hi - lo + 1 ))
    elif [[ -n "${part}" ]]; then
      total=$(( total + 1 ))
    fi
  done
  printf '%s' "${total}"
}

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

info "Fetching ${BASE_MODEL}"
if ollama list 2>/dev/null | awk 'NR>1 {print $1}' | grep -qx "${MODEL}"; then
  ok "${MODEL} already built"
elif ollama list 2>/dev/null | awk 'NR>1 {print $1}' | grep -qx "${BASE_MODEL}"; then
  ok "${BASE_MODEL} already present"
else
  ollama pull "${BASE_MODEL}" || die "could not pull ${BASE_MODEL}"
  ok "pulled ${BASE_MODEL}"
fi

# The thread count is the other half of the pinning, and the half that is easy
# to forget.  Ollama has no OLLAMA_NUM_THREADS: llama-server picks its own count
# from the machine's CPUs, not from the cgroup's cpuset.  Pinned to 8 cores it
# still oversubscribed them, and llama.cpp spin-waits at every graph barrier --
# so it burned 720% CPU and emitted ZERO tokens in 200s.  It does not fail, it
# simply never finishes.
#
# num_thread must therefore equal the number of pinned cores.  Derived here
# rather than written down twice, so the two cannot drift apart.
info "Matching the thread count to the pinned cores"
affinity="$(systemctl show ollama.service -p CPUAffinity --value)"
if [[ -n "${affinity}" ]]; then
  THREADS="$(cpuset_count "${affinity}")"
  ok "CPUAffinity=${affinity} -> num_thread ${THREADS}"
else
  THREADS="$(nproc)"
  warn "no CPUAffinity set; using num_thread ${THREADS} (all cores)"
fi
(( THREADS > 0 )) || die "computed a thread count of ${THREADS} from '${affinity}'"

if [[ "$(ollama show "${MODEL}" --parameters 2>/dev/null | awk '$1=="num_thread"{print $2}')" != "${THREADS}" ]]; then
  modelfile="$(mktemp /tmp/Modelfile.XXXXXX)"
  {
    echo "FROM ${BASE_MODEL}"
    echo "# Must equal the core count in the ollama.service drop-in CPUAffinity."
    echo "PARAMETER num_thread ${THREADS}"
  } > "${modelfile}"
  ollama create "${MODEL}" -f "${modelfile}" >/dev/null 2>&1 || die "could not build ${MODEL}"
  rm -f "${modelfile}"
  ok "built ${MODEL} with num_thread=${THREADS}"
else
  ok "${MODEL} already carries num_thread=${THREADS}"
fi

# Retire the un-parameterised tag.  Leaving it reachable is a footgun: a caller
# who names it gets the 720%-CPU stall described above.  The blobs are shared
# and refcounted, so this frees no disk and costs no re-download.
if ollama list 2>/dev/null | awk 'NR>1 {print $1}' | grep -qx "${BASE_MODEL}"; then
  ollama rm "${BASE_MODEL}" >/dev/null 2>&1 && ok "retired the unpinned ${BASE_MODEL} tag"
fi

# -------------------------------------------------------------- does it answer

# The regression guard for all of the above.  A stalled runner returns no error,
# it simply never responds, so this asserts an answer arrives in bounded time.
info "Smoke test"
started="$(date +%s)"
if ! curl -sS --max-time 180 http://127.0.0.1:11434/api/chat -o /tmp/ollama-smoke.json -d "{
      \"model\": \"${MODEL}\", \"stream\": false,
      \"options\": {\"num_predict\": 400},
      \"messages\": [{\"role\":\"user\",\"content\":\"Reply with the single word: ready\"}]
    }"; then
  die "no answer within 180s.

That is the oversubscription stall, not a slow board: check that num_thread
matches the CPUAffinity core count.
  systemctl show ollama.service -p CPUAffinity
  ollama show ${MODEL} --parameters"
fi
elapsed=$(( $(date +%s) - started ))

SMOKE_ELAPSED="${elapsed}" python3 -c '
import json, os, sys
d = json.load(open("/tmp/ollama-smoke.json"))
m = d.get("message", {})
gen = d.get("eval_count") or 0
dur = (d.get("eval_duration") or 1) / 1e9
content = (m.get("content") or "").strip()
print("  ok   answered in %ss: %r" % (os.environ["SMOKE_ELAPSED"], content[:40]))
print("  ok   %d tokens at %.1f tok/s" % (gen, gen / dur))
# Qwen3 reasons first. With a generous budget the reasoning lands in
# message.thinking and the answer in message.content; with a small one the
# budget is spent reasoning and content comes back EMPTY.
if not content:
    print("  !    content was empty - num_predict too small for a thinking model")
    sys.exit(1)
' || die "the model did not return usable content"

# --------------------------------------------------------------------- summary

cat <<EOF

$(printf '\033[1mDone. Ollama is the only LLM on the board.\033[0m')

Call it like this.  Qwen3 reasons before answering and the reasoning is
separated into message.thinking, so read message.content -- and give it a
generous num_predict, because a small budget is spent reasoning and returns an
EMPTY content.  Do NOT pass "think": false; on this version it stops separating
the reasoning and returns it AS the answer.

  curl -s http://127.0.0.1:11434/api/chat -d '{
    "model": "${MODEL}", "stream": false,
    "options": {"num_predict": 400},
    "messages": [{"role":"user","content":"Reply with the single word: ready"}]
  }' | python3 -c 'import json,sys; print(json.load(sys.stdin)["message"]["content"])'

${MODEL} carries num_thread=${THREADS} to match the pinned cores.  If you ever
add a model, give it the same parameter -- an unpinned tag stalls at 720% CPU
without ever answering.

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
