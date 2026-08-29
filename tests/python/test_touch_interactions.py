"""Drag, resize and camera controls have to work on a tablet, not just a mouse.

Three separate causes made the iPads feel broken:

- the Home grid stacked into a flex column below 1100px, and homeGridMode()
  reads that computed display, so card dragging and resizing were switched off
  on every tablet rather than merely awkward
- reordering used HTML5 drag-and-drop, which iOS Safari does not implement at
  all, so cards and camera tiles could not be moved by any gesture
- handles were revealed by :hover, which touch never fires, and were well
  under the ~44px a fingertip can reliably hit
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
    assert "pointercancel" in helper, "a cancelled touch must not leave a card stuck mid-drag"


def test_drag_handles_are_reachable_without_hover() -> None:
    css = STYLES.read_text(encoding="utf-8")

    block = re.search(r"@media \(hover: none\) \{.*?\n\}", css, re.S)
    assert block, "no touch-specific handle styling"
    body = block.group(0)
    # The resize corner is invisible until hover, which touch never fires.
    assert ".home-card-resize { opacity: 1; }" in body
    assert "44px" in body, "touch targets must reach ~44px"

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
