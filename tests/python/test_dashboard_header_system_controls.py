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


def test_theme_view_owns_palette_picker() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    header = html[html.index("<header>"):html.index("</header>")]
    theme_panel = html[html.index('data-view-panel="theme"'):]

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


def test_settings_is_one_view_of_app_tiles() -> None:
    """Settings opens on the right like every other view; each setting is a tile."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    js = APP_JS.read_text(encoding="utf-8")
    system = html[html.index('<div class="sidebar-section">System</div>'):]
    system = system[:system.index("</ul>")]
    settings = html[html.index('data-view-panel="settings"'):]
    settings = settings[:settings.index("</div>\n    </div>")]

    assert 'data-view="settings"' in system
    for page in ("theme", "startup", "news", "cast", "desktop", "nightlights", "about"):
        assert f'data-view="{page}"' not in system, f"{page} moved out of the sidebar"
        assert f'class="app-tile" data-goto-view="{page}"' in settings
        panel = html[html.index(f'data-view-panel="{page}"'):]
        panel = panel[:panel.index("</div>")]
        assert 'class="page-back" data-goto-view="settings"' in panel, f"{page} needs a way back"

    assert 'id="defaultViewSelect"' in html[html.index('data-view-panel="startup"'):]
    about = html[html.index('data-view-panel="about"'):]
    assert 'id="aboutVersion"' in about and 'id="buildBadge"' in about
    for page in ("theme", "startup", "news", "cast", "desktop", "nightlights", "about"):
        assert f'{page}: "settings"' in js, f"{page} keeps Settings lit in the sidebar"


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


def test_rotating_headlines_cannot_resize_the_header() -> None:
    """Each headline's length must not change how much room the logo gets.

    With an auto basis it did: the logo line wrapped on long headlines, the
    header grew past its fixed 72px and the page jumped every rotation.
    """
    css = (PROJECT_ROOT / "src" / "python" / "web_static" / "styles.css").read_text(encoding="utf-8")

    assert "header > .logo,\nheader > .header-right { flex-shrink: 0; }" in css
    assert ".logo-sub { white-space: nowrap; }" in css
    for rule in ("\n.header-news {", "\n.header-news-story {"):
        block = css[css.index(rule):css.index("}", css.index(rule))]
        assert "flex: 1 1 0;" in block, f"{rule} must not size itself from its text"
    title = css[css.index(".header-news-title {"):css.index("}", css.index(".header-news-title {"))]
    assert "white-space: nowrap;" in title and "text-overflow: ellipsis;" in title
