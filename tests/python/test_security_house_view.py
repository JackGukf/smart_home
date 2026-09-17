"""The Security view drawn as the house.

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
  boxes: HOUSE_ROOMS.map((r) => [r.x, r.y, r.w, r.h]),
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


def test_every_room_on_the_plan_is_inside_the_picture(tmp_path: Path) -> None:
    """A box placed off the canvas is invisible with no error to notice."""
    result = _run(tmp_path, [])

    assert "Master Bedroom" in result["plan"] and "Garage" in result["plan"]
    for (x, y, w, h), name in zip(result["boxes"], result["plan"]):
        assert 0 <= x and x + w <= 100, f"{name} runs off the side"
        assert 0 <= y and y + h <= 100, f"{name} runs off the bottom"


def test_the_upstairs_rooms_do_not_overlap(tmp_path: Path) -> None:
    result = _run(tmp_path, [])
    boxes = {n: b for n, b in zip(result["plan"], result["boxes"])}
    upstairs = ["Master Bedroom", "North Bedroom", "Hallway", "South Bedroom", "Bathroom"]

    for left, right in zip(upstairs, upstairs[1:]):
        lx, _, lw, _ = boxes[left]
        rx = boxes[right][0]
        assert lx + lw <= rx + 0.01, f"{left} overlaps {right}"


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
