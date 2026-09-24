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
                 motion_entity: 'binary_sensor.front_door_presence',
                 person_entity: 'binary_sensor.front_door_camera_npu_person' };
const ROUTE  = [GARAGE, YARD, DOOR];

const events = { renders: 0, slotApplies: 0, exits: 0, slots: [], log: [] };
globalThis.latestCameras = ROUTE;
globalThis.latestCameraPaths = [{
  name: 'Front approach',
  linger_seconds: 300,
  abandon_seconds: 300,
  prewarm_next: false,
  priority_camera_id: DOOR.id,
  steps: ROUTE.map((c) => ({ camera_id: c.id, name: c.name, motion_entity: c.motion_entity, person_entity: c.person_entity })),
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

eval(pick('cameraIdFor') + pick('motionSensorIsTripped') + pick('cameraTriggerIsTripped') + pick('motionWatchEnabled')
   + pick('cameraPathList') + pick('pathCameraIds') + pick('pathEpisodeCameras')
   + pick('activePathCameraId') + pick('openPathEpisode') + pick('advancePathEpisode')
   + pick('closePathEpisode') + pick('stopAllPathEpisodes') + pick('updatePathWatch')
   + pick('applyPathCameras') + pick('releaseMotionEpisodes'));

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
const setDirection = (i, dir) => { latestCameraPaths[0].steps[i].direction = dir; };

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

def test_the_first_camera_opens_alone_by_default(tmp_path: Path) -> None:
    """Only the camera the person is at plays. A second stream decoding for a
    person who may never leave the garage is the thing prewarm_next exists to
    opt into, and it is off by default."""
    result = _run("""
walkTo(0);
updatePathWatch();
report();
""", tmp_path)
    assert result["showing"] == "cam-garage"
    assert result["playing"] == ["cam-garage"]
    assert "cam-door" not in result["playing"], "the far end of the route is not needed yet"
    assert result["episodes"] == 1


def test_prewarm_next_holds_the_next_camera_open_too(tmp_path: Path) -> None:
    """prewarm_next: true is the old behaviour, kept for routes that want the
    instant handoff: the one on screen and the one they are walking towards,
    and no more. Pre-warming the *whole* route does not: three 1080p streams
    put the Raspberry Pi 4 panel at 80% CPU and none of them finished
    connecting."""
    result = _run("""
latestCameraPaths[0].prewarm_next = true;
walkTo(0);
updatePathWatch();
report();
""", tmp_path)
    assert result["showing"] == "cam-garage"
    assert result["playing"] == ["cam-garage", "cam-yard"]
    assert "cam-door" not in result["playing"]


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
latestCameraPaths[0].prewarm_next = true;
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


def test_abandon_closes_early_when_nobody_advanced(tmp_path: Path) -> None:
    """Somebody stayed at the garage, or left. They never came to the house,
    so there is nothing to wait the full linger for."""
    result = _run("""
latestCameraPaths[0].abandon_seconds = 60;
walkTo(0); updatePathWatch();
clearAll(); updatePathWatch();
report();
""", tmp_path)
    assert result["pending"] == [60_000]


def test_abandon_does_not_apply_once_the_card_has_followed_them(tmp_path: Path) -> None:
    result = _run("""
latestCameraPaths[0].abandon_seconds = 60;
walkTo(0); updatePathWatch();
walkTo(1); updatePathWatch();
clearAll(); updatePathWatch();
report();
""", tmp_path)
    assert result["pending"] == [300_000], "a followed person gets the full linger"


def test_somebody_walking_away_never_opens_the_route(tmp_path: Path) -> None:
    """An outward direction on the only tripped camera is a departure, not an
    arrival: do not open anything for it."""
    result = _run("""
setDirection(0, 'outward');
walkTo(0); updatePathWatch();
report();
""", tmp_path)
    assert result["episodes"] == 0
    assert result["playing"] == []


def test_advance_skips_a_camera_the_person_is_walking_away_from(tmp_path: Path) -> None:
    """The frontyard sensor trips, but the person there is walking away from
    the house - stay on the garage until they turn around."""
    result = _run("""
walkTo(0); updatePathWatch();
setDirection(1, 'outward');
walkTo(1); updatePathWatch();
const atGarage = activePathCameraId();
setDirection(1, undefined);
walkTo(1); updatePathWatch();
report({ atGarage });
""", tmp_path)
    assert result["atGarage"] == "cam-garage"
    assert result["showing"] == "cam-yard"


def test_the_view_closes_at_once_when_the_shown_camera_says_outward(tmp_path: Path) -> None:
    """Close the view immediately, but retain a marker until held motion clears."""
    result = _run("""
walkTo(0); updatePathWatch();
setDirection(0, 'outward'); updatePathWatch();
report({ released: pathEpisodes.get('Front approach')?.released });
""", tmp_path)
    assert result["episodes"] == 1
    assert result["released"] is True
    assert result["playing"] == []
    assert result["override"] is None


def test_outward_then_unknown_cannot_reopen_a_held_route(tmp_path: Path) -> None:
    """The detector's next empty frame changes direction to unknown while its
    occupancy hold stays on. A new visit may open only after motion clears."""
    result = _run("""
walkTo(0); updatePathWatch();
setDirection(0, 'outward'); updatePathWatch();
setDirection(0, 'unknown'); updatePathWatch();
const duringHold = { episodes: pathEpisodes.size, playing: [...activeCameraIds] };
clearAll(); updatePathWatch();
const afterClear = pathEpisodes.size;
walkTo(0); updatePathWatch();
report({ duringHold, afterClear });
""", tmp_path)
    assert result["duringHold"] == {"episodes": 1, "playing": []}
    assert result["afterClear"] == 0
    assert result["showing"] == "cam-garage"
    assert result["playing"] == ["cam-garage"]


def test_a_step_without_a_direction_is_trusted_as_before(tmp_path: Path) -> None:
    """The front door's PIR has no direction entity, so its trip must still
    open and advance the route."""
    result = _run("""
walkTo(2); updatePathWatch();
report();
""", tmp_path)
    assert result["showing"] == "cam-door"


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
             "motion_entity": "binary_sensor.garage_camera_npu_person",
             "direction_entity": "sensor.garage_camera_npu_person_direction"},
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
    assert paths[0]["abandon_seconds"] == 300, "abandon defaults to the linger"
    assert paths[0]["prewarm_next"] is False, "pre-warming is opt-in, not the default"
    assert paths[0]["steps"][0]["direction_entity"] == "sensor.garage_camera_npu_person_direction"
    assert paths[0]["steps"][1].get("direction_entity") is None, "no direction configured"


def test_the_api_reads_the_path_knobs(tmp_path: Path) -> None:
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
            {"name": "Front approach", "linger_seconds": 300,
             "abandon_seconds": 60, "prewarm_next": True,
             "cameras": ["Garage camera", "Front door camera"]},
        ],
    }), encoding="utf-8")

    paths = TestClient(create_app(config_path=cfg, check_camera_ports=False)) \
        .get("/api/cameras").json()["paths"]

    assert paths[0]["abandon_seconds"] == 60
    assert paths[0]["prewarm_next"] is True


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


