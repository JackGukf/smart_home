"""The stylesheet parses, and the rules the whole dashboard leans on are there.

This exists because of build 236. Deleting the old zone-tile rules by pattern
cut two blocks' closing braces, so every rule after that point sat inside an
unterminated @media and the browser dropped it: the dashboard rendered with no
styles at all, every view visible at once, and the wall panel - suddenly asked
to lay out eight camera feeds it normally hides - stopped responding. Nothing in
the suite noticed, because every test asserted on the *text* of the file.

A braces check is cheap and catches the whole family: a truncated file, a
deleted closing brace, a stray one.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STYLES = PROJECT_ROOT / "src" / "python" / "web_static" / "styles.css"


def _without_comments_and_strings(css: str) -> str:
    """Braces inside /* … */ or "…" are text, not structure."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return re.sub(r'"[^"\n]*"|\'[^\'\n]*\'', '""', css)


def test_every_block_is_closed() -> None:
    css = _without_comments_and_strings(STYLES.read_text(encoding="utf-8"))

    depth, line, opened_at = 0, 1, []
    for char in css:
        if char == "\n":
            line += 1
        elif char == "{":
            depth += 1
            opened_at.append(line)
        elif char == "}":
            depth -= 1
            assert depth >= 0, f"stray closing brace at line {line}"
            opened_at.pop()

    assert depth == 0, (
        f"{depth} block(s) never closed, first opened at line {opened_at[0]}; "
        "everything after it is inside that block and the browser drops it"
    )


def test_the_rules_that_hold_the_page_together_are_present() -> None:
    """The ones whose absence is not a missing detail but a broken page."""
    css = STYLES.read_text(encoding="utf-8")

    for rule in (
        ".view-panel",          # inactive views are hidden; without it, all of them show
        "body {",               # the ground colour, and the dark theme with it
        "main {",               # the sidebar/content split
        ".home-layout",         # the Home card grid
    ):
        assert rule in css, f"{rule} is gone"


@pytest.mark.parametrize("selector", [".view-panel", ".view-panel.active"])
def test_views_are_hidden_until_they_are_active(selector: str) -> None:
    css = _without_comments_and_strings(STYLES.read_text(encoding="utf-8"))
    at = css.index(selector + " ")
    block = css[at:css.index("}", at)]

    assert "display" in block, f"{selector} must say whether it is shown"


def test_the_ipad_home_fixes_work_without_container_queries() -> None:
    """Safari before iPadOS 16 ignores @container. The first fix for the iPad's
    overlapping cards was built on it and changed nothing on an older iPad."""
    css = STYLES.read_text(encoding="utf-8")
    start = css.index("/* ── Cards narrower than their design ──")
    block = css[start:css.index("#homeAlarmBody .alarm-kinds { grid-template-columns: repeat(2, minmax(0, 1fr)); }", start)]
    rules = _without_comments_and_strings(block)
    assert "@container" not in rules and "cqh" not in rules and "cqw" not in rules
    for selector in ("#homeWeatherPanel .home-weather-body", "#homeAlarmBody .alarm-arm span", "#homeSensorsPanel .tc-hum"):
        assert selector in rules
    # The 13-inch iPad in landscape is three columns of ~354px cards: covered too.
    assert rules.count("(min-width: 1101px) and (max-width: 1400px) and (min-height: 821px)") >= 3


def test_container_units_have_a_fallback_for_older_safari() -> None:
    """A font-size in cqh alone is dropped by old Safari, leaving the base size."""
    css = _without_comments_and_strings(STYLES.read_text(encoding="utf-8"))
    for match in re.finditer(r"([^{};]*)\{([^{}]*)\}", css):
        body = match.group(2)
        for prop in ("font-size",):
            values = re.findall(rf"{prop}\s*:\s*([^;]+)", body)
            if any("cq" in v for v in values) and match.group(1).strip().startswith("#homeWeatherPanel"):
                assert any("cq" not in v for v in values), f"{match.group(1).strip()} needs a plain {prop} first"
