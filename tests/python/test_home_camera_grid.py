"""The Camera card's 2x2 grid on the wall panel: used only where it fits."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

APP_JS = Path(__file__).resolve().parents[2] / "src" / "python" / "web_static" / "app.js"
CSS = APP_JS.parent / "styles.css"


def _pick(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    depth, i = 0, source.index("{", start)
    for i in range(i, len(source)):
        depth += {"{": 1, "}": -1}.get(source[i], 0)
        if depth == 0:
            return source[start:i + 1]
    raise AssertionError(name)


def _child(height: int, *classes: str) -> str:
    """A fake element with the classList the function reads."""
    return ("{ offsetHeight: %d, classList: { contains: (c) => %s.includes(c) } }"
            % (height, json.dumps(list(classes))))


def _fits(tmp_path, body_h, content_h, extra_h, width, slots=()) -> bool:
    """`slots`: extra (height, showing) camera slots in the body - since
    2026-09-23 a hidden approach-camera slot does not count."""
    if not shutil.which("node"):
        pytest.skip("node is not installed")
    source = APP_JS.read_text(encoding="utf-8")
    children = [_child(content_h)] + [
        _child(h, "home-camera-slot", *(["showing"] if showing else [])) for h, showing in slots]
    script = f"""
const CAMERA_GRID_GAP = 8, CAMERA_EXTRA_MARGIN = 10;
const els = {{
  '#homeCameraBody': {{ clientHeight: {body_h}, children: [{", ".join(children)}] }},
  '#homeCameraExtra': {{ clientWidth: {width}, offsetHeight: {extra_h} }},
}};
const document = {{ querySelector: (q) => els[q] }};
{_pick(source, "cameraCardHasRoomForGrid")}
console.log(JSON.stringify(cameraCardHasRoomForGrid()));
"""
    path = tmp_path / "t.js"
    path.write_text(script, encoding="utf-8")
    return json.loads(subprocess.run(["node", str(path)], capture_output=True, text=True, check=True).stdout)


def test_the_wall_panels_tall_card_gets_the_grid(tmp_path):
    """Measured 2026-09-19 at 1920x1080: a 503px-wide picture of 283px plus its
    caption, and ~175px of gap above a strip of 3 small cameras and a line."""
    assert _fits(tmp_path, body_h=498, content_h=323, extra_h=138, width=503) is True


def test_a_card_just_tall_enough_for_the_picture_and_strip_keeps_the_strip(tmp_path):
    assert _fits(tmp_path, body_h=330, content_h=323, extra_h=138, width=503) is False


def test_switching_layouts_does_not_change_the_answer(tmp_path):
    """The grid is taller than the strip: the body shrinks by the difference, the
    extras grow by it, and the shared height the check uses is the same."""
    strip = _fits(tmp_path, body_h=498, content_h=323, extra_h=138, width=503)
    grid = _fits(tmp_path, body_h=498 - 162, content_h=323, extra_h=138 + 162, width=503)
    assert strip == grid


def test_the_grid_is_three_cameras_and_the_last_person_tile():
    js = APP_JS.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")
    extra = _pick(js, "renderHomeCameraExtra")

    assert "const roomy = homeCameraRoomy && allOthers.length >= 3;" in extra
    assert 'class="cam-strip roomy"' in extra and "cam-last-tile" in extra
    assert ".cam-strip.roomy { grid-template-columns: repeat(2, minmax(0, 1fr)); }" in css
    # Declared with the start-up state: it is read before its section runs.
    assert js.index("let homeCameraRoomy = false;") < js.index("function renderHomeCameraExtra")


def test_the_check_runs_again_after_the_camera_draws():
    """The card's size does not change when the picture first arrives, so a
    resize observer alone measured only the loading placeholder (2026-09-19)."""
    extra = _pick(APP_JS.read_text(encoding="utf-8"), "renderHomeCameraExtra")
    assert "requestAnimationFrame(updateCameraGridMode)" in extra


def test_a_hidden_approach_camera_slot_does_not_take_room(tmp_path):
    """14eb7c0 (2026-09-23): the approach camera plays in a slot that is hidden
    until someone approaches; only a showing slot counts toward the height."""
    assert _fits(tmp_path, body_h=498, content_h=323, extra_h=138, width=503,
                 slots=[(283, False)]) is True
    assert _fits(tmp_path, body_h=498, content_h=323, extra_h=138, width=503,
                 slots=[(283, True)]) is False
