import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML = PROJECT_ROOT / "src" / "python" / "web_static" / "index.html"
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"
STYLES_CSS = PROJECT_ROOT / "src" / "python" / "web_static" / "styles.css"

DEVICE_GROUP_VIEWS = ["lights", "plugs", "ambient", "humidifier", "environment", "tuya", "climate"]


def _group_colors(css: str) -> dict[str, str]:
    """Map each device-group view to the --group-color variable it resolves to.

    Parses rules of the form:
        .room-item[data-view="lights"],
        .device-group-tile[data-goto-view="lights"] { --group-color: var(--amber); }
    """
    colors: dict[str, str] = {}
    for block in re.finditer(r"([^{}]+)\{([^{}]*--group-color\s*:\s*([^;}]+)[;}][^{}]*)\}", css):
        selector, _body, value = block.group(1), block.group(2), block.group(3).strip()
        for view in re.findall(r'data-view="([^"]+)"', selector):
            colors[view] = value
        for view in re.findall(r'data-goto-view="([^"]+)"', selector):
            colors[view] = value
    return colors


def test_new_palette_colors_are_defined_before_use() -> None:
    css = STYLES_CSS.read_text(encoding="utf-8")

    assert "--teal:" in css
    assert "--indigo:" in css
    # Must be declared in :root before any rule references them.
    root_end = css.index("}", css.index(":root"))
    root_block = css[:root_end]
    assert "--teal:" in root_block
    assert "--indigo:" in root_block


def test_every_device_group_resolves_a_group_color() -> None:
    colors = _group_colors(STYLES_CSS.read_text(encoding="utf-8"))

    missing = [v for v in DEVICE_GROUP_VIEWS if v not in colors]
    assert not missing, f"no --group-color for: {missing}"


def test_no_two_device_groups_share_a_colour() -> None:
    """The bug this guards: devices/plugs both used --accent and
    environment/tuya both used --cyan before this change."""
    colors = _group_colors(STYLES_CSS.read_text(encoding="utf-8"))
    used = {v: colors[v] for v in DEVICE_GROUP_VIEWS}

    duplicates = {c for c in used.values() if list(used.values()).count(c) > 1}
    assert not duplicates, f"colour reused across sibling groups: {duplicates} in {used}"


def test_sidebar_icon_reads_the_group_color_variable() -> None:
    """Sidebar and tile must consume one definition, or they drift apart."""
    css = STYLES_CSS.read_text(encoding="utf-8")

    assert re.search(r"\.room-icon\s*\{[^}]*color:\s*var\(--group-color", css)


def test_tile_markup_has_an_accent_strip_and_keeps_navigation() -> None:
    javascript = APP_JS.read_text(encoding="utf-8")

    assert "device-group-tile-accent" in javascript
    # Navigation still rides the existing document-level [data-goto-view] handler.
    assert 'data-goto-view="${escapeHtml(tile.view)}"' in javascript


def test_tile_accent_and_icon_read_the_group_colour() -> None:
    css = STYLES_CSS.read_text(encoding="utf-8")

    accent = re.search(r"\.device-group-tile-accent\s*\{([^}]*)\}", css)
    assert accent, "no .device-group-tile-accent rule"
    assert "var(--group-color" in accent.group(1)

    icon = re.search(r"\.device-group-tile-head\s+i\s*\{([^}]*)\}", css)
    assert icon, "no .device-group-tile-head i rule"
    assert "var(--group-color" in icon.group(1)


def test_tile_has_a_group_colour_fallback() -> None:
    """A group without an assignment must still render, not vanish."""
    css = STYLES_CSS.read_text(encoding="utf-8")

    tile = re.search(r"\.device-group-tile\s*\{([^}]*)\}", css)
    assert tile, "no .device-group-tile rule"
    assert "--group-color:" in tile.group(1), "tile needs a default --group-color"
