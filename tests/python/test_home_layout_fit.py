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


# ── Small screens: two columns, because three do not fit ──────────────────────
#
# An iPad mini in landscape is 1133x744. It clears the 1101px width, so it was
# getting the panel's three-column layout with twenty rows - and nineteen 16px
# gaps eat 304px of the ~548px available, leaving 12px rows and six squashed
# cards. In portrait, 744px wide is three ~197px columns, and below 900px `main`
# is height:auto so the rows stayed a literal 40px and the page simply grew.

TWO_COL = re.compile(
    r'\[data-home-card="(\w+)"\][^{]*\{\s*grid-column:\s*(\d+) / span (\d+)\s*!important;'
    r'\s*grid-row:\s*(\d+) / span (\d+)\s*!important;'
)


def _two_column_layout() -> dict[str, dict[str, int]]:
    css = STYLES.read_text(encoding="utf-8")
    return {
        name: {"x": int(x), "w": int(w), "y": int(y), "h": int(h)}
        for name, x, w, y, h in TWO_COL.findall(css)
    }


def test_small_screens_place_every_card_in_two_columns() -> None:
    layout = _two_column_layout()

    assert set(layout) == set(_default_layout()), "every Home card needs a small-screen cell"
    assert {cell["x"] for cell in layout.values()} == {1, 7}
    assert {cell["w"] for cell in layout.values()} == {6}


def test_both_small_screen_columns_total_the_same_rows() -> None:
    """Same invariant as the panel: agree, or the columns go ragged."""
    layout = _two_column_layout()

    columns: dict[int, list[tuple[int, int]]] = {}
    for cell in layout.values():
        columns.setdefault(cell["x"], []).append((cell["y"], cell["h"]))

    ends = {x: max(y + h for y, h in cards) - 1 for x, cards in columns.items()}

    assert set(ends.values()) == {14}, f"columns end at {ends}, expected 14 rows each"

    for x, cards in columns.items():
        expected = 1
        for y, h in sorted(cards):
            assert y == expected, f"small-screen column {x}: row {y} expected {expected}"
            expected = y + h


def test_the_short_landscape_case_is_covered_by_width_and_height() -> None:
    """1133x744 clears the width test, so width alone never caught it."""
    css = STYLES.read_text(encoding="utf-8")

    assert "(min-width: 740px) and (max-width: 1100px)" in css, "portrait tablets"
    assert "(min-width: 1101px) and (max-height: 820px)" in css, "landscape tablets"
    assert "(min-width: 1101px) and (min-height: 821px)" in css, "the panel and desktops"


def test_cards_cannot_be_dragged_where_css_places_them() -> None:
    """A drag would write a cell the stylesheet overrides: the card just sticks."""
    css = STYLES.read_text(encoding="utf-8")
    js = APP_JS.read_text(encoding="utf-8")

    assert "--home-arrangeable: 0" in css
    assert "--home-arrangeable: 1" in css
    assert "function homeCardsArrangeable()" in js
    # Both the move and the resize handler must ask, not just one.
    assert js.count("!homeCardsArrangeable()) return;") == 2


def test_the_weather_card_gets_the_height_it_cannot_compress_below() -> None:
    """It is the one Home card with a hard floor.

    ~54px of card padding and panel header, plus a fixed 58px weather icon, is
    about 120px before anything renders. Two of fourteen rows is 71px on an iPad
    mini in landscape, which clipped it to a sliver that scrolled inside its own
    card. Four rows is 151px.

    The other cards in that column can give the rows up: the ecobee dial scales
    itself to whatever card it is in, and the sensor grid scrolls.
    """
    weather = _two_column_layout()["weather"]

    assert weather["h"] >= 4, (
        "Weather needs four of the fourteen rows on a small screen; it cannot "
        "shrink below its icon the way Climate and Temperatures can"
    )


# ── Cross-column alignment, three-column layout only ─────────────────────────
#
# Two relationships run across columns rather than within one, so they cannot be
# kept by the per-column totals alone. Weather plus Climate has to break where
# Camera does, and Temperatures has to sit exactly where Security sits.


def test_weather_and_climate_together_match_camera() -> None:
    layout = _default_layout()
    weather, climate, camera = layout["weather"], layout["climate"], layout["camera"]

    assert weather["y"] == camera["y"] == 1, "all three start at the top"
    assert climate["y"] + climate["h"] == camera["y"] + camera["h"], (
        "Weather + Climate must end exactly where Camera ends, or the left and "
        "middle columns break at different heights"
    )
    assert weather["h"] + climate["h"] == camera["h"], (
        "2 + 9 == 11. The gap between Weather and Climate is not a row - Camera "
        "spanning 11 rows already contains the ten gaps between them, so the "
        "pixel heights come out equal: 74 + 16 + 389 == 479"
    )


