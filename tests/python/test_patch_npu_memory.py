"""The one-instruction patch that gives the NPU driver 1 GiB instead of 4 GiB.

The script runs on the board with root, so what is testable here is that it
keeps saying the same thing as the driver source and the module it patches:
the byte it looks for, the byte it writes, and that it can undo itself.
"""
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "patch-npu-memory.sh"


def test_it_swaps_exactly_one_known_instruction():
    text = SCRIPT.read_text(encoding="utf-8")
    # mov w23,#4 -> mov w23,#1, little endian, at .text file offset 0x40 + 0x7944.
    assert 'FOUR="97008052"' in text and 'ONE="37008052"' in text
    assert "OFFSET=$((0x7984))" in text
    assert "seek=\"$OFFSET\"" in text and "conv=notrunc" in text
    # One byte, and only when the module is the stock one.
    assert r"printf '\x37'" in text and "bs=1" in text
    assert "unexpected bytes" in text


def test_it_backs_up_first_and_can_restore():
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'cp -p "$MODULE" "$BACKUP"' in text
    assert "--restore" in text and 'cp -p "$BACKUP" "$MODULE"' in text
    # Idempotent: a second run changes nothing, so it is safe after a kernel update.
    assert "already patched; nothing to do" in text
    # The detector is stopped around the reload and put back as it was found.
    assert "npu-detector.service" in text and "rmmod aipu" in text and "modprobe aipu" in text


def test_xxd_is_not_used_because_the_board_has_no_xxd():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "xxd -p" not in text.split("# od, not xxd")[1]
    assert "od -An -tx1" in text
