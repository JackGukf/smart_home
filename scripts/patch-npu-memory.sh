#!/usr/bin/env bash
# Give the NPU driver 1 GiB instead of 4 GiB, and get 3 GB of the board back.
#
# aipu.ko sizes its DMA memory from how much RAM the board has (aipu_mm.c,
# aipu_mm_add_iova_region): 6 x 1 GiB above 16 GB, **4 x 1 GiB on this 16 GB
# board**, 1 x 1 GiB on 4-8 GB boards, 256 MB below that. It takes it when the
# module loads, used or not, and never gives it back. Our YOLOv8n detector uses
# a sliver of one region, so the board loses 3 GB to nothing - on a machine with
# no swap.
#
# There are no kernel headers for 6.6.89-cix on the board and none in the
# archives, so the module cannot be rebuilt from /usr/src/aipu-5.11.0. Instead
# this changes one instruction in the compiled module:
#
#     .text+0x7944   mov w23, #0x4   ->   mov w23, #0x1
#
# w23 is the region count. It is the loop bound *and* the "only one region" test
# a few instructions later, so setting it to 1 puts the driver on exactly the
# path it takes on a 4-8 GB board - the same instruction word (0x52800037) the
# driver itself writes there at .text+0x7d34, with the same 1 GiB region size.
# Module signing and MODVERSIONS are off on this kernel, so a patched module
# loads normally (the module is already tainted O, out-of-tree).
#
# Measured 2026-09-19: DMA memory 4193 MB -> 1121 MB, available RAM 6.8 -> 11.0 GB,
# detector unchanged on all five cameras.
#
# A kernel or driver package update replaces aipu.ko - run this again after one.
# Idempotent: it says so and does nothing if the module is already patched.
#
#   sudo scripts/patch-npu-memory.sh            # patch, reload, verify
#   sudo scripts/patch-npu-memory.sh --check    # report only, change nothing
#   sudo scripts/patch-npu-memory.sh --restore  # put the backup back
set -euo pipefail

MODULE="/lib/modules/$(uname -r)/extra/aipu.ko"
BACKUP_DIR="${SUDO_USER:+/home/$SUDO_USER}/npu-driver-backup"
BACKUP="$BACKUP_DIR/aipu.ko.orig-$(uname -r)"
OFFSET=$((0x7984))          # .text file offset 0x40 + 0x7944
FOUR="97008052"             # mov w23, #0x4, little endian
ONE="37008052"              # mov w23, #0x1
UNIT="npu-detector.service"
MODE="${1:---apply}"

# od, not xxd: xxd is not installed on the board.
at_offset() { od -An -tx1 -j "$OFFSET" -N 4 "$1" | tr -d " \n"; }

dma_mb() { awk '/dma_common_pages_remap/ {s+=$2} END {printf "%.0f", s/1048576}' /proc/vmallocinfo; }

[[ $EUID -eq 0 ]] || { echo "run with sudo: sudo $0 $MODE" >&2; exit 1; }
[[ -f $MODULE ]] || { echo "no $MODULE" >&2; exit 1; }

case "$(at_offset "$MODULE")" in
    "$FOUR") STATE=stock ;;
    "$ONE")  STATE=patched ;;
    *) echo "unexpected bytes at $OFFSET: $(at_offset "$MODULE") - the module changed, patch by hand" >&2; exit 1 ;;
esac

reload() {
    local was_running=no
    systemctl --user --machine="${SUDO_USER:-orangepi}@" is-active "$UNIT" >/dev/null 2>&1 && was_running=yes
    [[ $was_running == yes ]] && systemctl --user --machine="${SUDO_USER:-orangepi}@" stop "$UNIT"
    sleep 2
    rmmod aipu
    depmod -a
    modprobe aipu
    sleep 2
    [[ $was_running == yes ]] && systemctl --user --machine="${SUDO_USER:-orangepi}@" start "$UNIT"
    echo "NPU driver reloaded; detector $([[ $was_running == yes ]] && echo restarted || echo left stopped)"
}

case "$MODE" in
    --check)
        echo "$MODULE is $STATE ($(at_offset "$MODULE"))"
        echo "driver DMA memory now: $(dma_mb) MB"
        ;;
    --apply)
        if [[ $STATE == patched ]]; then
            echo "already patched; nothing to do (DMA memory $(dma_mb) MB)"
            exit 0
        fi
        mkdir -p "$BACKUP_DIR"
        cp -p "$MODULE" "$BACKUP"
        echo "backed up to $BACKUP"
        echo "DMA memory before: $(dma_mb) MB"
        printf '\x37' | dd of="$MODULE" bs=1 seek="$OFFSET" conv=notrunc status=none
        [[ $(at_offset "$MODULE") == "$ONE" ]] || { cp -p "$BACKUP" "$MODULE"; echo "patch did not take; restored" >&2; exit 1; }
        reload
        echo "DMA memory after: $(dma_mb) MB"
        ;;
    --restore)
        [[ -f $BACKUP ]] || { echo "no backup at $BACKUP" >&2; exit 1; }
        cp -p "$BACKUP" "$MODULE"
        reload
        echo "restored; DMA memory $(dma_mb) MB"
        ;;
    *)
        echo "usage: sudo $0 [--apply|--check|--restore]" >&2
        exit 1
        ;;
esac
