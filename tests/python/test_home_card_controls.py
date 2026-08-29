"""Arranging, hiding and resetting the Home view's cards.

Cards could travel down the grid but never back up: a dropped card that
overlapped anything was pushed further down, so once two had drifted low,
every attempt to drag one up collided on the way and was pushed back.
"""

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"
INDEX_HTML = PROJECT_ROOT / "src" / "python" / "web_static" / "index.html"


def test_a_dropped_card_can_settle_upward() -> None:
    js = APP_JS.read_text(encoding="utf-8")
    fn = re.search(r"function nearestFreeRow\(.*?\n\}", js, re.S)
    assert fn, "nearestFreeRow is gone"
    body = fn.group(0)

    # Searching only downward is what stranded cards at the bottom.
    assert "lay.y - step" in body, "a dropped card must be able to settle upward"
    assert "lay.y + step" in body
    # Upward is checked first, so a card dragged up does not sink back down.
    assert body.index("lay.y - step") < body.index("lay.y + step")
    assert "y >= 1" in body, "row 1 is the top of the grid"


def test_drop_no_longer_pushes_cards_down_forever() -> None:
    js = APP_JS.read_text(encoding="utf-8")
    assert "while (others.some((o) => homeCellsOverlap(lay, o)) && guard++ < 200) lay.y += 1;" not in js


def test_reset_and_visibility_controls_exist() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    js = APP_JS.read_text(encoding="utf-8")

    assert 'id="homeResetLayout"' in html
    assert 'id="homeCardsButton"' in html
    assert 'id="homeCardsModal"' in html
    assert "function resetHomeLayout()" in js


def test_hiding_a_card_keeps_its_layout() -> None:
    js = APP_JS.read_text(encoding="utf-8")

    # Hiding must not clear the stored position, or showing a card again would
    # dump it at the bottom instead of putting it back.
    apply_fn = js[js.index("function applyHomeCardLayout()") :]
    apply_fn = apply_fn[: apply_fn.index("\n}\n")]
    assert "card.hidden = hidden.has(id)" in apply_fn
    assert "if (card.hidden) continue;" in apply_fn
    assert "removeItem(HOME_HIDDEN_CARDS_KEY)" not in apply_fn


def test_reset_clears_both_layout_and_hidden_cards() -> None:
    js = APP_JS.read_text(encoding="utf-8")
    fn = re.search(r"function resetHomeLayout\(.*?\n\}", js, re.S).group(0)

    assert "removeItem(HOME_CARD_LAYOUT_KEY)" in fn
    assert "removeItem(HOME_HIDDEN_CARDS_KEY)" in fn


def test_legacy_browsers_get_a_playable_camera_stream() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    js = APP_JS.read_text(encoding="utf-8")

    # The probe must not itself contain the modern syntax it tests for, or the
    # file it lives in would fail to parse on the browser it is probing.
    probe = re.search(r"try \{\s*new Function\((.*?)\);", html, re.S).group(1)
    assert "?." in probe and "??" in probe
    assert "legacy-js" in html

    # go2rtc's player is modern JS; on an old browser its iframe shows only
    # the "Live broadcast" heading, so serve MJPEG instead.
    assert "LEGACY_JS" in js
    assert "/mjpeg" in js[js.index("function cameraMedia") : js.index("function cameraMedia") + 2000]


def _rule_display(css: str, selector: str) -> str | None:
    """The display value a bare class rule sets, if any."""
    match = re.search(rf"^{re.escape(selector)}\s*\{{(.*?)\}}", css, re.S | re.M)
    if not match:
        return None
    display = re.search(r"display:\s*([a-z-]+)", match.group(1))
    return display.group(1) if display else None


def test_elements_hidden_by_attribute_beat_their_display_rule() -> None:
    """The `hidden` attribute only works if no rule out-specifies it.

    `[hidden] { display: none }` comes from the UA stylesheet, which any class
    rule setting a display beats. Setting element.hidden then does nothing at
    all - which is exactly what happened to the Home cards.
    """
    css = (PROJECT_ROOT / "src" / "python" / "web_static" / "styles.css").read_text(encoding="utf-8")
    js = APP_JS.read_text(encoding="utf-8")

    # Classes whose elements the code hides via the attribute rather than a class.
    hidden_by_attribute = [".home-card", ".room-item", ".device-back-btn"]

    for selector in hidden_by_attribute:
        display = _rule_display(css, selector)
        if display in (None, "none"):
            continue
        assert re.search(rf"{re.escape(selector)}\[hidden\]", css), (
            f"{selector} sets display:{display}, which beats [hidden]; "
            f"hiding it from JS will silently do nothing"
        )

    # And the Home cards really are hidden by the attribute.
    assert "card.hidden = hidden.has(id)" in js
