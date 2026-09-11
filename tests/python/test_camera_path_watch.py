"""Following somebody up the drive: garage, then frontyard, then front door.

A camera path is an ordered route where every camera has a sensor watching it.
The dashboard opens all of them when the first one trips and shows whichever one
the person has reached. No re-identification model: the geometry already says it
is the same person walking, and guessing at it would mean a second graph on an
NPU where the last one cost days.

Three rules carry the whole thing, and each is a bug waiting to come back:

  * advancing is one-way. The presence hold keeps the garage sensor true for a
    minute after somebody has left it, so anything but "the furthest camera that
    has seen them" bounces the view back to a place they have already walked out
    of;
  * the slot markup does not change while an episode runs. Re-creating an
    <iframe> reloads it, so a card that swapped which cameras it held would tear
    down the stream it had just spent three seconds pre-warming;
  * a person beats the automation here too.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

HARNESS = """
const src = require('fs').readFileSync(process.argv[2], 'utf8');
const pick = (name) => {
  let at = src.indexOf(`async function ${name}`);
  if (at < 0) at = src.indexOf(`function ${name}`);
  if (at < 0) throw new Error(`missing function ${name}`);
  let depth = 0, i = src.indexOf('{', at);
  for (; i < src.length; i++) {
    if (src[i] === '{') depth++;
    else if (src[i] === '}') { depth--; if (depth === 0) return src.slice(at, i + 1); }
  }
  throw new Error(`unbalanced ${name}`);
};

const GARAGE = { id: 'cam-garage', name: 'Garage camera',
                 motion_entity: 'binary_sensor.garage_camera_npu_person' };
const YARD   = { id: 'cam-yard', name: 'Frontyard camera',
                 motion_entity: 'binary_sensor.frontyard_camera_npu_person' };
const DOOR   = { id: 'cam-door', name: 'Front door camera',
                 motion_entity: 'binary_sensor.front_door_presence' };
const ROUTE  = [GARAGE, YARD, DOOR];

const events = { renders: 0, slotApplies: 0, exits: 0, slots: [], log: [] };
globalThis.latestCameras = ROUTE;
globalThis.latestCameraPaths = [{
  name: 'Front approach',
  linger_seconds: 300,
  steps: ROUTE.map((c) => ({ camera_id: c.id, name: c.name, motion_entity: c.motion_entity })),
}];
globalThis.latestCameraById = new Map(ROUTE.map((c) => [c.id, c]));
globalThis.latestTuyaDevices = ROUTE.map((c) => ({ id: c.motion_entity, state: 'off', online: true }));
globalThis.activeCameraIds = new Set();
globalThis.homeCameraOverride = null;
globalThis.motionEpisodes = new Map();
globalThis.pathEpisodes = new Map();
globalThis.renderHomeCamera = () => { events.renders += 1; };
globalThis.exitPathMode = () => { events.exits += 1; };
// Records which cameras the card is asked to hold open, without a DOM.
globalThis.syncPathSlots = (cameras) => {
  events.slotApplies += 1;
  events.slots = cameras.map((c) => c.id);
};
globalThis.logActivity = (msg) => { events.log.push(msg); };

const store = new Map([['home_camera_motion_auto', '1']]);
globalThis.localStorage = {
  getItem: (k) => (store.has(k) ? store.get(k) : null),
  setItem: (k, v) => store.set(k, String(v)),
};

let timers = [];
let nextTimerId = 1;
globalThis.setTimeout = (fn, ms) => { const id = nextTimerId++; timers.push({ id, fn, ms }); return id; };
globalThis.clearTimeout = (id) => { timers = timers.filter((t) => t.id !== id); };
const pendingTimers = () => timers.map((t) => t.ms);
const fireTimers = () => { const due = timers; timers = []; due.forEach((t) => t.fn()); };

eval(src.match(/const HOME_CAMERA_AUTO_KEY = [^;]+;/)[0].replace('const ', 'globalThis.'));
eval(src.match(/const MOTION_ON_STATES = new Set\\([^)]*\\);/)[0].replace('const ', 'globalThis.'));

eval(pick('cameraIdFor') + pick('motionSensorIsTripped') + pick('motionWatchEnabled')
   + pick('cameraPathList') + pick('pathCameraIds') + pick('pathEpisodeCameras')
   + pick('activePathCameraId') + pick('openPathEpisode') + pick('advancePathEpisode')
   + pick('closePathEpisode') + pick('stopAllPathEpisodes') + pick('updatePathWatch')
   + pick('applyPathCameras'));

// `at` is how far along the route the person is; -1 is nobody. The sensors
// behind them stay true, which is what the presence hold really does.
const walkTo = (at, { hold = true } = {}) => {
  // The server puts the state on the step itself, so that is what is set here.
  latestCameraPaths[0].steps.forEach((step, i) => {
    step.state = (hold ? i <= at : i === at) ? 'on' : 'off';
  });
};
const clearAll = () => {
  latestCameraPaths[0].steps.forEach((step) => { step.state = 'off'; });
};

