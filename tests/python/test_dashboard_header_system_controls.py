from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML = PROJECT_ROOT / "src" / "python" / "web_static" / "index.html"
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"


def test_weather_details_live_in_header_and_dashboard_weather_card_is_removed() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    header = html[html.index("<header>"):html.index("</header>")]

    assert 'id="headerWeather"' in header
    assert 'id="weatherTemp"' in header
    assert 'id="weatherCondition"' in header
    assert 'id="weatherFeels"' in header
    assert 'id="weatherHumidity"' in header
    assert 'id="weatherWind"' in header
    assert 'id="weatherPressure"' in header
    assert 'id="weatherUv"' in header
    assert 'id="weatherGrid"' not in html
    assert '<i class="ti ti-cloud"></i> Weather' not in html


def test_theme_view_under_system_owns_palette_picker() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    header = html[html.index("<header>"):html.index("</header>")]
    system = html[html.index('<div class="sidebar-section">System</div>'):]
    theme_panel = html[html.index('data-view-panel="theme"'):]

    assert 'data-view="theme"' in system
    assert 'data-view-panel="theme"' in html
    assert 'id="palettePicker"' not in header
    assert 'id="palettePicker"' in theme_panel


def test_homeos_title_is_editable_and_persistent() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    js = APP_JS.read_text(encoding="utf-8")

    assert 'id="logoText"' in html
    assert 'contenteditable="true"' in html
    assert 'const BRAND_TITLE_KEY = "dashboard_brand_title";' in js
    assert "saveBrandTitle" in js
