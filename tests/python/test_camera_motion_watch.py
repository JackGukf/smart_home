"""A screen shows the front door camera when the front door sees motion.

A camera paired with a `motion_entity` in devices.local.yaml plays on the Home
card while that sensor reads motion, and stops `motion_linger_seconds` after it
reads clear. The rules that make it live with rather than fight the people in
the house, and that are each easy to lose in a refactor:

  * every screen decides for itself and starts out saying no - a dashboard left
    open on a phone would otherwise pull a video stream over cellular because a
    cat walked past;
  * motion returning inside the linger window cancels the stop, so someone
    standing at the door does not watch the picture blink out;
  * touching the card releases the episode - the automation stops managing it
    and will not yank the picture away five minutes later;
  * the saved camera choice is never overwritten, so ending an episode puts
    back the camera you actually picked.

The state machine runs under node with the DOM, timers and device data stubbed.
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

const CAMERA = {
  id: '192.168.0.191', name: 'Front door camera', room: 'Home',
  motion_entity: 'binary_sensor.0xa4c138f3061bad8d_presence',
  motion_linger_seconds: 300,
};

const events = { renders: 0, log: [], snapshots: 0 };
globalThis.latestCameras = [CAMERA];
globalThis.latestTuyaDevices = [
  { id: CAMERA.motion_entity, state: 'off', online: true },
];
globalThis.activeCameraIds = new Set();
globalThis.homeCameraOverride = null;
globalThis.motionEpisodes = new Map();
// No routes configured here - this file is about the single-camera watch. The
// real path functions are loaded rather than stubbed so that the two rules
// meeting each other is exercised, not imagined.
globalThis.latestCameraPaths = [];
globalThis.pathEpisodes = new Map();
globalThis.latestCameraById = new Map();
globalThis.applyPathSlots = () => {};
globalThis.renderHomeCamera = () => { events.renders += 1; };
globalThis.logActivity = (msg) => { events.log.push(msg); };
globalThis.captureSnapshotOnce = async () => { events.snapshots += 1; };

// One browser's storage. The preference is per screen, so this standing in for
// localStorage is the whole mechanism, not a convenience.
const store = new Map();
globalThis.localStorage = {
  getItem: (k) => (store.has(k) ? store.get(k) : null),
  setItem: (k, v) => store.set(k, String(v)),
};

// Just enough DOM for the switch itself.
const toggleWrap = { hidden: false };
const toggleBox = { checked: false };
globalThis.document = {
  querySelector: (selector) => ({
    '#homeCameraAutoWrap': toggleWrap,
    '#homeCameraAuto': toggleBox,
  }[selector] ?? null),
};

// Timers are held rather than run, so a test can say exactly when the linger
// window expires instead of waiting five real minutes for it.
let timers = [];
let nextTimerId = 1;
globalThis.setTimeout = (fn, ms) => {
  const id = nextTimerId++;
  timers.push({ id, fn, ms });
  return id;
};
globalThis.clearTimeout = (id) => { timers = timers.filter((t) => t.id !== id); };
const pendingTimers = () => timers.map((t) => t.ms);
const fireTimers = () => { const due = timers; timers = []; due.forEach((t) => t.fn()); };

eval(src.match(/const MOTION_WATCH_DEFAULT_LINGER_MS = [^;]+;/)[0].replace('const ', 'globalThis.'));
eval(src.match(/const MOTION_ON_STATES = new Set\\([^)]*\\);/)[0].replace('const ', 'globalThis.'));
eval(src.match(/const HOME_CAMERA_AUTO_KEY = [^;]+;/)[0].replace('const ', 'globalThis.'));

eval(pick('cameraIdFor') + pick('motionSensorIsTripped') + pick('motionLingerMs')
   + pick('openMotionEpisode') + pick('closeMotionEpisode')
   + pick('stopAllMotionEpisodes') + pick('releaseMotionEpisodes')
   + pick('updateMotionWatch') + pick('motionWatchEnabled')
   + pick('setMotionWatchEnabled') + pick('anyCameraWatchesMotion')
   + pick('syncMotionWatchToggle') + pick('cameraPathList') + pick('pathCameraIds')
   + pick('pathEpisodeCameras') + pick('activePathCameraId') + pick('openPathEpisode')
   + pick('advancePathEpisode') + pick('closePathEpisode') + pick('stopAllPathEpisodes')
   + pick('updatePathWatch'));

const setMotion = (state, extra = {}) => {
  // The server reports the sensor state on the camera card itself; `online`
  // still comes from the device list, so both are set.
  globalThis.latestCameras = latestCameras.map(
    (c) => (c.motion_entity ? { ...c, motion_state: extra.online === false ? undefined : state } : c));
  globalThis.latestTuyaDevices = [
    { id: CAMERA.motion_entity, state, online: true, ...extra },
  ];
};
/* Most tests are about what happens once a screen has opted in. */
const optIn = () => setMotionWatchEnabled(true);
const report = (extra = {}) => console.log(JSON.stringify({
  playing: activeCameraIds.has(CAMERA.id),
  override: homeCameraOverride,
  episodes: motionEpisodes.size,
  pending: pendingTimers(),
  stored: store.get(HOME_CAMERA_AUTO_KEY) ?? null,
  toggle: { hidden: toggleWrap.hidden, checked: toggleBox.checked },
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


# ── Off until this screen asks for it ────────────────────────────────────────

def test_a_screen_that_has_not_opted_in_does_nothing(tmp_path: Path) -> None:
    """The default. A dashboard left open on a phone must not start pulling
    video over cellular because something moved at the front door."""
    result = _run("""
