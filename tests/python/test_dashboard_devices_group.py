import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML = PROJECT_ROOT / "src" / "python" / "web_static" / "index.html"
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"
STYLES_CSS = PROJECT_ROOT / "src" / "python" / "web_static" / "styles.css"

DEVICE_CHILD_VIEWS = ["lights", "plugs", "ambient", "humidifier", "tuya", "climate"]


def test_devices_parent_exists_with_badge_and_chevron() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="devicesGroupToggle"' in html
    assert 'data-view="devices"' in html
    assert 'id="deviceGroupCount"' in html
    assert "settings-chevron" in html[html.index('id="devicesGroupToggle"'):][:400]


def test_device_children_are_marked_and_sit_under_devices() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    views_start = html.index('<div class="sidebar-section">Views</div>')
    discovery_start = html.index('<div class="sidebar-section">Discovery</div>')
    views = html[views_start:discovery_start]

    devices_at = views.index('data-view="devices"')
    ha_at = views.index('data-view="homeassistant"')

    for view in DEVICE_CHILD_VIEWS:
        at = views.index(f'data-view="{view}"')
        assert devices_at < at < ha_at, f"{view} must sit between Devices and Home Asst"

    children = re.findall(r'<li[^>]*\bdevice-group-item\b[^>]*\bdata-view="([^"]+)"', views)
    assert children == DEVICE_CHILD_VIEWS


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


def test_group_state_is_persisted() -> None:
    javascript = APP_JS.read_text(encoding="utf-8")

    assert "devices_group_open_v1" in javascript
    assert "setDevicesGroupOpen" in javascript


def test_mobile_rail_flattens_the_group() -> None:
    css = STYLES_CSS.read_text(encoding="utf-8")

    assert ".device-group-item" in css
    assert "#devicesGroupToggle { display: none; }" in css
    # The un-hide rule must come after .room-item[hidden] to win at equal specificity.
    assert css.index(".device-group-item[hidden]") > css.index(".room-item[hidden]")
