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
