"""The Home camera card on a screen that has never picked a camera.

That is every cast to the TV (Chromium starts with a fresh profile each time),
and it showed whichever camera happened to be first - the family room.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

APP_JS = Path(__file__).resolve().parents[2] / "src" / "python" / "web_static" / "app.js"
CAMERAS = [
    {"id": "192.168.0.24", "name": "Family room camera", "stream_name": "family_room_camera"},
    {"id": "192.168.0.88", "name": "Front door camera", "stream_name": "front_door_camera"},
    {"id": "192.168.0.191", "name": "Garage camera", "stream_name": "garage_camera"},
]


def _function(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    depth = 0
    for i in range(source.index("{", start), len(source)):
        depth += {"{": 1, "}": -1}.get(source[i], 0)
        if depth == 0:
            return source[start:i + 1]
    raise AssertionError(name)


def _shown(tmp_path: Path, cameras: list[dict], saved: str | None = None) -> str:
    if not shutil.which("node"):
        pytest.skip("node is not installed")
    source = APP_JS.read_text(encoding="utf-8")
    default = re.search(r'const HOME_CAMERA_DEFAULT_STREAM = "[^"]*";', source).group(0)
    script = f"""
const HOME_CAMERA_KEY = "home_camera_id";
{default}
let homeCameraOverride = null, shownHomeCameraId = null, shown = null;
const store = {json.dumps({"home_camera_id": saved} if saved else {})};
const localStorage = {{ getItem: (k) => store[k] ?? null }};
const body = {{ dataset: {{}} }}, select = {{}};
const document = {{ querySelector: (q) => q === "#homeCameraBody" ? body : q === "#homeCameraSelect" ? select : null }};
const homeCameraList = () => {json.dumps(cameras)};
const cameraIdFor = (c) => c.id || c.host || c.name;
const escapeHtml = (s) => String(s);
const renderHtml = (el, html) => {{ if (el === body) shown = html; }};
const homeCameraMarkup = (c) => c.name;
const pathEpisodeCameras = () => [];
const syncMotionWatchToggle = () => {{}}, renderHomeCameraExtra = () => {{}}, reportWallPanelCamera = () => {{}};
const exitPathMode = () => {{}}, syncPathSlots = () => {{}}, activePathCameraId = () => null;
{_function(source, "renderHomeCamera")}
renderHomeCamera();
console.log(shown);
"""
    path = tmp_path / "t.js"
    path.write_text(script, encoding="utf-8")
    return subprocess.run(["node", str(path)], capture_output=True, text=True, check=True).stdout.strip()


def test_a_screen_that_never_chose_shows_the_front_door(tmp_path):
    assert _shown(tmp_path, CAMERAS) == "Front door camera"


def test_a_screen_that_chose_keeps_its_choice(tmp_path):
    assert _shown(tmp_path, CAMERAS, saved="192.168.0.191") == "Garage camera"


def test_without_a_front_door_camera_the_first_is_shown(tmp_path):
    others = [c for c in CAMERAS if c["stream_name"] != "front_door_camera"]
    assert _shown(tmp_path, others) == "Family room camera"
