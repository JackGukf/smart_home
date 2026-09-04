"""The two Home layouts: a placed grid above 740px, a stack below it.

Below 740px .home-layout becomes a flex column and the stored grid-column /
grid-row values are inert, so the phone order is markup order in index.html -
which is a different thing from the grid's reading order, and easy to change
one of while forgetting the other.
"""

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"
INDEX_HTML = PROJECT_ROOT / "src" / "python" / "web_static" / "styles.css"
HTML = PROJECT_ROOT / "src" / "python" / "web_static" / "index.html"
STYLES = PROJECT_ROOT / "src" / "python" / "web_static" / "styles.css"

# Below 740px this list is the literal top-to-bottom order. Zigbee health used
# to sit above Music here; it now lives in the Bridges group under Devices,
# alongside the Tuya gateway, so the coordinator is read next to the other
# radios rather than as a lone tile on the landing view.
PHONE_ORDER = [
    "weather", "camera", "climate", "tempsensors", "areas", "bluetooth",
]

# Grid columns are 4 wide, so these are the three column starts.
LEFT, MIDDLE, RIGHT = 1, 5, 9


def _defaults() -> dict[str, dict[str, int]]:
    js = APP_JS.read_text(encoding="utf-8")
    body = re.search(r"const DEFAULT_HOME_LAYOUT = \{(.*?)\};", js, re.S).group(1)
    out = {}
    for name, cell in re.findall(r"(\w+):\s*\{([^}]*)\}", body):
        out[name] = {k: int(v) for k, v in re.findall(r"(\w+):\s*(\d+)", cell)}
    return out


def test_phone_order_is_markup_order() -> None:
    html = HTML.read_text(encoding="utf-8")
    assert re.findall(r'data-home-card="([^"]+)"', html) == PHONE_ORDER


def test_desktop_columns_hold_the_intended_cards() -> None:
    cells = _defaults()

    assert [n for n, c in cells.items() if c["x"] == LEFT] == ["weather", "climate", "bluetooth"]
    assert [n for n, c in cells.items() if c["x"] == MIDDLE] == ["camera", "tempsensors"]
    assert [n for n, c in cells.items() if c["x"] == RIGHT] == ["areas"]


def test_no_two_default_cards_overlap() -> None:
    """Overlap is allowed when a user arranges cards, but not out of the box."""
    cells = _defaults()
    for a, ca in cells.items():
        for b, cb in cells.items():
            if a >= b:
                continue
            apart = (
                ca["x"] + ca["w"] <= cb["x"] or cb["x"] + cb["w"] <= ca["x"]
                or ca["y"] + ca["h"] <= cb["y"] or cb["y"] + cb["h"] <= ca["y"]
            )
            assert apart, f"{a} and {b} overlap in the default layout"


def test_every_card_has_a_default_and_fits_the_grid() -> None:
    cells = _defaults()
    html = HTML.read_text(encoding="utf-8")

    assert set(cells) == set(re.findall(r'data-home-card="([^"]+)"', html))
    for name, cell in cells.items():
        assert cell["x"] >= 1 and cell["x"] + cell["w"] - 1 <= 12, f"{name} runs off the grid"
        assert cell["y"] >= 1


def test_home_header_buttons_wrap_to_two_lines_on_a_phone() -> None:
    css = STYLES.read_text(encoding="utf-8")

    block = re.search(
        r"@media \(max-width: 739px\) \{[^@]*?#homeOverview \.section-actions \{(.*?)\}", css, re.S
    )
    assert block, "no narrow-screen rule for the Home header controls"
    body = block.group(1)

    # Four buttons over two columns is two lines of two.
    assert "grid-template-columns: 1fr 1fr" in body
    # Grid gap, not flex gap: older Safari ignores the latter entirely.
    assert "display: grid" in body