const report = (extra = {}) => console.log(JSON.stringify({
  showing: activePathCameraId(),
  playing: [...activeCameraIds].sort(),
  override: homeCameraOverride,
  episodes: pathEpisodes.size,
  pending: pendingTimers(),
  ...events,
  ...extra,
}));
"""


def _run(script: str, tmp_path: Path) -> dict:
    harness = tmp_path / "harness.js"
    harness.write_text(HARNESS + script, encoding="utf-8")
    out = subprocess.run(
        ["node", str(harness), str(APP_JS)], capture_output=True, text=True, check=True
    )
    return json.loads(out.stdout)


# ── Opening the route ────────────────────────────────────────────────────────

def test_the_first_camera_opens_it_and_the_next_one(tmp_path: Path) -> None:
    """The one on screen and the one they are walking towards, and no more.

    Pre-warming matters because a stream takes seconds to come up and by then
    they have moved on. Pre-warming the *whole* route does not: three 1080p
    streams put the Raspberry Pi 4 panel at 80% CPU and none of them finished
    connecting. Only the next one has to be ready."""
    result = _run("""
walkTo(0);
updatePathWatch();
report();
""", tmp_path)
    assert result["showing"] == "cam-garage"
    assert result["playing"] == ["cam-garage", "cam-yard"]
    assert "cam-door" not in result["playing"], "the far end of the route is not needed yet"
    assert result["episodes"] == 1


def test_arriving_mid_route_starts_where_they_are(tmp_path: Path) -> None:
    """The garage can miss somebody - a gap in cover, a low-confidence frame."""
    result = _run("""
walkTo(1, { hold: false });
updatePathWatch();
report();
""", tmp_path)
    assert result["showing"] == "cam-yard"


# ── Following them ───────────────────────────────────────────────────────────

def test_the_view_follows_them_along_the_route(tmp_path: Path) -> None:
    result = _run("""
walkTo(0); updatePathWatch();
const atGarage = activePathCameraId();
walkTo(1); updatePathWatch();
const atYard = activePathCameraId();
walkTo(2); updatePathWatch();
report({ atGarage, atYard });
""", tmp_path)
    assert result["atGarage"] == "cam-garage"
    assert result["atYard"] == "cam-yard"
    assert result["showing"] == "cam-door"


def test_following_them_never_rebuilds_the_card(tmp_path: Path) -> None:
    """Rebuilding re-creates the iframes, and a re-created iframe reloads - a
    black gap at exactly the moment somebody walks into view, and the
    pre-warming thrown away. Every step must be a node change instead."""
    result = _run("""
walkTo(0); updatePathWatch();
walkTo(1); updatePathWatch();
walkTo(2); updatePathWatch();
report();
""", tmp_path)
    assert result["renders"] == 0, "the card must never be re-rendered mid-episode"
    assert result["slotApplies"] == 3, "open, then one slot change per step"


def test_the_pre_warmed_camera_is_the_one_they_walk_into(tmp_path: Path) -> None:
    """The handoff is only instant if the next camera was already open - and it
    must still be open, not re-added, after the step."""
    result = _run("""
walkTo(0); updatePathWatch();
const warmedAtGarage = [...events.slots];
walkTo(1); updatePathWatch();
report({ warmedAtGarage });
""", tmp_path)
    assert result["warmedAtGarage"] == ["cam-garage", "cam-yard"]
    assert result["slots"] == ["cam-yard", "cam-door"], "showing the yard, warming the door"
    assert result["playing"] == ["cam-door", "cam-yard"]


def test_a_held_sensor_behind_them_never_drags_the_view_back(tmp_path: Path) -> None:
    """NPU_PRESENCE_HOLD keeps the garage true for a minute after they have
    left it. Taking the first true sensor would sit on an empty garage while
    somebody stands at the door."""
    result = _run("""
walkTo(2);            // at the door, garage and yard still held true
updatePathWatch();
report();
""", tmp_path)
    assert result["showing"] == "cam-door"


def test_it_does_not_walk_backwards_when_a_later_camera_clears(tmp_path: Path) -> None:
    result = _run("""
walkTo(2); updatePathWatch();
walkTo(1); updatePathWatch();     // the door sensor drops, the earlier ones hold
report();
""", tmp_path)
    assert result["showing"] == "cam-door", "the view must not retreat to the yard"


# ── Ending ───────────────────────────────────────────────────────────────────

def test_the_route_closes_after_the_linger(tmp_path: Path) -> None:
    result = _run("""
