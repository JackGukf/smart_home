#!/usr/bin/env bash
# Verify the Matter bridge running on the board, from chip-tool.
#
# This drives the *deployed* bridge over the network. It is the counterpart to
# scripts/test-matter-commissioning.sh, which starts a native binary inside the
# dev container and tests that in isolation.
#
# Nothing here needs ssh: the bridge answers Matter on the board's port 5540,
# the bridge sync API is on :8000, and matter-server is on :5580.
#
#   scripts/verify-matter-bridge.sh                  # inventory, read-only
#   scripts/verify-matter-bridge.sh --commission     # pair this chip-tool fabric
#   scripts/verify-matter-bridge.sh --cycle 7        # on/off once on endpoint 7
#   scripts/verify-matter-bridge.sh --cycle 7 --times 2
#
# Environment:
#   PI_HOST        board address              (default 192.168.0.234)
#   CHIP_TOOL      chip-tool binary           (default: first on PATH)
#   NODE_ID        node id in chip-tool       (default 1)
#   STORAGE_DIR    chip-tool fabric storage   (default ~/.chip-tool-bridge)
#
# ── Why one interactive session, not many chip-tool runs ────────────────────
# The bridge is commissioned once and the fabric persists in STORAGE_DIR --
# nothing here re-registers or re-pairs anything. But each *separate* chip-tool
# process must find the node again over DNS-SD before it can talk, and from
# WSL2 that multicast lookup routinely waits out its whole timeout:
#
#     node lookup status for ADEF574ABBDFA616-0000000000000001 after 45002 ms
#
# An earlier version of this script spawned chip-tool per operation and could
# spend 45 s on one attribute read. Driving a single `interactive start`
# session over a FIFO pays discovery once: measured, the four operations after
# the first completed in 32 ms total.
#
# A cycle restores the endpoint to the state it started in, so it is safe to
# run against real lights.
set -euo pipefail

PI_HOST="${PI_HOST:-192.168.0.234}"
CHIP_TOOL="${CHIP_TOOL:-$(command -v chip-tool || true)}"
NODE_ID="${NODE_ID:-1}"
STORAGE_DIR="${STORAGE_DIR:-$HOME/.chip-tool-bridge}"
MATTER_PORT=5540
BRIDGE_API="http://${PI_HOST}:8000"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Generous, because the first command in a session pays DNS-SD discovery.
FIRST_OP_TIMEOUT="${FIRST_OP_TIMEOUT:-70}"
OP_TIMEOUT="${OP_TIMEOUT:-20}"

DO_COMMISSION=0
CYCLE_EP=""
TIMES=1

while [[ $# -gt 0 ]]; do
    case "$1" in
        --commission) DO_COMMISSION=1; shift ;;
        --cycle) CYCLE_EP="$2"; shift 2 ;;
        --times) TIMES="$2"; shift 2 ;;
        -h|--help) sed -n '2,36p' "${BASH_SOURCE[0]}" | sed 's/^# \?//'; exit 0 ;;
        *) echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
done

[[ -n "$CHIP_TOOL" && -x "$CHIP_TOOL" ]] || {
    echo "chip-tool not found. Set CHIP_TOOL=/path/to/chip-tool" >&2; exit 1; }
mkdir -p "$STORAGE_DIR"

# ── The bridge's own view of what it exposes ────────────────────────────────
echo "==> Devices the bridge is told to expose (${BRIDGE_API}/bridge/devices)"
DEVICES_JSON="$(curl -fsS -m 20 "${BRIDGE_API}/bridge/devices")"
python3 - "$DEVICES_JSON" <<'PY'
import json, sys
devices = json.loads(sys.argv[1])
# Endpoints are allocated from 3 upward in list order (kDynamicEndpointStart),
# so this is the endpoint each device should have landed on.
for index, device in enumerate(devices):
    print(f"    ep{3 + index:<3} {device['device_id']:<26} {device['name']}")
print(f"    {len(devices)} device(s)")
PY

