from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML = PROJECT_ROOT / "src" / "python" / "web_static" / "index.html"
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"


def test_weather_card_lives_in_home_view_with_forecast_dropdown() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    header = html[html.index("<header>"):html.index("</header>")]
    home = html[html.index('data-view-panel="home"'):html.index('data-view-panel="cameras"')]

    # Weather moved out of the header into a Home view card.
    assert 'id="headerWeather"' not in header
    assert 'id="weatherTemp"' not in header
    assert 'id="homeWeatherPanel"' in home
    assert 'id="weatherTemp"' in home
    assert 'id="weatherLocation"' in home
    assert "Outdoor Temperature" in home

    # Forecast dropdown still exists and opens from the card.
    assert 'id="headerWeather"' in home
    assert 'id="weatherDropdown"' in html
    assert 'id="weatherFeels"' in html
    assert 'id="weatherForecast"' in html


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