# ── A person picks another camera mid-route ─────────────────────────────────

def test_picking_a_camera_hands_the_card_back_at_once(tmp_path: Path) -> None:
    """A garage detector that kept re-triggering held the route open for
    minutes, and a pick from the dropdown waited all that time: the released
    episode still owned the card, still set the dropdown back to the route, and
    the panel kept decoding both of the route's streams."""
    result = _run("""
walkTo(0);
updatePathWatch();
const before = [...activeCameraIds].sort();
releaseMotionEpisodes();
report({ before, route: pathEpisodeCameras().map((c) => c.id) });
""", tmp_path)

    assert result["before"] == ["cam-garage"], "only the camera they are at plays"
    assert result["route"] == [], "a released episode must not own the card"
    assert result["showing"] is None
    assert result["playing"] == [], "the route's streams stop with it"
    assert result["exits"] == 1, "the card leaves path mode"
    assert result["override"] is None


def test_a_released_route_does_not_come_back_while_the_same_motion_lasts(tmp_path: Path) -> None:
    result = _run("""
walkTo(0);
updatePathWatch();
releaseMotionEpisodes();
walkTo(1);          // still the same visit
updatePathWatch();
report({ route: pathEpisodeCameras().map((c) => c.id) });
""", tmp_path)

    assert result["route"] == []
    assert result["playing"] == []
    assert result["episodes"] == 1, "tracked, so the same motion cannot reopen it"


# ── Under the picture: the other cameras, and who was seen last ──────────────

def test_the_strip_and_the_last_person_line_read_the_detector_zones(tmp_path: Path) -> None:
    """The Security zones already carry the NPU person sensors and their age, so
    the strip costs no extra fetch. The mapping is the camera's name in lower
    case with underscores - binary_sensor.front_door_camera_npu_person."""
    js = APP_JS.read_text(encoding="utf-8")
    body = js[js.index("function cameraSightings()"):js.index("function agoLabel(")]

    assert "latestAlarmData?.zones" in body
    assert "_npu_person$" in body
    assert 'zone.state === "motion" ? 0' in body, "a camera seeing someone now is 0 minutes ago"
    assert "sort((a, b) => a.minutes - b.minutes)" in body

    key = js[js.index("function cameraDetectorKey(camera)"):js.index("/* cameraId -> minutes")]
    assert 'replace(/\\s+/g, "_")' in key


def test_picking_a_camera_from_the_strip_behaves_like_the_dropdown(tmp_path: Path) -> None:
    """Same three rules: the person beats the automation, the card holds one
    stream, and a live view stays live across the switch."""
    js = APP_JS.read_text(encoding="utf-8")
    handler = js[js.index('const pick = event.target.closest("[data-home-camera-pick]");'):]
    handler = handler[:handler.index("/* The picture and its controls.")]

    assert "releaseMotionEpisodes();" in handler
    assert "activeCameraIds.delete(previous)" in handler
    assert "if (wasLive) activeCameraIds.add(id);" in handler
    assert "localStorage.setItem(HOME_CAMERA_KEY, id)" in handler