setMotion('on');
updateMotionWatch();
report();
""", tmp_path)
    assert result["playing"] is False
    assert result["episodes"] == 0
    assert result["stored"] is None, "nothing is written until somebody chooses"


def test_the_choice_is_remembered_for_this_screen(tmp_path: Path) -> None:
    """Per browser, which is what lets the panel and the laptop disagree."""
    result = _run("""
optIn();
report();
""", tmp_path)
    assert result["stored"] == "1"


def test_enabling_picks_up_motion_already_in_progress(tmp_path: Path) -> None:
    """Ticking the box with somebody on the doorstep should not wait a minute
    for the next refresh to notice."""
    result = _run("""
setMotion('on');
optIn();
report();
""", tmp_path)
    assert result["playing"] is True


def test_turning_it_off_puts_the_card_back_immediately(tmp_path: Path) -> None:
    """Not five minutes later, when the linger happens to expire."""
    result = _run("""
optIn();
setMotion('on'); updateMotionWatch();
setMotionWatchEnabled(false);
report();
""", tmp_path)
    assert result["playing"] is False
    assert result["override"] is None
    assert result["episodes"] == 0
    assert result["stored"] == "0"


# ── Motion puts the camera up ────────────────────────────────────────────────

def test_motion_starts_the_camera_and_takes_over_the_card(tmp_path: Path) -> None:
    result = _run("""
optIn();
setMotion('on');
updateMotionWatch();
report();
""", tmp_path)
    assert result["playing"] is True
    assert result["override"] == "192.168.0.191"
    assert any("Front door camera" in line for line in result["log"])


def test_an_offline_sensor_is_not_read_as_motion(tmp_path: Path) -> None:
    result = _run("""
optIn();
setMotion('on', { online: false });
updateMotionWatch();
report();
""", tmp_path)
    assert result["playing"] is False


def test_a_camera_without_a_paired_sensor_is_left_alone(tmp_path: Path) -> None:
    result = _run("""
optIn();
latestCameras = [{ id: 'cam2', name: 'Garage', host: 'cam2' }];
setMotion('on');
updateMotionWatch();
report();
""", tmp_path)
    assert result["episodes"] == 0


# ── The switch itself ────────────────────────────────────────────────────────

def test_the_switch_is_hidden_when_nothing_is_paired(tmp_path: Path) -> None:
    """A control that cannot do anything is worse than no control."""
    result = _run("""
latestCameras = [{ id: 'cam2', name: 'Garage', host: 'cam2' }];
syncMotionWatchToggle();
report();
""", tmp_path)
    assert result["toggle"]["hidden"] is True


def test_the_switch_shows_and_reflects_the_stored_choice(tmp_path: Path) -> None:
    result = _run("""
