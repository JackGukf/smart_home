import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML = PROJECT_ROOT / "src" / "python" / "web_static" / "index.html"
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"
STYLES_CSS = PROJECT_ROOT / "src" / "python" / "web_static" / "styles.css"

DEVICE_GROUP_VIEWS = ["lights", "plugs", "ambient", "humidifier", "environment", "tuya", "climate"]


def _find_all(haystack: str, needle: str) -> list[int]:
    """Every start offset of needle, so a test can pick by content not position."""
    offsets, at = [], haystack.find(needle)
    while at != -1:
        offsets.append(at)
        at = haystack.find(needle, at + 1)
    return offsets


def _balanced_block(source: str, start: int) -> str:
    """The statement beginning at start, ending at its matching close brace.

    A fixed-size window would spill into whatever follows, so an assertion could
    pass on a neighbouring block's contents even after the code under test was
    deleted. Brace-matching keeps each assertion inside its own block.
    """
    open_at = source.index("{", start)
    depth = 0
    for i in range(open_at, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[start:i + 1]
    raise AssertionError("unbalanced braces from offset %d" % start)


def _strip_css_comments(css: str) -> str:
    """Drop /* ... */ comments before parsing.

    A commented-out rule for a view placed after the real one would otherwise be
    parsed too and silently overwrite the real value (masking a genuine
    collision); placed before, it would fabricate a false one.
    """
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _group_colors(css: str) -> dict[str, str]:
    """Map each device-group view to the --group-color variable it resolves to.

    Parses rules of the form:
        .room-item[data-view="lights"],
        .device-group-tile[data-goto-view="lights"] { --group-color: var(--amber); }
    """
    css = _strip_css_comments(css)
    colors: dict[str, str] = {}
    for block in re.finditer(r"([^{}]+)\{([^{}]*--group-color\s*:\s*([^;}]+)[;}][^{}]*)\}", css):
        selector, _body, value = block.group(1), block.group(2), block.group(3).strip()
        for view in re.findall(r'data-view="([^"]+)"', selector):
            colors[view] = value
        for view in re.findall(r'data-goto-view="([^"]+)"', selector):
            colors[view] = value
    return colors


def _group_colors_by_context(css: str) -> dict[tuple[str, str], str]:
    """Like _group_colors, but keyed by (view, "sidebar"|"tile") separately.

    _group_colors keys by view name only, so if the sidebar declaration
    (.room-item[data-view=X]) and the tile declaration
    (.device-group-tile[data-goto-view=X]) are split into two rules with
    different colours, the later rule silently wins in that dict and nothing
    notices. Keeping the two contexts apart lets a test compare them directly.
    """
    css = _strip_css_comments(css)
    colors: dict[tuple[str, str], str] = {}
    for block in re.finditer(r"([^{}]+)\{([^{}]*--group-color\s*:\s*([^;}]+)[;}][^{}]*)\}", css):
        selector, _body, value = block.group(1), block.group(2), block.group(3).strip()
        for view in re.findall(r'data-view="([^"]+)"', selector):
            colors[(view, "sidebar")] = value
        for view in re.findall(r'data-goto-view="([^"]+)"', selector):
            colors[(view, "tile")] = value
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


def test_devices_parent_colour_differs_from_all_its_children() -> None:
    """DEVICE_GROUP_VIEWS covers only the seven children, so the parent row's
    colour went unchecked and stayed on --accent alongside Plugs two rows below.
    The parent is visible at the same time as every child, so it needs its own."""
    colors = _group_colors(STYLES_CSS.read_text(encoding="utf-8"))

    parent = colors.get("devices")
    assert parent is not None, "no --group-color for the devices parent"

    clashes = [v for v in DEVICE_GROUP_VIEWS if colors.get(v) == parent]
    assert not clashes, f"Devices parent shares {parent} with child view(s): {clashes}"


def test_sidebar_and_tile_group_colors_match_for_every_group() -> None:
    """The entire reason --group-color is a single shared declaration is to keep
    the sidebar item and the Devices overview tile from drifting apart. If
    someone splits a group's rule into two declarations (one per selector) with
    different colours, the plain view->colour map silently picks whichever rule
    parses last and nothing notices. Compare the two contexts directly."""
    colors = _group_colors_by_context(STYLES_CSS.read_text(encoding="utf-8"))

    mismatches = {}
    for view in DEVICE_GROUP_VIEWS:
        sidebar = colors.get((view, "sidebar"))
        tile = colors.get((view, "tile"))
        assert sidebar is not None, f"no sidebar --group-color for {view}"
        assert tile is not None, f"no tile --group-color for {view}"
        if sidebar != tile:
            mismatches[view] = (sidebar, tile)
    assert not mismatches, f"sidebar/tile colour drift: {mismatches}"


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


def test_all_seven_device_panels_have_a_hidden_back_button() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    panel_starts = _find_all(html, "data-view-panel=")

    for view in DEVICE_GROUP_VIEWS:
        start = html.index(f'data-view-panel="{view}"')
        # Bound the slice at the next panel's start (or EOF for the last panel)
        # instead of a fixed-size window, which the reviewer showed overruns
        # into the neighbouring panel for five of the seven groups.
        later_starts = [p for p in panel_starts if p > start]
        end = min(later_starts) if later_starts else len(html)
        panel = html[start:end]
        assert "data-back-to-devices" in panel, f"{view} panel has no back button"
        button = re.search(r"<button[^>]*data-back-to-devices[^>]*>", panel)
        assert button, f"{view} back button is not a <button>"
        assert "hidden" in button.group(0), (
            f"{view} back button must ship hidden so it cannot flash before JS runs"
        )


def test_activate_view_sets_back_button_visibility_for_both_branches() -> None:
    """Covers mutation (a): deleting setDevicesBackVisible(arrivedFromDevices)
    and the else branch from activateView must be caught here."""
    javascript = APP_JS.read_text(encoding="utf-8")

    fn_at = javascript.index("function activateView")
    body = _balanced_block(javascript, fn_at)
    assert "setDevicesBackVisible(arrivedFromDevices)" in body, (
        "activateView must arm the back button using the arrival flag for device-group views"
    )
    assert "setDevicesBackVisible(false)" in body, (
        "activateView must hide the back button for non-device-group views"
    )


def test_back_to_devices_click_handler_activates_devices_view() -> None:
    """Covers mutation (b): deleting the [data-back-to-devices] click handler
    must be caught here (the button would render but do nothing)."""
    javascript = APP_JS.read_text(encoding="utf-8")

    handler_starts = _find_all(javascript, 'document.addEventListener("click"')
    blocks = [_balanced_block(javascript, at) for at in handler_starts]
    matches = [b for b in blocks if "data-back-to-devices" in b]
    assert len(matches) == 1, (
        f"expected exactly one click handler referencing data-back-to-devices, found {len(matches)}"
    )
    assert 'activateView("devices")' in matches[0], (
        "the data-back-to-devices click handler must navigate back to the devices view"
    )


def test_set_devices_back_visible_actually_toggles_hidden() -> None:
    """Covers mutation (c): replacing the body of setDevicesBackVisible with a
    bare `return;` must be caught here (a no-op that still matches the loose
    string-presence checks)."""
    javascript = APP_JS.read_text(encoding="utf-8")

    fn_at = javascript.index("function setDevicesBackVisible")
    body = _balanced_block(javascript, fn_at)
    assert re.search(r"\.hidden\s*=", body), (
        "setDevicesBackVisible must actually assign to .hidden, not just return"
    )


def test_back_button_visibility_is_tracked_by_a_flag() -> None:
    javascript = APP_JS.read_text(encoding="utf-8")

    assert "arrivedFromDevices" in javascript
    assert "function setDevicesBackVisible" in javascript


def test_flag_is_only_set_for_clicks_inside_the_devices_panel() -> None:
    """data-goto-view is also used by the Home view's thermostat dial, camera
    frame and device rows, and by Area detail cards. Only the Devices overview
    may set the flag, or those other jumps would show a false back button."""
    javascript = APP_JS.read_text(encoding="utf-8")

    if_at = javascript.index("if (gotoCard)")
    handler = _balanced_block(javascript, if_at)
    assert 'data-view-panel="devices"' in handler, (
        "the goto handler must scope the flag to the Devices panel"
    )


def test_sidebar_click_clears_the_flag() -> None:
    """Sidebar clicks are handled by one delegated document listener, so nav
    items created at runtime work without registration and none can be bound
    twice. Identify it by the selector it matches rather than by file position,
    and scope the assertion to its own braces so it cannot pass on a
    neighbouring handler's contents."""
    javascript = APP_JS.read_text(encoding="utf-8")

    handlers = [
        _balanced_block(javascript, at)
        for at in _find_all(javascript, 'document.addEventListener("click"')
    ]
    sidebar = [h for h in handlers if '.room-item[data-view]' in h]
    assert len(sidebar) == 1, (
        f"expected exactly one delegated sidebar click handler, found {len(sidebar)}"
    )
    assert "arrivedFromDevices = false" in sidebar[0]
