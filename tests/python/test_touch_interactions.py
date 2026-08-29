"""Drag, resize and camera controls have to work on a tablet, not just a mouse.

Three separate causes made the iPads feel broken:

- the Home grid stacked into a flex column below 1100px, and homeGridMode()
  reads that computed display, so card dragging and resizing were switched off
  on every tablet rather than merely awkward
- reordering used HTML5 drag-and-drop, which iOS Safari does not implement at
  all, so cards and camera tiles could not be moved by any gesture
- handles were revealed by :hover, which touch never fires, and were well
  under the ~44px a fingertip can reliably hit
- and underneath all of it, every drag was bound to Pointer Events, which
  Safari did not ship until 13: on an iOS 12 iPad those handlers never fire
"""

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"
STYLES = PROJECT_ROOT / "src" / "python" / "web_static" / "styles.css"

# The narrowest iPad mini viewport; the grid must survive down to here.
NARROWEST_TABLET_PX = 744


def test_home_grid_stays_arrangeable_on_tablets() -> None:
    css = STYLES.read_text(encoding="utf-8")

    match = re.search(r"@media \(max-width: (\d+)px\) \{[^}]*?\.home-layout \{ display: flex", css, re.S)
    assert match, "the flex-stack fallback for .home-layout is gone"
    assert int(match.group(1)) < NARROWEST_TABLET_PX, (
        f"cards stack below {match.group(1)}px, which disables dragging on tablets"
    )


def test_reorderable_lists_do_not_rely_on_html5_drag_and_drop() -> None:
    js = APP_JS.read_text(encoding="utf-8")

    for selector in (".camera-card", ".area-card"):
        pattern = rf'class="{selector[1:]}[^"]*"[^>]*draggable="true"'
        assert not re.search(pattern, js), (
            f"{selector} still uses draggable=true, which iOS Safari ignores entirely"
        )

    assert "enablePointerReorder" in js
    assert js.count("enablePointerReorder({") >= 2, "cameras and areas both need pointer reordering"


def test_pointer_reorder_works_for_grids_and_single_columns() -> None:
    js = APP_JS.read_text(encoding="utf-8")
    helper = re.search(r"function enablePointerReorder\(.*?\n\}", js, re.S).group(0)

    # A captured pointer reports the handle as its target, so the element under
    # the finger has to be looked up rather than read off the event.
    assert "elementFromPoint" in helper
    # The axis has to be chosen per pair: the same lists are multi-column on a
    # tablet and single-column on a phone.
    assert "sameRow" in helper
    # Cancellation is handled by trackDrag, which every drag path shares.
    tracker = re.search(r"function trackDrag\(.*?\n\}", js, re.S).group(0)
    assert "pointercancel" in tracker and "touchcancel" in tracker, (
        "a cancelled touch must not leave a card stuck mid-drag"
    )


def test_drag_handles_are_reachable_without_hover() -> None:
    css = STYLES.read_text(encoding="utf-8")

    block = re.search(r"@media \(hover: none\) \{.*?\n\}", css, re.S)
    assert block, "no touch-specific handle styling"
    body = block.group(0)
    # The resize corner is invisible until hover, which touch never fires.
    assert re.search(r"\.home-card-resize \{[^}]*opacity: 1", body, re.S)
    assert "width: 40px" in body, "touch targets must be finger-sized"

    # Suppressing scroll is only acceptable on the handle itself.
    assert re.search(r"\.camera-drag-handle,\s*\.area-card-grip \{\s*touch-action: none;", css)


def test_home_camera_starts_and_stops_in_place() -> None:
    js = APP_JS.read_text(encoding="utf-8")

    # Tapping the card used to navigate away instead of showing the camera.
    assert "data-goto-view=\"cameras\"" not in js or "home-camera-frame" not in js.split("data-goto-view=\"cameras\"")[0][-200:]
    assert "data-home-camera-toggle" in js
    assert "data-home-camera-fullscreen" in js
    assert "expandHomeCamera" in js