# ── Commissioning is a one-off, and needs its own process ───────────────────
if [[ "$DO_COMMISSION" == "1" ]]; then
    echo
    echo "==> Commissioning node ${NODE_ID} at ${PI_HOST}:${MATTER_PORT}"
    echo "    NOTE: CHIP closes the commissioning window ~15 minutes after boot."
    echo "    If this times out in PASE, reopen it and retry:"
    echo "      ssh orangepi@${PI_HOST} systemctl --user restart matter-bridge"
    PASSCODE="$(grep -oP -- '--passcode \K[0-9]+' "$PROJECT_ROOT/configs/matter-bridge.service")"
    "$CHIP_TOOL" pairing already-discovered "$NODE_ID" "$PASSCODE" "$PI_HOST" "$MATTER_PORT" \
        --storage-directory "$STORAGE_DIR" 2>&1 \
        | grep -aE "Commissioning complete|Pairing Failure|Run command failure" || true
fi

# ── One long-lived chip-tool session ────────────────────────────────────────
SESSION_DIR="$(mktemp -d)"
FIFO="${SESSION_DIR}/in"
LOG="${SESSION_DIR}/out"
CT_PID=""

cleanup() {
    if [[ -n "$CT_PID" ]] && kill -0 "$CT_PID" 2>/dev/null; then
        echo "quit" >&3 2>/dev/null || true
        sleep 0.5
        kill "$CT_PID" 2>/dev/null || true
        wait "$CT_PID" 2>/dev/null || true
    fi
    exec 3>&- 2>/dev/null || true
    rm -rf "$SESSION_DIR"
}
trap cleanup EXIT

mkfifo "$FIFO"
: > "$LOG"
"$CHIP_TOOL" interactive start --storage-directory "$STORAGE_DIR" < "$FIFO" > "$LOG" 2>&1 &
CT_PID=$!
# Holding the write end open is what keeps the session alive between commands;
# closing it tells chip-tool its input ended.
exec 3>"$FIFO"

# Send one command and wait for a line matching $2 to appear *after* everything
# already consumed, so a reply is never confused with the previous command's.
#
# The result goes in the global REPLY_LINE rather than stdout: calling this as
# `x="$(send_wait ...)"` would run it in a subshell, CONSUMED would not persist,
# and every call would re-match an older reply -- which showed up as every
# endpoint reporting the first endpoint's name, and states lagging one step.
CONSUMED=0
REPLY_LINE=""
send_wait() {
    local command="$1" pattern="$2" limit="${3:-$OP_TIMEOUT}"
    local line_count match deadline
    REPLY_LINE=""
    # Anything already in the log predates this command.
    CONSUMED="$(wc -l < "$LOG")"
    echo "$command" >&3
    deadline=$(( $(date +%s) + limit ))
    while (( $(date +%s) < deadline )); do
        line_count="$(wc -l < "$LOG")"
        if (( line_count > CONSUMED )); then
            match="$(tail -n "+$((CONSUMED + 1))" "$LOG" | grep -aE "$pattern" | tail -1 || true)"
            if [[ -n "$match" ]]; then
                # Strip ANSI colour and chip-tool's leading timestamp/pid block.
                REPLY_LINE="$(sed 's/\x1b\[[0-9;]*[A-Za-z]//g; s/^\[[^]]*\] *\[[^]]*\] *\[[^]]*\] *//' <<<"$match")"
                CONSUMED="$line_count"
                return 0
            fi
        fi
        sleep 0.2
    done
    return 1
}

field() { sed "s/.*$1 *//" <<<"$2"; }

# ── Is this chip-tool fabric actually commissioned? ─────────────────────────
# Without this the endpoint list below is simply empty, which reads as "the
# bridge registered nothing" when the truth is "this storage directory was
# never paired". Different problems, different fixes.
echo
if ! send_wait "descriptor read parts-list ${NODE_ID} 1" "PartsList:" "$FIRST_OP_TIMEOUT"; then
    cat >&2 <<EOF

ERROR: chip-tool cannot reach node ${NODE_ID}.

  Storage directory: ${STORAGE_DIR}

  The fabric lives in that directory. If it was never paired -- or you are
  using a different --storage-directory than you commissioned with -- there is
  no fabric here and every read fails.

  Commission this one:
      $(basename "${BASH_SOURCE[0]}") --commission

  If commissioning times out during PASE, the bridge's window has closed
  (CHIP shuts it ~15 min after boot). Reopen it and retry:
      ssh orangepi@${PI_HOST} systemctl --user restart matter-bridge
