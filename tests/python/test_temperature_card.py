"""The Temperatures card: which sensors it counts, and where.

  * the ecobee's remote sensors are also Home Assistant entities, and the same
    sensor used to be counted twice - once through the thermostat, once as a
    sensor group;
  * a sensor in an outdoor area is outdoor, whatever its name says;
  * names are shortened to the place, since the card has no room for models.

Driven under node with the real functions sliced out of app.js.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"
INDEX_HTML = PROJECT_ROOT / "src" / "python" / "web_static" / "index.html"

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
globalThis.areasDoc = {
  areas: [{ id: 'front-door' }, { id: 'bedroom' }, { id: 'porch', outdoor: true }, { id: 'back-yard', outdoor: false }],
  assignments: {
    'sensor:motion-sensor-and-th-front-door': 'front-door',
    'sensor:motion-sensor-and-th-bedroom': 'bedroom',
  },
};
globalThis.latestThermostats = [{
  id: 'climate.my_ecobee', temperature_unit: '°C',
  sensors: [{ id: '8jt7_temperature', name: 'Family Room', temperature: 23.5, occupied: false }],
}];
const reading = (name, category, entity, value) => ({ name, category, entity_id: entity, values: { State: String(value) } });
globalThis.latestTuyaDevices = [
  reading('Family room Temperature', 'tuya_temperature', 'sensor.8jt7_temperature', 23.5),
  reading('Motion sensor and TH front door Temperature', 'tuya_temperature', 'sensor.fd_temperature', 14.8),
  reading('Motion sensor and TH front door Humidity', 'tuya_humidity', 'sensor.fd_humidity', 72),
  reading('Motion sensor and TH bedroom Temperature', 'tuya_temperature', 'sensor.bd_temperature', 23.0),
];
globalThis.isTuyaCamera = () => false;
globalThis.groupSensorDevices = (devices) => {
  const map = new Map();
  for (const d of devices) {
    const key = d.name.replace(/ (Temperature|Humidity)$/, '');
    if (!map.has(key)) map.set(key, []);
    map.get(key).push(d);
  }
  return [...map.entries()].map(([name, readings]) => ({ name, readings }));
};
globalThis.readingMetricNumber = (r) => parseFloat(r.values.State);
eval(src.match(/const OUTDOOR_AREA_IDS = [^;]+;/)[0].replace('const ', 'globalThis.'));
eval(pick('areaSlug') + pick('isOutdoorArea') + pick('shortSensorName') + pick('homeTempSources'));
console.log(JSON.stringify({
  sources: homeTempSources(),
  names: JSON.parse(process.argv[3]).map(shortSensorName),
  outdoor: ['front-door', 'bedroom', 'porch', 'back-yard', undefined].map((id) => isOutdoorArea(id)),
}));
"""


def _run(tmp_path: Path, names: list[str]) -> dict:
    harness = tmp_path / "harness.js"
    harness.write_text(HARNESS, encoding="utf-8")
    out = subprocess.run(
        ["node", str(harness), str(APP_JS), json.dumps(names)],
        capture_output=True, text=True, check=True,
    )
    return json.loads(out.stdout)


def test_an_ecobee_sensor_is_counted_once(tmp_path: Path) -> None:
    sources = _run(tmp_path, [])["sources"]
    entities = [s["tempEntity"] for s in sources]

    assert entities.count("sensor.8jt7_temperature") == 1
    assert len(sources) == 3


def test_the_front_door_sensor_is_outdoor_by_its_area(tmp_path: Path) -> None:
    by_entity = {s["tempEntity"]: s for s in _run(tmp_path, [])["sources"]}

    assert by_entity["sensor.fd_temperature"]["outdoor"] is True
    assert by_entity["sensor.fd_temperature"]["humEntity"] == "sensor.fd_humidity"
    assert by_entity["sensor.fd_temperature"]["humidity"] == 72
    assert by_entity["sensor.bd_temperature"]["outdoor"] is False
    assert by_entity["sensor.8jt7_temperature"]["outdoor"] is False


def test_an_area_can_say_it_is_outdoors_or_not(tmp_path: Path) -> None:
    # front-door by default, porch by its own flag; back-yard's flag overrides the default.
    assert _run(tmp_path, [])["outdoor"] == [True, False, True, False, False]


def test_names_shorten_to_the_place(tmp_path: Path) -> None:
    names = _run(tmp_path, [
        "Motion sensor and TH front door",
        "Motion and TH Kitchen and Family Room",
        "Temperature and humidity south bedroom",
        "Motion sensor and illumination",
        "IR remote family room",
    ])["names"]

    assert names == [
        "Front door motion",
        "Kitchen and Family Room motion",
        "South bedroom T&H",
        "Motion & light",
        "IR remote family room",
    ]


def test_the_card_has_four_sparklines_and_no_tiles() -> None:
    js = APP_JS.read_text(encoding="utf-8")

    for key in ("indoor_temperature", "outdoor_temperature", "indoor_humidity", "outdoor_humidity"):
        assert f'key: "{key}"' in js
    assert "temp-sensor-tile" not in js
    assert '"/api/sensors/history"' in js


def test_the_hero_row_wraps_rather_than_colliding():
    """Four figures - indoor, humidity, CO2, outdoor - do not fit a narrow
    card, and this card is narrow on a phone *and* in its column on a laptop.
    Grid tracks answered that by printing over each other (2026-09-20); a
    wrapping row answers it without a media or container query, which matters
    because the owner's iPad ignores container queries."""
    from pathlib import Path

    css = (Path(__file__).resolve().parents[2] / "src" / "python" / "web_static" / "styles.css").read_text(encoding="utf-8")
    hero = css[css.index(".tc-hero {"):css.index(".tc-big")]

    assert "flex-wrap: wrap;" in hero and "display: flex;" in hero
    assert "grid-template-columns" not in hero, "fixed tracks cannot wrap"
    # Outdoor keeps to the right until the row wraps.
    assert ".tc-out { margin-left: auto; }" in css
