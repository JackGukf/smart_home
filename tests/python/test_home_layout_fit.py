"""The Home view has to fit the wall panel without scrolling.

The panel is 1920x1080 and the card grid gets 884px of it: 1080 less the 72px
header, less .content's 22/48 padding, less the section header above the grid.
The old layout asked for 1104px - twenty 40px rows plus nineteen 16px gaps - so
the left column ran 220px past the bottom of the screen while Areas stopped
228px short of it. Three columns, three different heights, one of them off-screen.

The fix is that the twenty rows divide the height that is actually there, which
only lines the columns up if every column totals the same number of rows. That
total is the invariant these tests hold: change one card's height and another in
the same column has to give the rows back.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"
STYLES = PROJECT_ROOT / "src" / "python" / "web_static" / "styles.css"

CARD = re.compile(r"(\w+):\s*\{\s*x:\s*(\d+),\s*y:\s*(\d+),\s*w:\s*(\d+),\s*h:\s*(\d+)\s*\}")


def _default_layout() -> dict[str, dict[str, int]]:
    js = APP_JS.read_text(encoding="utf-8")
    block = re.search(r"const DEFAULT_HOME_LAYOUT = \{(.*?)\};", js, re.S)
    assert block, "DEFAULT_HOME_LAYOUT not found"
    return {
        name: {"x": int(x), "y": int(y), "w": int(w), "h": int(h)}
        for name, x, y, w, h in CARD.findall(block.group(1))
    }


def _grid_rows() -> int:
    js = APP_JS.read_text(encoding="utf-8")
    match = re.search(r"const HOME_GRID_ROWS = (\d+);", js)
    assert match, "HOME_GRID_ROWS not found"
    return int(match.group(1))


def test_every_column_totals_the_same_number_of_rows() -> None:
    """This is what makes the three columns end flush instead of ragged."""
    layout = _default_layout()
    rows = _grid_rows()

    columns: dict[int, list[tuple[str, int, int]]] = {}
    for name, cell in layout.items():
        columns.setdefault(cell["x"], []).append((name, cell["y"], cell["h"]))

    ends = {x: max(y + h for _, y, h in cards) - 1 for x, cards in columns.items()}

    assert set(ends.values()) == {rows}, (
        f"columns end at different rows {ends}; every column must total {rows} "
        "or the Home view goes ragged again"
    )


def test_no_card_is_placed_below_the_last_row() -> None:
    """The grid has a fixed number of row tracks; past it is off-screen."""
    rows = _grid_rows()

    too_low = {
        name: cell for name, cell in _default_layout().items()
        if cell["y"] + cell["h"] - 1 > rows
    }

    assert not too_low, f"cards past row {rows}: {too_low}"


def test_cards_in_a_column_do_not_overlap_or_leave_gaps() -> None:
    layout = _default_layout()
    columns: dict[int, list[tuple[int, int]]] = {}
    for cell in layout.values():
        columns.setdefault(cell["x"], []).append((cell["y"], cell["h"]))

    for x, cards in columns.items():
        expected = 1
        for y, h in sorted(cards):
            assert y == expected, f"column {x}: card at row {y} expected row {expected}"
            expected = y + h


def test_the_grid_divides_the_real_height_rather_than_assuming_40px() -> None:
    """`grid-auto-rows: 40px` is what made fitting a matter of luck."""
    css = STYLES.read_text(encoding="utf-8")

    assert "grid-template-rows: repeat(20, minmax(0, 1fr))" in css
    # ...and the chain that gives it a height to divide.
    assert '.view-panel.active[data-view-panel="home"]' in css
    assert "#homeOverview > .home-layout" in css


def test_drag_and_resize_measure_the_row_instead_of_hardcoding_it() -> None:
    """A 40px assumption would move a card a third further than the pointer."""
    js = APP_JS.read_text(encoding="utf-8")
    pitch = re.search(r"function homeGridPitch\(grid\) \{(.*?)\n\}", js, re.S)
    assert pitch, "homeGridPitch not found"

    body = pitch.group(1)
    assert "grid.clientHeight" in body, "row height must come from the drawn grid"
    assert "HOME_GRID_ROWS" in body


def test_dragging_cannot_push_a_card_off_the_bottom() -> None:
    """Implicit rows past the last track are how a card leaves the screen."""
    js = APP_JS.read_text(encoding="utf-8")

    assert re.search(r"lay\.y = Math\.min\(Math\.max\(1, originY \+ dy\)", js), \
        "the drag handler must clamp y to HOME_GRID_ROWS"
    assert re.search(r"lay\.h = Math\.min\(", js), \
        "the resize handler must clamp h to HOME_GRID_ROWS"


def test_the_phone_still_stacks_and_scrolls() -> None:
    """One column at natural height below the breakpoint - unchanged."""
    css = STYLES.read_text(encoding="utf-8")

    assert ".home-layout { display: flex; flex-direction: column; }" in css
    # The fit rules must not reach below the stacking breakpoint.
    assert "@media (min-width: 1101px)" in css