walkTo(0); updatePathWatch();
clearAll(); updatePathWatch();
const pendingBefore = pendingTimers();
fireTimers();
report({ pendingBefore });
""", tmp_path)
    assert result["pendingBefore"] == [300_000]
    assert result["playing"] == [], "every camera on the route must stop"
    assert result["override"] is None
    assert result["episodes"] == 0


def test_somebody_reappearing_cancels_the_close(tmp_path: Path) -> None:
    result = _run("""
walkTo(0); updatePathWatch();
clearAll(); updatePathWatch();
walkTo(1); updatePathWatch();
fireTimers();
report();
""", tmp_path)
    assert result["pending"] == []
    assert result["showing"] == "cam-yard"


def test_turning_the_switch_off_closes_the_route_at_once(tmp_path: Path) -> None:
    result = _run("""
walkTo(0); updatePathWatch();
stopAllPathEpisodes();
report();
""", tmp_path)
    assert result["playing"] == []
    assert result["episodes"] == 0


def test_a_screen_that_has_not_opted_in_is_left_alone(tmp_path: Path) -> None:
    result = _run("""
store.set('home_camera_motion_auto', '0');
walkTo(0);
updatePathWatch();
report();
""", tmp_path)
    assert result["episodes"] == 0
    assert result["playing"] == []


# ── The route reaches the browser ────────────────────────────────────────────

def test_the_api_resolves_names_to_cameras(tmp_path: Path) -> None:
    import yaml
    from fastapi.testclient import TestClient

    from src.python.web_app import create_app

    cfg = tmp_path / "devices.local.yaml"
    cfg.write_text(yaml.dump({
        "cameras": [
            {"name": "Garage camera", "host": "10.0.0.1", "provider": "wyze",
             "snapshot_url": "http://10.0.0.1/s.jpg",
             "motion_entity": "binary_sensor.garage_camera_npu_person"},
            {"name": "Front door camera", "host": "10.0.0.2", "provider": "wyze",
             "snapshot_url": "http://10.0.0.2/s.jpg",
             "motion_entity": "binary_sensor.front_door_presence"},
        ],
        "camera_paths": [
            {"name": "Front approach", "linger_seconds": 300,
             "cameras": ["Garage camera", "Front door camera"]},
        ],
    }), encoding="utf-8")

    paths = TestClient(create_app(config_path=cfg, check_camera_ports=False)) \
        .get("/api/cameras").json()["paths"]

    assert len(paths) == 1
    assert [step["camera_id"] for step in paths[0]["steps"]] == ["10.0.0.1", "10.0.0.2"]
    assert paths[0]["linger_seconds"] == 300


def test_a_step_naming_a_camera_that_does_not_exist_is_dropped(tmp_path: Path) -> None:
    """A typo should cost that step, not the whole route."""
    import yaml
    from fastapi.testclient import TestClient

    from src.python.web_app import create_app

    cfg = tmp_path / "devices.local.yaml"
    cfg.write_text(yaml.dump({
        "cameras": [
            {"name": "Garage camera", "host": "10.0.0.1", "provider": "wyze",
             "snapshot_url": "http://10.0.0.1/s.jpg",
             "motion_entity": "binary_sensor.a"},
            {"name": "Front door camera", "host": "10.0.0.2", "provider": "wyze",
             "snapshot_url": "http://10.0.0.2/s.jpg",
             "motion_entity": "binary_sensor.b"},
        ],
        "camera_paths": [
            {"name": "Front approach",
             "cameras": ["Garage camera", "Garge camera", "Front door camera"]},
        ],
    }), encoding="utf-8")

    paths = TestClient(create_app(config_path=cfg, check_camera_ports=False)) \
        .get("/api/cameras").json()["paths"]
    assert [step["name"] for step in paths[0]["steps"]] == ["Garage camera", "Front door camera"]


def test_a_camera_with_no_sensor_cannot_be_a_step(tmp_path: Path) -> None:
    """Nothing would ever announce somebody reaching it, so the route would
    stall there for ever."""
    import yaml
    from fastapi.testclient import TestClient

    from src.python.web_app import create_app

    cfg = tmp_path / "devices.local.yaml"
    cfg.write_text(yaml.dump({
        "cameras": [
            {"name": "Garage camera", "host": "10.0.0.1", "provider": "wyze",
             "snapshot_url": "http://10.0.0.1/s.jpg", "motion_entity": "binary_sensor.a"},
            {"name": "Blind camera", "host": "10.0.0.3", "provider": "wyze",
             "snapshot_url": "http://10.0.0.3/s.jpg"},
        ],
        "camera_paths": [
            {"name": "Front approach", "cameras": ["Garage camera", "Blind camera"]},
        ],
    }), encoding="utf-8")

    paths = TestClient(create_app(config_path=cfg, check_camera_ports=False)) \
        .get("/api/cameras").json()["paths"]
    # One usable step left, which is not a route.
    assert paths == []
