from pathlib import Path
from re import fullmatch as re_fullmatch


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


def test_header_shows_hour_and_minute_only() -> None:
    """The date moved into the Weather card; the header keeps HH:MM."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    js = APP_JS.read_text(encoding="utf-8")
    header = html[html.index("<header>"):html.index("</header>")]
    weather = html[html.index('id="homeWeatherPanel"'):html.index('id="homeCameraPanel"')]

    assert 'id="clock"' in header
    assert 'id="dateDisplay"' not in header
    assert 'id="buildBadge"' not in header
    assert 'id="weatherClock"' in weather
    assert 'id="weatherDate"' in weather
    assert 'id="weatherWeek"' in weather
    assert "toTimeString().slice(0, 5)" in js


def test_news_and_about_live_under_settings() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    system = html[html.index('<div class="sidebar-section">System</div>'):]
    system = system[:system.index("</ul>")]

    for view in ("news", "about"):
        assert f'class="room-item system-settings-item" data-view="{view}" hidden' in system
        assert f'data-view-panel="{view}"' in html

    about = html[html.index('data-view-panel="about"'):]
    assert 'id="aboutVersion"' in about
    assert 'id="buildBadge"' in about


def test_news_lives_in_the_header_between_logo_and_clock() -> None:
    """One line in the header, not a card on Home: it costs the grid no height."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    header = html[html.index("<header>"):html.index("</header>")]
    home = html[html.index('data-view-panel="home"'):html.index('data-view-panel="cameras"')]

    assert header.index('class="logo"') < header.index('id="headerNews"') < header.index('id="clock"')
    assert 'id="headerNewsTitle"' in header
    assert 'id="headerNewsMarkets"' in header
    assert 'id="headerNews"' not in home


def test_youtube_player_lives_in_media() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    media = html[html.index('data-view-panel="media"'):html.index('data-view-panel="automations"')]

    for element in ("youtubeUrl", "youtubeFrame", "youtubeFullscreen", "youtubeExit", "youtubeOpen"):
        assert f'id="{element}"' in media


def test_deploy_records_the_release_version() -> None:
    deploy = (PROJECT_ROOT / "scripts" / "deploy-dashboard.sh").read_text(encoding="utf-8")
    version = (PROJECT_ROOT / "VERSION").read_text(encoding="utf-8").strip()

    assert '"version": "%s"' in deploy
    assert "/VERSION" in deploy
    assert re_fullmatch(r"\d+\.\d+\.\d+", version)