def test_fullscreen_falls_back_when_the_api_is_refused() -> None:
    js = APP_JS.read_text(encoding="utf-8")
    fn = re.search(r"function expandHomeCamera\(.*?\n\}", js, re.S).group(0)

    assert "webkitRequestFullscreen" in fn, "iPadOS only offers the prefixed call"
    assert "home-camera-expanded" in fn, "needs a fallback where the API is refused"
    # The frame is replaced on refresh, so the state must live on the container.
    assert 'querySelector("#homeCameraBody")' in fn

    # An older iPad defines the method but reports fullscreenEnabled false, and
    # the call then does nothing and throws nothing. Testing for the method
    # alone returns early and leaves the screen untouched.
    assert "fullscreenEnabled" in fn, "must ask whether full screen is allowed, not just callable"
    assert "webkitFullscreenEnabled" in fn
    # requestFullscreen rejects asynchronously, which try/catch cannot see.
    assert "pending.catch" in fn, "an async refusal must fall back to the overlay"


def test_the_fullscreen_overlay_says_how_to_leave() -> None:
    css = STYLES.read_text(encoding="utf-8")

    # The overlay draws no browser chrome, so without a hint there is nothing
    # to suggest that tapping the picture exits.
    block = re.search(r"\.home-camera-expanded::after \{(.*?)\}", css, re.S)
    assert block, "no exit hint on the fullscreen fallback"
    assert "content:" in block.group(1)
    assert "pointer-events: none" in block.group(1), "the hint must not eat the tap that exits"


def test_drag_does_not_depend_on_pointer_events_alone() -> None:
    """Safari gained Pointer Events in 13; an iOS 12 iPad has none."""
    js = APP_JS.read_text(encoding="utf-8")

    assert "HAS_POINTER_EVENTS" in js
    assert "typeof window.PointerEvent" in js
    # Touch is the fallback that makes an iOS 12 iPad work at all.
    assert '"touchstart"' in js and '"touchmove"' in js
    # And mouse for any desktop browser in the same position.
    assert '"mousedown"' in js and '"mousemove"' in js


def test_drag_paths_go_through_the_input_abstraction() -> None:
    js = APP_JS.read_text(encoding="utf-8")

    # Card move, card resize and list reordering must all be reachable by touch.
    for anchor in ('.home-card-grip"', '.home-card-resize"'):
        block = js[js.index(anchor) - 400 : js.index(anchor)]
        assert "onDragStart(" in block, f"the drag starting at {anchor} is not routed through onDragStart"

    helper = re.search(r"function enablePointerReorder\(.*?\n\}", js, re.S).group(0)
    assert "onDragStart(container" in helper
    assert "trackDrag(event" in helper


def test_touch_moves_can_cancel_page_scrolling() -> None:
    js = APP_JS.read_text(encoding="utf-8")
    tracker = re.search(r"function trackDrag\(.*?\n\}", js, re.S).group(0)

    # Without a non-passive listener preventDefault is ignored, and the page
    # scrolls out from under the gesture instead of the card moving.
    assert "passive: false" in tracker
    assert "event.preventDefault()" in tracker


def test_touch_targets_are_grown_not_overflowed() -> None:
    css = STYLES.read_text(encoding="utf-8")

    # .home-card clips its overflow, so a target that reaches past the corner
    # is cut off - which is most of where a thumb lands on a corner handle.
    assert re.search(r"\.home-card \{[^}]*overflow: hidden", css, re.S)
    block = re.search(r"@media \(hover: none\) \{.*?\n\}", css, re.S).group(0)
    assert "width: 40px" in block and "height: 40px" in block

    # Press-and-hold must not raise the iOS callout instead of dragging.
    assert "-webkit-touch-callout: none" in css


def _card_move_handler(js: str) -> str:
    start = js.index('const grip = event.target.closest(".home-card-grip")')
    return js[start : js.index("trackDrag(event", start)]