optIn();
syncMotionWatchToggle();
report();
""", tmp_path)
    assert result["toggle"]["hidden"] is False
    assert result["toggle"]["checked"] is True


# ── Clearing puts it away again, five minutes later ──────────────────────────

def test_the_stop_is_scheduled_for_the_configured_linger(tmp_path: Path) -> None:
    result = _run("""
optIn();
setMotion('on');  updateMotionWatch();
setMotion('off'); updateMotionWatch();
report();
""", tmp_path)
    assert result["pending"] == [300_000], "five minutes, from motion_linger_seconds"
    assert result["playing"] is True, "still up during the linger window"


def test_the_camera_stops_when_the_linger_expires(tmp_path: Path) -> None:
    result = _run("""
optIn();
setMotion('on');  updateMotionWatch();
setMotion('off'); updateMotionWatch();
fireTimers();
report();
""", tmp_path)
    assert result["playing"] is False
    assert result["override"] is None, "the card goes back to the chosen camera"
    assert result["episodes"] == 0


def test_motion_returning_cancels_the_stop(tmp_path: Path) -> None:
    """Someone standing at the door must not watch the picture blink out."""
    result = _run("""
optIn();
setMotion('on');  updateMotionWatch();
setMotion('off'); updateMotionWatch();
setMotion('on');  updateMotionWatch();
fireTimers();
report();
""", tmp_path)
    assert result["pending"] == []
    assert result["playing"] is True


def test_a_missing_linger_falls_back_to_five_minutes(tmp_path: Path) -> None:
    result = _run("""
optIn();
latestCameras = [{ ...CAMERA, motion_linger_seconds: undefined }];
setMotion('on');  updateMotionWatch();
setMotion('off'); updateMotionWatch();
report();
""", tmp_path)
    assert result["pending"] == [300_000]


# ── A person beats the automation ────────────────────────────────────────────

def test_releasing_stops_the_automation_managing_the_card(tmp_path: Path) -> None:
    result = _run("""
optIn();
setMotion('on'); updateMotionWatch();
releaseMotionEpisodes();          // the viewer pressed stop, or picked a camera
setMotion('off'); updateMotionWatch();
fireTimers();
report();
""", tmp_path)
    assert result["override"] is None, "the viewer's saved choice wins immediately"
    assert result["pending"] == [], "no stop is scheduled for a released episode"
    assert result["playing"] is True, "the automation must not turn off what a person turned on"


def test_a_released_episode_is_forgotten_once_motion_clears(tmp_path: Path) -> None:
    """So the next person at the door gets the automation back."""
    result = _run("""
optIn();
setMotion('on'); updateMotionWatch();
releaseMotionEpisodes();
setMotion('off'); updateMotionWatch();
const afterClear = motionEpisodes.size;
activeCameraIds.clear();
setMotion('on'); updateMotionWatch();
report({ afterClear });
""", tmp_path)
    assert result["afterClear"] == 0
    assert result["playing"] is True, "a fresh rise starts a fresh episode"


# ── The pairing reaches the browser ──────────────────────────────────────────

def test_the_api_carries_the_pairing_to_the_page(tmp_path: Path) -> None:
    """The rule above is worth nothing if the camera payload omits the fields."""
    import yaml
    from fastapi.testclient import TestClient

    from src.python.web_app import create_app

    cfg = tmp_path / "devices.local.yaml"
    cfg.write_text(yaml.dump({
        "cameras": [
            {"name": "Front door camera", "host": "192.168.0.191",
             "provider": "wyze", "snapshot_url": "http://192.168.0.191/snap.jpg",
             "motion_entity": "binary_sensor.front_door_presence",
             "motion_linger_seconds": 300},
            {"name": "Garage camera", "host": "192.168.0.192",
             "provider": "wyze", "snapshot_url": "http://192.168.0.192/snap.jpg"},
        ],
    }), encoding="utf-8")

    client = TestClient(create_app(config_path=cfg, check_camera_ports=False))
    cameras = {c["name"]: c for c in client.get("/api/cameras").json()["cameras"]}

    assert cameras["Front door camera"]["motion_entity"] == "binary_sensor.front_door_presence"
    assert cameras["Front door camera"]["motion_linger_seconds"] == 300
    assert "motion_entity" not in cameras["Garage camera"], "unpaired cameras stay unpaired"
