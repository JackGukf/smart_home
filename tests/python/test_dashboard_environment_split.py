import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML = PROJECT_ROOT / "src" / "python" / "web_static" / "index.html"
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"


def test_environment_is_a_device_group_child_before_sensors() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    views_start = html.index('<div class="sidebar-section">Views</div>')
    discovery_start = html.index('<div class="sidebar-section">Discovery</div>')
    views = html[views_start:discovery_start]

    children = re.findall(r'<li[^>]*\bdevice-group-item\b[^>]*\bdata-view="([^"]+)"', views)

    assert children == ["lights", "plugs", "ambient", "humidifier", "environment", "tuya", "climate"]


def test_environment_panel_and_badge_exist() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'data-view-panel="environment"' in html
    assert 'id="environmentGrid"' in html
    assert 'id="environmentCount"' in html


def test_split_filter_is_capability_driven() -> None:
    javascript = APP_JS.read_text(encoding="utf-8")

    assert "ENVIRONMENT_CAPABILITIES" in javascript
    assert "function filterReadingsForView(readings, mode)" in javascript
    assert "function groupHasViewContent(group, mode)" in javascript
    # The split must reuse the existing capability classifier, not re-derive it.
    assert "sensorCapabilityKey" in javascript


def test_card_renderer_takes_a_mode() -> None:
    javascript = APP_JS.read_text(encoding="utf-8")

    assert "function renderSensorDeviceCard(group, mode)" in javascript
    assert 'renderSensorDeviceCard(group, "sensors")' in javascript or \
           'renderSensorDeviceCard(g, "sensors")' in javascript


def test_environment_sensors_are_loaded_and_rendered() -> None:
    javascript = APP_JS.read_text(encoding="utf-8")

    assert "latestEnvironmentSensors" in javascript
    assert 'requestJson("/api/environment-sensors")' in javascript
    assert "function environmentSensorCard(sensor)" in javascript
    # Loaded on startup like ambient lights and humidifiers, not only on view switch.
    # Scope to the initDefaultView IIFE body rather than a fixed character window:
    # the function grew, and a byte-count assertion would fail on placement that is
    # actually correct.
    start = javascript.index("function initDefaultView")
    init = javascript[start:javascript.index("})();", start)]
    assert "loadEnvironmentSensors()" in init
    # Sits with its sibling loaders, so startup wiring stays in one place.
    assert "loadAmbientLights()" in init
    assert "loadHumidifiers()" in init