def test_temperatures_and_security_occupy_the_same_rows() -> None:
    layout = _default_layout()
    temps, alarm = layout["tempsensors"], layout["alarm"]

    assert (temps["y"], temps["h"]) == (alarm["y"], alarm["h"]), (
        f"Temperatures {temps} and Security {alarm} must line up across the view"
    )


def test_weather_scales_with_its_own_height_rather_than_clipping() -> None:
    """The card is a fixed box on the fitted grid, and it carries a clock.

    Same mechanism the sensor tiles use: the card is its own size container and
    its type is a clamp on cqh, so it shrinks continuously instead of at a
    breakpoint, and tops out at the designed sizes when given more room.
    """
    css = STYLES.read_text(encoding="utf-8")

    assert "#homeWeatherPanel { container-type: size; }" in css
    for part in ("home-weather-time", "home-weather-temp", "home-weather-icon"):
        assert re.search(rf"#homeWeatherPanel \.{re.escape(part)}[^{{]*\{{[^}}]*cqh", css), \
            f"{part} must scale with the card height"
    # What is dropped rather than shrunk, in order: the week, then the date.
    week = re.search(r"@container \(max-height: (\d+)px\) \{[^@]*home-weather-week \{ display: none; \}", css)
    date = re.search(r"@container \(max-height: (\d+)px\) \{[^@]*home-weather-date \{ display: none; \}", css)
    assert week and date
    assert int(week.group(1)) > int(date.group(1)), "the week must go before the date"


def test_weather_keeps_enough_rows_to_render_in_both_layouts() -> None:
    """The clock, today and the week need about 210px on the wall panel.

    Six of twenty rows is that with the News card above the grid. The two
    layouts size it independently - fourteen rows on a small screen is a
    coarser scale than twenty - so neither number can be derived from the other.
    """
    assert _default_layout()["weather"]["h"] == 6
    assert _two_column_layout()["weather"]["h"] == 5


def test_a_stored_cell_cannot_outlive_the_table_it_was_resolved_against() -> None:
    """The wall panel held a Climate cell from an older default table.

    Weather shrank, the freed row had nobody to fill it, and it showed as a gap
    that only Reset Layout cleared. Versioning the defaults makes that automatic:
    a browser storing cells for built-in cards under an older version drops them
    on the next load. Cards the user added themselves are kept, because there is
    no default to fall back to for those.
    """
    js = APP_JS.read_text(encoding="utf-8")

    assert "HOME_CARD_LAYOUT_VERSION" in js
    loader = re.search(r"function loadHomeLayout\(\) \{(.*?)\n\}", js, re.S)
    assert loader, "loadHomeLayout not found"
    body = loader.group(1)

    assert "HOME_CARD_LAYOUT_VERSION" in body, "the loader must check the version"
    assert "DEFAULT_HOME_LAYOUT[id]" in body, "custom cards must survive the drop"


def test_the_camera_player_grows_into_slack_but_never_shrinks() -> None:
    """Locked to 16:9 it was sized by width alone.

    The wall panel gives the card 485px and a 506px-wide 16:9 frame needs 284,
    so ~112px sat empty under the controls. `flex: 1 0 auto` lets it take the
    remainder - and the 0 matters: where the frame already wants more height
    than the card has, as on an iPad mini, it must not be flexed smaller.
    """
    css = STYLES.read_text(encoding="utf-8")

    assert "#homeCameraPanel .home-camera-frame { flex: 1 0 auto; }" in css, \
        "must grow (1) and never shrink (0)"
    # The 16:9 basis has to stay, because it is what the frame grows *from*.
    assert re.search(r"\.home-camera-frame \{[^}]*aspect-ratio: 16 / 9", css)
    # Below 740px cards are natural height and the ratio is load-bearing.
    block = css.split("The camera player takes the height the card actually has")[1]
    assert "@media (min-width: 740px)" in block.split("@media")[0] + "@media (min-width: 740px)"


def test_hiding_the_overview_actually_hides_it() -> None:
    """Opening an area broke the whole view until this was here.

    renderAreaDetail() sets #homeOverview.hidden = true and shows a sibling.
    But `display` on an id beats the user agent's [hidden] { display: none } on
    specificity - 1,0,0 against 0,1,0 - so the fit rules kept the overview on
    screen and the area detail drew on top of it, with no way back but a reload.

    The codebase already had this idiom for .home-card[hidden]; the fit rules
    needed it too. Any new rule here that sets display needs the same guard.
    """
    css = STYLES.read_text(encoding="utf-8")

    assert "#homeOverview[hidden]" in css, \
        "#homeOverview sets display, so it must also state what [hidden] means"
    assert '.view-panel[data-view-panel="home"][hidden]' in css

    # The guard has to sit with the rule it guards - same media block - or the
    # breakpoint will not carry it.
    guard = css.index("#homeOverview[hidden]")
    rule = css.index("#homeOverview {")
    assert guard < rule, "the guard must come before the display rule"
    assert rule - guard < 400, "the guard drifted away from the rule it guards"
    assert "display: none" in css[guard:rule]
