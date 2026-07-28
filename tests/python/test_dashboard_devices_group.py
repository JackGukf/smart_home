import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML = PROJECT_ROOT / "src" / "python" / "web_static" / "index.html"
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"
STYLES_CSS = PROJECT_ROOT / "src" / "python" / "web_static" / "styles.css"

DEVICE_CHILD_VIEWS = ["lights", "plugs", "ambient", "humidifier", "environment", "tuya", "climate"]


def test_devices_parent_exists_with_badge_and_no_chevron() -> None:
    """Devices is now a plain nav item: the groups live behind its overview
    tiles, so there are no children to collapse and no chevron."""
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="devicesGroupToggle"' in html
    assert 'data-view="devices"' in html
    assert 'id="deviceGroupCount"' in html
    entry = html[html.index('id="devicesGroupToggle"'):]
    assert "settings-chevron" not in entry[:entry.index("</li>")]


def test_no_device_group_children_in_the_sidebar() -> None:
    """The seven groups were removed from the sidebar; they are reached through
    the Devices overview tiles instead. Their panels must still exist."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    views_start = html.index('<div class="sidebar-section">Views</div>')
    discovery_start = html.index('<div class="sidebar-section">Discovery</div>')
    views = html[views_start:discovery_start]

    assert "device-group-item" not in views
    for view in DEVICE_CHILD_VIEWS:
        assert f'data-view="{view}"' not in views, f"{view} should no longer be a nav item"
        assert f'data-view-panel="{view}"' in html, f"{view}'s panel must still exist"


def test_sidebar_is_exactly_the_top_level_views() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    views_start = html.index('<div class="sidebar-section">Views</div>')
    discovery_start = html.index('<div class="sidebar-section">Discovery</div>')
    views = html[views_start:discovery_start]

    found = re.findall(r'<li[^>]*\bdata-view="([^"]+)"', views)
    assert found == ["home", "cameras", "devices", "homeassistant", "alarm", "status"]


def test_top_level_views_are_untouched() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    views_start = html.index('<div class="sidebar-section">Views</div>')
    discovery_start = html.index('<div class="sidebar-section">Discovery</div>')
    views = html[views_start:discovery_start]

    for view in ["home", "cameras", "homeassistant", "alarm", "status"]:
        item = re.search(rf'<li[^>]*\bdata-view="{view}"', views)
        assert item is not None
        assert "device-group-item" not in item.group(0)


def test_devices_overview_panel_has_a_tile_per_child() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'data-view-panel="devices"' in html
    assert 'id="devicesOverviewGrid"' in html


def test_overview_tiles_reuse_the_existing_goto_view_handler() -> None:
    javascript = APP_JS.read_text(encoding="utf-8")

    assert "renderDevicesOverview" in javascript
    # Tiles must navigate via the existing document-level handler, not a new one.
    assert "data-goto-view" in javascript
    for view in DEVICE_CHILD_VIEWS:
        assert f'"{view}"' in javascript


def test_collapse_machinery_is_gone() -> None:
    """With no children in the sidebar there is nothing to collapse, so the
    persisted open/closed state and its helpers were removed rather than left
    as controls that do nothing."""
    javascript = APP_JS.read_text(encoding="utf-8")

    assert "devices_group_open_v1" not in javascript
    assert "setDevicesGroupOpen" not in javascript
    assert "isDevicesGroupOpen" not in javascript


def test_mobile_rail_shows_the_devices_icon() -> None:
    """The rail used to hide Devices and show its seven children flat. With the
    children gone that would have left no device navigation at all on a phone,
    so Devices itself must now appear on the rail."""
    css = STYLES_CSS.read_text(encoding="utf-8")

    assert "#devicesGroupToggle { display: none; }" not in css
    assert ".device-group-item" not in css