def test_the_strip_lives_outside_the_body_an_episode_rebuilds(tmp_path: Path) -> None:
    """syncPathSlots owns #homeCameraBody node by node; a strip inside it would
    be torn down and rebuilt - and its thumbnails would blink - on every step."""
    html = (PROJECT_ROOT / "src" / "python" / "web_static" / "index.html").read_text(encoding="utf-8")
    js = APP_JS.read_text(encoding="utf-8")

    card = html[html.index('id="homeCameraCard"') if 'id="homeCameraCard"' in html else html.index('id="homeCameraPanel"'):]
    card = card[:card.index("</div>\n          <div class=\"panel")] if "</div>\n          <div class=\"panel" in card else card[:2000]
    assert 'id="homeCameraExtra"' in card
    assert card.index('id="homeCameraBody"') < card.index('id="homeCameraExtra"')
    # Refreshed in place, so a thumbnail never blinks back to a placeholder.
    assert "function refreshCameraThumbs()" in js
    assert "img.src = camera.snapshot_url" in js


def test_the_strip_shows_outdoor_cameras_only(tmp_path: Path) -> None:
    """A thumbnail of the living room adds nothing to a glance at the doors, and
    puts the room on a panel anyone walking past can see."""
    js = APP_JS.read_text(encoding="utf-8")
    render = js[js.index("function renderHomeCameraExtra()"):js.index("/* Fresh thumbnails")]
    sightings = js[js.index("function cameraSightings()"):js.index("function agoLabel(")]

    assert "homeCameraList().filter(isOutdoorCamera)" in render
    assert ".filter(isOutdoorCamera)" in sightings, "the last-person line is outdoor too"
    assert "camera?.outdoor === true" in js, "the server decides; the browser reads the flag"


def test_the_strip_follows_the_approach_route_and_ends_off_it(tmp_path: Path) -> None:
    """Garage, frontyard, front door is the order somebody walking up passes
    them; the back yard is not on the route, so it sits at the end."""
    result = _run("""
globalThis.homeCameraList = () => [
  { id: 'cam-back', name: 'Backyard camera', outdoor: true },
  { id: 'cam-door', name: 'Front door camera', outdoor: true },
  { id: 'cam-garage', name: 'Garage camera', outdoor: true },
  { id: 'cam-yard', name: 'Frontyard camera', outdoor: true },
];
latestCameraPaths[0].steps = [
  { camera_id: 'cam-garage' }, { camera_id: 'cam-yard' }, { camera_id: 'cam-door' },
];
eval(pick('outdoorCameraOrder') + pick('isOutdoorCamera'));
report({ order: outdoorCameraOrder(homeCameraList().filter(isOutdoorCamera)).map((c) => c.id) });
""", tmp_path)

    assert result["order"] == ["cam-garage", "cam-yard", "cam-door", "cam-back"]

def test_front_door_route_opens_from_either_sensor(tmp_path: Path) -> None:
    result = _run("""
clearAll();
latestCameraPaths[0].steps[2].person_state = 'on';
updatePathWatch();
report();
""", tmp_path)
    assert result["showing"] == "cam-door"

    result = _run("""
walkTo(2, { hold: false });
latestCameraPaths[0].steps[2].person_state = 'off';
updatePathWatch();
report();
""", tmp_path)
    assert result["showing"] == "cam-door"

def test_door_person_has_priority_over_outward_frontyard(tmp_path: Path) -> None:
    result = _run("""
walkTo(1, { hold: false }); updatePathWatch();
setDirection(1, 'outward');
clearAll();
latestCameraPaths[0].steps[2].person_state = 'on';
updatePathWatch();
report();
""", tmp_path)
    assert result["showing"] == "cam-door"
    assert result["playing"] == ["cam-door"]


def test_door_person_reopens_an_outward_closed_route(tmp_path: Path) -> None:
    result = _run("""
walkTo(1, { hold: false }); updatePathWatch();
setDirection(1, 'outward'); updatePathWatch();
clearAll();
latestCameraPaths[0].steps[2].person_state = 'on';
updatePathWatch();
report();
""", tmp_path)
    assert result["showing"] == "cam-door"
    assert result["episodes"] == 1


def test_warmed_frontyard_stays_live_beside_door(tmp_path: Path) -> None:
    result = _run("""
latestCameraPaths[0].prewarm_next = true;
walkTo(1, { hold: false }); updatePathWatch();
const before = [...events.slots];
walkTo(2, { hold: false }); updatePathWatch();
report({ before });
""", tmp_path)
    assert result["before"] == ["cam-yard", "cam-door"]
    assert result["slots"] == ["cam-door", "cam-yard"]
    assert result["showing"] == "cam-door"
    assert result["playing"] == ["cam-door", "cam-yard"]