def test_card_move_uses_deltas_not_a_captured_grid_rect() -> None:
    """A rect captured at drag start goes stale the moment the page scrolls.

    Moving a card can shorten the page; where the document is the scroller, as
    on a tablet, the browser then clamps the scroll offset. Every later move
    measured against the stale rect resolves to row 1, pinning the card to the
    top of the view - which is exactly what an iPad mini did.
    """
    js = APP_JS.read_text(encoding="utf-8")
    handler = _card_move_handler(js)

    assert "getBoundingClientRect" not in handler, (
        "card move measures against a captured rect, which goes stale on scroll"
    )
    # Same delta arithmetic the resize handle uses, which never had this bug.
    assert "point.clientX - startX" in handler
    assert "point.clientY - startY" in handler


def test_card_move_survives_a_zero_pitch() -> None:
    js = APP_JS.read_text(encoding="utf-8")
    handler = _card_move_handler(js)

    # Dividing by a zero pitch yields NaN, and a NaN grid row silently drops
    # the card back to automatic placement at the top.
    assert "if (!pitchX || !pitchY) return;" in handler


def test_synthetic_mouse_events_after_a_touch_are_ignored() -> None:
    js = APP_JS.read_text(encoding="utf-8")
    fn = re.search(r"function onDragStart\(.*?\n\}", js, re.S).group(0)

    # iOS replays a touch as mousedown/mouseup, which would start a second drag
    # over the one just finished and move the card on the next gesture.
    assert "lastTouchAt" in fn
    assert re.search(r"Date\.now\(\) - lastTouchAt < \d+", fn)


def test_fullscreen_overlay_sizes_the_frame_without_a_ratio() -> None:
    """A frame with no height makes its height:100% media zero too.

    Everywhere else the camera frame is sized by aspect-ratio, or by the
    percentage-padding stand-in used where that is unsupported. Neither is
    dependable for a flex item in an old WebKit, and the result is a black
    overlay with the picture present and one pixel tall.
    """
    css = STYLES.read_text(encoding="utf-8")

    block = re.search(
        r"\.home-camera-expanded \.home-camera-frame \{(.*?)\}", css, re.S
    )
    assert block, "the expanded frame has no rule of its own"
    body = block.group(1)

    height = re.search(r"height:\s*([0-9.]+)(vh|px)", body)
    assert height, "the expanded frame needs an explicit height, not an inherited ratio"

    # The stand-in would otherwise stack its own height on top of this one.
    assert re.search(
        r"\.home-camera-expanded \.home-camera-frame::before \{[^}]*display: none", css, re.S
    )

    # The media fills the frame, so a zero-height frame hides it entirely.
    media = re.search(r"\.home-camera-frame \.camera-media,.*?\{(.*?)\}", css, re.S).group(1)
    assert "height: 100%" in media


def test_expanded_camera_is_sized_in_pixels_from_javascript() -> None:
    """CSS sizing failed three ways on an older iPad; stop depending on it.

    aspect-ratio, then a percentage-padding stand-in, then a vh rule each left
    the frame at zero height, and the media inside is height:100%, so the
    picture collapsed while the black backdrop remained.
    """
    js = APP_JS.read_text(encoding="utf-8")
    fn = re.search(r"function sizeExpandedCamera\(.*?\n\}", js, re.S)
    assert fn, "no JS sizing for the expanded camera"
    body = fn.group(0)

    assert "frame.style.height" in body and "frame.style.width" in body
    # The media must not depend on the frame establishing a containing block.
    assert 'media.style.position = "static"' in body
    assert "media.style.height" in body

    # Sizing has to survive a re-render, which replaces the sized elements.
    render = js[js.index("function renderHomeCamera") :]
    render = render[: render.index("\n}\n")]
    assert "sizeExpandedCamera()" in render

    # And leaving full screen must not strand inline styles on the card.
    collapse = re.search(r"function collapseExpandedCamera\(.*?\n\}", js, re.S).group(0)
    assert 'removeAttribute("style")' in collapse
