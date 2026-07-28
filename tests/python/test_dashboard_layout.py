import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML = PROJECT_ROOT / "src" / "python" / "web_static" / "index.html"
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

def _sidebar_view_order(html: str) -> list[str]:
    """Views in the sidebar's Views section, in source order.

    Tolerates <li> items carrying extra classes (e.g. device-group-item);
    a literal '<li class="room-item"' match would silently skip them.
    """
    views_start = html.index('<div class="sidebar-section">Views</div>')
    # Discovery is its own section between Views and System; scan only the Views <ul>.
    discovery_start = html.index('<div class="sidebar-section">Discovery</div>')
    views_markup = html[views_start:discovery_start]
    return re.findall(r'<li[^>]*\bclass="[^"]*\broom-item\b[^"]*"[^>]*\bdata-view="([^"]+)"', views_markup)


def test_status_view_is_last_view_item() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert _sidebar_view_order(html)[-1] == "status"


def test_sidebar_view_order_helper_sees_multi_class_items() -> None:
    """Guards the helper itself: a second class must not hide an item."""
    markup = (
        '<div class="sidebar-section">Views</div>'
        '<li class="room-item" data-view="home">Home</li>'
        '<li class="room-item device-group-item" data-view="lights">Lights</li>'
        '<div class="sidebar-section">Discovery</div>'
    )

    assert _sidebar_view_order(markup) == ["home", "lights"]


def test_ambient_view_is_present_and_backend_is_preserved() -> None:
    """Ambient was hidden once, then restored in efeda71. Its sidebar item was
    later removed with the other device groups, but the panel and backend stay."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    backend = WEB_APP.read_text(encoding="utf-8")

    assert 'data-view-panel="ambient"' in html
    assert 'id="ambientGrid"' in html
    assert '@app.get("/api/ambient-lights")' in backend
