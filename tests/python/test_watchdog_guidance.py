"""No document may tell anyone to enable the systemd watchdog on this board.

The SBSA Generic Watchdog here has a fixed 10-second timeout that `SETTIMEOUT`
cannot raise, so `RuntimeWatchdogSec=60s` makes systemd ping every 30 s against
a timer that fires at 10. The board then resets roughly every 80 s with no
kernel panic and an empty pstore — the 2026-09-02 loop, which cost a full
rebuild and, indirectly, the Matter fabric and the north bedroom S505.

`CLAUDE.md` and the recovery handoff were corrected at the time. `docs/local-ai.md`
was not, and sat there for two days still recommending it — in exactly the file
someone reinstalling the AI stack would open. This test is here so a corrected
document cannot quietly regress, in any file, ever again.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Every prose file a person might follow. third_party/ is a vendored dependency
# and not ours to police.
DOC_FILES = sorted(
    p for p in PROJECT_ROOT.rglob("*.md")
    if "third_party" not in p.parts
    and ".git" not in p.parts
    and "node_modules" not in p.parts
)

# "RuntimeWatchdogSec=<something other than 0>", however it is spelled.
ENABLING = re.compile(r"RuntimeWatchdog(?:Sec|USec)\s*=\s*(?!0\b)(\S+)", re.IGNORECASE)

# A line that names the setting only to forbid it, or to explain why it broke the
# board, is the point of the exercise -- those are allowed. Recognised by the
# warning vocabulary in the surrounding paragraph. Deliberately narrow: it has to
# reject the original recommendation, which
# test_the_scanner_would_catch_the_original_wording holds it to.
FORBIDDING = re.compile(
    r"(\bnever\b|\bdo not\b|\bdon't\b|\bmust not\b|\bno longer\b|\bremoved\b"
    r"|\bcorrected\b|\bprime suspect\b|\bearlier revision\b|\bguaranteed reset\b"
    r"|resets the board|cannot be (?:changed|raised)|guarantees it fires"
    r"|is the mechanism)",
    re.IGNORECASE,
)


def _offending_lines(text: str) -> list[tuple[int, str]]:
    lines = text.splitlines()
    out = []
    for i, line in enumerate(lines):
        if not ENABLING.search(line):
            continue
        # Judge the setting in its paragraph, not in isolation: the warning that
        # forbids it usually sits in the sentence before or after.
        window = "\n".join(lines[max(0, i - 4):i + 5])
        if not FORBIDDING.search(window):
            out.append((i + 1, line.strip()))
    return out


def test_docs_exist_to_be_scanned() -> None:
    """A glob that silently matches nothing would make every test below vacuous."""
    assert len(DOC_FILES) >= 5
    assert any(p.name == "local-ai.md" for p in DOC_FILES)


@pytest.mark.parametrize("doc", DOC_FILES, ids=lambda p: str(p.relative_to(PROJECT_ROOT)))
def test_no_document_recommends_enabling_the_watchdog(doc: Path) -> None:
    offending = _offending_lines(doc.read_text(encoding="utf-8"))

    assert not offending, (
        f"{doc.relative_to(PROJECT_ROOT)} appears to recommend enabling the watchdog: "
        f"{offending}. This board's watchdog timeout is fixed at 10 s and cannot be "
        "raised; a non-zero RuntimeWatchdogSec resets it in a loop. If this line "
        "forbids the setting rather than recommending it, say so in the surrounding "
        "sentence."
    )


def test_local_ai_states_the_rule_outright() -> None:
    """The file that used to carry the bad advice must now carry the correction —
    absence of the instruction is not the same as a warning against it."""
    text = (PROJECT_ROOT / "docs" / "local-ai.md").read_text(encoding="utf-8")

    assert "Never set `RuntimeWatchdogSec` on this board" in text
    assert "RuntimeWatchdogUSec=0" in text


def test_the_scanner_would_catch_the_original_wording() -> None:
    """Guards the guard: the exact paragraph that was in local-ai.md until today
    must be something this scanner rejects."""
    original = (
        "**The hard lockup detector is disabled**, so a hang will not self-recover.\n"
        "`/dev/watchdog` exists; enabling `RuntimeWatchdogSec=60s` in\n"
        "`/etc/systemd/system.conf` would let the board reboot itself instead of\n"
        "waiting for a power cycle.\n"
    )
    # Stripped of the phrase that reads as forbidding vocabulary, this is a
    # recommendation and has to be caught.
    bare = original.replace("would let the board reboot itself instead of", "enables")

    assert _offending_lines(bare)
