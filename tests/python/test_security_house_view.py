"""The Security view drawn as the house: a picture with live pins over it.

  * every room on the plan is a real place in this house, and each sensor finds
    its room through Areas rather than a list of entity ids;
  * the two exceptions are written down: Areas has one "Bedroom" for the whole
    upstairs, and a camera's person detector belongs where the camera looks;
  * a sensor whose area says nothing is still reachable, or it would vanish;
  * arming and the panel switches keep the handlers they already had.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

HARNESS = r"""
const src = require('fs').readFileSync(process.argv[2], 'utf8');
const pick = (name) => {
  const at = src.indexOf(`function ${name}(`);
  if (at < 0) throw new Error(`missing function ${name}`);
  let depth = 0, i = src.indexOf('{', at);
  for (; i < src.length; i++) {
    if (src[i] === '{') depth++;
    else if (src[i] === '}') { depth--; if (depth === 0) return src.slice(at, i + 1); }
  }
  throw new Error(`unbalanced ${name}`);
};
const constant = (name) => {
  const at = src.indexOf(`const ${name} = [`);
  if (at < 0) throw new Error(`missing ${name}`);
  return src.slice(at, src.indexOf('\n];', at) + 3).replace('const ', 'globalThis.');
};
globalThis.areasDoc = {
  areas: [{ id: 'bedroom', name: 'Bedroom' }, { id: 'family-room', name: 'Family Room' },
          { id: 'office', name: 'Office' }, { id: 'utility-room', name: 'Utility Room' }],
  assignments: {
    'sensor:master-bedroom': 'bedroom',
    'sensor:motion-sensor-and-th-upstairs': 'bedroom',
    'sensor:motion-sensor-and-th-bedroom': 'bedroom',
    'sensor:vibration-sensor-backdoor': 'family-room',
    'sensor:door-sensor-office-window-r': 'office',
    'sensor:water-sensor': 'utility-room',
  },
};
eval(constant('ROOM_OVERRIDES') + constant('HOUSE_ROOMS'));
eval(pick('areaSlug') + pick('sensorBaseName') + pick('shortZoneName')
   + pick('cameraZoneRoom') + pick('zoneRoom'));
