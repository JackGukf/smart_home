from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML = PROJECT_ROOT / "src" / "python" / "web_static" / "index.html"
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"
WEB_APP = PROJECT_ROOT / "src" / "python" / "web_app.py"


def test_status_view_exists_in_sidebar() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'data-view="status"' in html
    assert '>Status<' in html
    assert 'data-view-panel="status"' in html


def test_stat_cards_are_inside_status_view_only() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")

    status_start = html.index('data-view-panel="status"')
    lights_start = html.index('data-view-panel="lights"')
    status_panel = html[status_start:lights_start]
    before_status = html[:status_start]

    assert '<div class="stat-row">' in status_panel
    assert before_status.count('<div class="stat-row">') == 0
    assert status_panel.count('class="stat-card"') == 4

def test_status_view_is_last_view_item() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    views_start = html.index('<div class="sidebar-section">Views</div>')
    # Discovery is now its own section between Views and System; scan only the Views <ul>
    discovery_start = html.index('<div class="sidebar-section">Discovery</div>')
    views_markup = html[views_start:discovery_start]
    view_order = []

    for item in views_markup.split('<li class="room-item"'):
        if 'data-view="' not in item:
            continue
        view_order.append(item.split('data-view="', 1)[1].split('"', 1)[0])

    assert view_order[-1] == "status"

def test_ambient_view_is_hidden_but_backend_is_preserved() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    javascript = APP_JS.read_text(encoding="utf-8")
    backend = WEB_APP.read_text(encoding="utf-8")

    assert 'data-view="ambient"' not in html
    assert 'data-view-panel="ambient"' not in html
    assert 'id="ambientGrid"' not in html
    assert 'requestJson("/api/ambient-lights")' not in javascript.split("async function loadDevices()", 1)[1].split("/* ── Send commands", 1)[0]
    assert '@app.get("/api/ambient-lights")' in backend
