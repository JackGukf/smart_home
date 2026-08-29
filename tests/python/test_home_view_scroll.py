"""The Home view must not throw the reader back to the top as it refreshes.

The Home panels rebuild by assigning innerHTML, which empties the container
for an instant. The browser clamps the scroll offset to the briefly shorter
page, and below 900px `main` drops to height:auto - so on a tablet the
document itself is the scroller and every 60s refresh jumped to the top.
"""

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"
STYLES = PROJECT_ROOT / "src" / "python" / "web_static" / "styles.css"

# Functions the 60s refresh runs; each one used to rebuild markup in place.
REFRESHED_RENDERERS = (
    "renderHomeView",
    "renderHomeClimate",
    "renderHomeTempSensors",
    "renderHomeCamera",
    "renderCustomHomeCards",
)


def _function_body(js: str, name: str) -> str:
    match = re.search(rf"^function {name}\(.*?^\}}", js, flags=re.S | re.M)
    assert match, f"{name} not found"
    return match.group(0)


def test_refresh_renderers_do_not_assign_innerhtml_directly() -> None:
    js = APP_JS.read_text(encoding="utf-8")

    for name in REFRESHED_RENDERERS:
        body = _function_body(js, name)
        for line in body.splitlines():
            if ".innerHTML" not in line or "=" not in line:
                continue
            # Building a brand new element before it is in the document cannot
            # disturb anyone's scroll position; re-rendering a live one can.
            assert "createElement" in body and "el.innerHTML" in line, (
                f"{name} assigns innerHTML directly, which resets scroll: {line.strip()!r}"
            )


def test_render_helper_skips_identical_markup_and_restores_scroll() -> None:
    js = APP_JS.read_text(encoding="utf-8")
    helper = _function_body(js, "renderHtml")

    # Skipping unchanged markup is what removes the churn altogether.
    assert "lastRenderedHtml.get(element) === html" in helper
    assert "return false" in helper
    # And when the markup did change, put the offset back by hand.
    assert "scroller.scrollTop = documentTop" in helper
    assert "panel.scrollTop = panelTop" in helper


def test_both_scrollers_are_handled() -> None:
    css = STYLES.read_text(encoding="utf-8")
    js = APP_JS.read_text(encoding="utf-8")

    # Which element scrolls depends on the breakpoint, so the helper has to
    # cover both: the panel on desktop, the document on a narrow screen.
    assert "main { grid-template-columns: 68px 1fr; height: auto; }" in css
    assert "document.scrollingElement" in js
    assert 'element.closest(".content")' in js