EOF
    exit 1
fi

# ── What the bridge actually registered ─────────────────────────────────────
echo "==> Endpoints registered on the bridge"
for ep in $(python3 -c "
import json,sys
print(' '.join(str(3+i) for i in range(len(json.loads(sys.argv[1])))))" "$DEVICES_JSON"); do
    send_wait "bridgeddevicebasicinformation read node-label ${NODE_ID} ${ep}" "NodeLabel:" || true
    label_line="$REPLY_LINE"
    send_wait "onoff read on-off ${NODE_ID} ${ep}" "OnOff:" || true
    state_line="$REPLY_LINE"
    if [[ -z "$label_line" ]]; then
        printf '    ep%-3s %-28s NOT REGISTERED (look for "will NOT be bridged" in matter-bridge.log)\n' "$ep" "-"
    else
        printf '    ep%-3s %-28s OnOff=%s\n' "$ep" "$(field 'NodeLabel:' "$label_line")" \
            "$(field 'OnOff:' "$state_line")"
    fi
done

[[ -n "$CYCLE_EP" ]] || { echo; echo "Read-only run. Add --cycle <endpoint> to exercise a device."; exit 0; }

# ── Exercise one endpoint ───────────────────────────────────────────────────
DEVICE_ID="$(python3 -c "
import json,sys
devices = json.loads(sys.argv[1])
index = int(sys.argv[2]) - 3
print(devices[index]['device_id'] if 0 <= index < len(devices) else '')" "$DEVICES_JSON" "$CYCLE_EP")"
[[ -n "$DEVICE_ID" ]] || { echo "No device maps to endpoint ${CYCLE_EP}" >&2; exit 1; }

# The device's real state, independent of anything the bridge recorded. For a
# bridged Matter node that means asking matter-server; otherwise the bridge
# cache is the best available witness, and it is written only after the vendor
# library returned, so it does still mean the device was driven.
truth() {
    if [[ "$DEVICE_ID" == matter:* ]]; then
        python3 "$PROJECT_ROOT/scripts/matter_node_state.py" "${DEVICE_ID#matter:}" \
            --host "$PI_HOST" 2>/dev/null | sed 's/^/        /' || true
    else
        curl -fsS -m 20 "${BRIDGE_API}/bridge/state/all" \
            | python3 -c "
import json,sys
print('        bridge cache:', json.load(sys.stdin).get(sys.argv[1]))" "$DEVICE_ID"
    fi
}

echo
echo "==> Exercising ep${CYCLE_EP} (${DEVICE_ID}), ${TIMES} on/off cycle(s)"
send_wait "onoff read on-off ${NODE_ID} ${CYCLE_EP}" "OnOff:" || REPLY_LINE="OnOff: UNKNOWN"
BASELINE="$(field 'OnOff:' "$REPLY_LINE")"
echo "    baseline OnOff=${BASELINE}"
truth

for ((i = 1; i <= TIMES; i++)); do
    for cmd in on off; do
        echo "    -- cycle ${i}: ${cmd} --"
        send_wait "onoff ${cmd} ${NODE_ID} ${CYCLE_EP}" "Status=0x" || true
        status_line="$REPLY_LINE"
        if [[ -z "$status_line" ]]; then
            # The first command after an idle period can lose a CASE session
            # re-establishment. One retry distinguishes that from a real fault.
            echo "        no status returned; retrying once"
            send_wait "onoff ${cmd} ${NODE_ID} ${CYCLE_EP}" "Status=0x" || true
            status_line="$REPLY_LINE"
        fi
        echo "        $(grep -oE 'Status=0x[0-9a-f]+' <<<"${status_line:-}" | tail -1 || echo 'no status')"
        sleep 2
        send_wait "onoff read on-off ${NODE_ID} ${CYCLE_EP}" "OnOff:" || REPLY_LINE="OnOff: UNKNOWN"
        echo "        bridge attribute: $(field 'OnOff:' "$REPLY_LINE")"
        truth
    done
done

if [[ "$BASELINE" == "TRUE" ]]; then
    send_wait "onoff on ${NODE_ID} ${CYCLE_EP}" "Status=0x" || true
    echo "    restored to ON"
else
    echo "    left OFF (matches baseline)"
fi