globalThis.SENSOR_SUFFIXES = [' Contact', ' Occupancy', ' Motion', ' Smoke', ' Moisture', ' Vibration', ' Person'];
const zones = JSON.parse(process.argv[3]);
console.log(JSON.stringify({
  rooms: zones.map((z) => zoneRoom(z)),
  plan: HOUSE_ROOMS.map((r) => r.name),
  pins: HOUSE_ROOMS.map((r) => ({ name: r.name, x: r.x, y: r.y, w: r.w || 0, cover: r.cover || null })),
}));
"""


def _run(tmp_path: Path, zones: list[dict]) -> dict:
    harness = tmp_path / "harness.js"
    harness.write_text(HARNESS, encoding="utf-8")
    out = subprocess.run(
        ["node", str(harness), str(APP_JS), json.dumps(zones)],
        capture_output=True, text=True, check=True,
    )
    return json.loads(out.stdout)


def test_each_sensor_finds_its_room(tmp_path: Path) -> None:
    zones = [
        {"id": "binary_sensor.8k2g_motion", "name": "Master Bedroom Motion"},
        {"id": "binary_sensor.0xa4c138ae_presence", "name": "Motion sensor and TH Upstairs Occupancy"},
        {"id": "binary_sensor.0xa4c13805_presence", "name": "Motion sensor and TH bedroom Occupancy"},
        {"id": "binary_sensor.0xa4c1387_vibration", "name": "Vibration sensor backdoor Vibration"},
        {"id": "binary_sensor.0xffffdc_contact", "name": "Door sensor office window R"},
        {"id": "binary_sensor.garage_camera_npu_person", "name": "Garage Camera (NPU) Person"},
        {"id": "binary_sensor.frontyard_camera_npu_person", "name": "Frontyard Camera (NPU) Person"},
        {"id": "binary_sensor.front_door_camera_npu_person", "name": "Front Door Camera (NPU) Person"},
        {"id": "binary_sensor.nowhere_contact", "name": "Sensor nobody assigned"},
    ]

    rooms = _run(tmp_path, zones)["rooms"]

    assert rooms == [
        "Master Bedroom",   # the ecobee sensors name the master bedroom
        "Hallway",          # both upstairs sensors are in the hallway between the bedrooms
        "Hallway",
        "Family Room",      # from its area
        "Office",
        "Garage",           # a camera belongs where it looks
        "Front Yard",
        "Front Door",
        None,               # no area: shown under "not in a room", never dropped
    ]


def test_every_pin_and_cover_is_inside_the_picture(tmp_path: Path) -> None:
    """A pin placed off the picture is invisible with no error to notice."""
    result = _run(tmp_path, [])

    assert "Master Bedroom" in result["plan"] and "Garage" in result["plan"]
    for pin in result["pins"]:
        assert 0 < pin["x"] - pin["w"] / 2 and pin["x"] + pin["w"] / 2 < 100, f"{pin['name']} runs off the side"
        assert 0 < pin["y"] < 100, f"{pin['name']} runs off the picture"
        if pin["cover"]:
            assert 0 < pin["cover"][0] < 100 and 0 < pin["cover"][1] < 100


def test_no_two_pins_sit_on_each_other(tmp_path: Path) -> None:
    pins = _run(tmp_path, [])["pins"]
    for i, a in enumerate(pins):
        for b in pins[i + 1:]:
            apart = abs(a["x"] - b["x"]) > (a["w"] + b["w"]) / 2 or abs(a["y"] - b["y"]) > 4
            assert apart, f"{a['name']} and {b['name']} overlap"


def test_the_pictures_bedroom_names_are_covered_with_ours(tmp_path: Path) -> None:
    """It paints "Bedroom 1-3"; the house has a master, a north and a south bedroom."""
    pins = {p["name"]: p for p in _run(tmp_path, [])["pins"]}
    for room in ("Master Bedroom", "North Bedroom", "South Bedroom"):
        assert pins[room]["cover"], f"{room} needs its name over the painted one"
        assert pins[room]["w"], f"{room}'s painted icons need covering even with no sensors"


def test_the_picture_is_the_one_the_pins_were_measured_on() -> None:
    from PIL import Image

    js = APP_JS.read_text(encoding="utf-8")
    picture = PROJECT_ROOT / "src" / "python" / "web_static" / "security-house.jpg"
    assert 'const HOUSE_PICTURE = "/static/security-house.jpg?v=' in js
    assert Image.open(picture).size == (1312, 1199), "a new picture means re-measuring every pin"
    assert picture.stat().st_size < 600_000, "the panel loads this on every visit to the view"


def test_arming_and_the_panel_switches_keep_their_handlers() -> None:
    js = APP_JS.read_text(encoding="utf-8")
    body = js[js.index("function renderAlarmSection("):js.index("/* Choosing a room only changes")]

    # Built from a list, so check the list and the attribute that carries it.
    assert 'data-arm-mode="${mode}"' in body
    for mode in ('"home", "Arm home"', '"away", "Arm away"', '"disarmed", "Disarm"'):
        assert mode in body, f"{mode} is not offered"
    assert "data-ha-command=" in body and "data-ha-entity-id=" in body
    assert 'id="sirenTestBtn"' in body and 'id="sosTriggerBtn"' in body


def test_the_view_survives_a_poll_without_moving() -> None:
    """A refresh every 60s must not throw the reader back to another room."""
    js = APP_JS.read_text(encoding="utf-8")

    assert "let selectedHouseRoom = null;" in js
    body = js[js.index("function renderAlarmSection("):js.index("/* Choosing a room only changes")]
    assert "if (!selectedHouseRoom" in body, "the selection is only re-derived when it has gone"


PIN_HARNESS = r"""
const src = require('fs').readFileSync(process.argv[2], 'utf8');
const pick = (name) => {
  const at = src.indexOf(`function ${name}(`);
  let depth = 0, i = src.indexOf('{', at);
  for (; i < src.length; i++) {
    if (src[i] === '{') depth++;
    else if (src[i] === '}') { depth--; if (depth === 0) return src.slice(at, i + 1); }
  }
};
globalThis.escapeHtml = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');
globalThis.zoneIsBreached = (z) => z.state === 'on';
globalThis.zoneIconSVG = () => '<svg></svg>';
globalThis.selectedHouseRoom = 'Garage';
eval(pick('houseRoomHtml') + pick('houseLatestZone'));
const garage = { name: 'Garage', x: 19, y: 50, w: 9.4 };
const master = { name: 'Master Bedroom', x: 30, y: 15, w: 6.9, cover: [29, 27] };
const bath = { name: 'Bathroom', x: 58, y: 20, named: true };
const hall = { name: 'Hallway', x: 50, y: 33, named: true };
console.log(JSON.stringify({
  quiet: houseRoomHtml(garage, [{ name: 'Garage camera', state: 'off' }]),
  hot: houseRoomHtml(garage, [{ name: 'Garage camera', state: 'on' }]),
  empty: houseRoomHtml(master, []),
  bare: houseRoomHtml(bath, []),
  named: houseRoomHtml(hall, [{ name: 'Upstairs', state: 'off' }]),
  latest: houseLatestZone([{ name: 'a', age_seconds: 300 }, { name: 'b', age_seconds: 20 }, { name: 'c' }]).name,
}));
"""


def test_a_room_is_a_pin_a_no_sensors_chip_or_nothing(tmp_path: Path) -> None:
    harness = tmp_path / "pins.js"
    harness.write_text(PIN_HARNESS, encoding="utf-8")
    out = subprocess.run(["node", str(harness), str(APP_JS)], capture_output=True, text=True, check=True)
    r = json.loads(out.stdout)

    assert 'data-house-room="Garage"' in r["quiet"] and "min-width:9.4%" in r["quiet"]
    assert "selected" in r["quiet"] and "breached" not in r["quiet"]
    assert "house-pin breached" in r["hot"] and "1 active" in r["hot"]
    # No sensors, but painted icons and a painted name to cover: our name, and a chip.
    assert "Master Bedroom</span>" in r["empty"] and "No sensors" in r["empty"]
    assert "data-house-room" not in r["empty"], "nothing to open in a room without sensors"
    assert r["bare"] == "", "nothing painted there, nothing to cover"
    assert 'house-pin-name">Hallway' in r["named"]
    assert r["latest"] == "b"
