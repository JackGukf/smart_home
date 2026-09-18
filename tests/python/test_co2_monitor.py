"""The Govee H5140 CO2 monitor on the dashboard.

  * CO2 is read alongside temperature and humidity, and a value outside what
    the sensor can measure is dropped rather than shown;
  * the level says what to do - fresh, ok, stuffy, poor - at fixed bands;
  * readings are mirrored into Home Assistant as a carbon_dioxide sensor, so
    there is a history and the house memory sees it; an offline monitor is
    not mirrored as if it had a reading;
  * the view is served from the background poll while it is fresh, so open
    screens do not each spend Govee API calls;
  * the card leads with CO2 and its 24 h line leaves gaps as gaps.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.python import sensor_history, web_app
from src.python.web_app import EnvironmentSensorDefinition, create_app

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"

MONITOR = {"sku": "H5140", "device": "0B:AD:00:00:00:00:00:01", "deviceName": "Smart CO₂ Monitor",
           "capabilities": [{"instance": "carbonDioxideConcentration"}, {"instance": "sensorTemperature"},
                            {"instance": "sensorHumidity"}]}


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    web_app._GOVEE_CLOUD_CACHE.update({"devices": None, "fetched": 0.0})
    web_app.ENVIRONMENT_RUNTIME_STATE.clear()
    monkeypatch.setenv("GOVEE_API_KEY", "key")
    yield
    web_app._GOVEE_CLOUD_CACHE.update({"devices": None, "fetched": 0.0})
    web_app.ENVIRONMENT_RUNTIME_STATE.clear()


def _state(co2=622, temp_f=73.94, humidity=51.7) -> dict:
    return {"payload": {"capabilities": [
        {"instance": "online", "state": {"value": True}},
        {"instance": "carbonDioxideConcentration", "state": {"value": co2}},
        {"instance": "sensorTemperature", "state": {"value": temp_f}},
        {"instance": "sensorHumidity", "state": {"value": humidity}},
    ]}}


def _cloud(monkeypatch, state: dict) -> list[str]:
    calls: list[str] = []

    def request(path, payload=None):
        calls.append(path)
        return {"data": [MONITOR]} if path.endswith("/user/devices") else state

    monkeypatch.setattr(web_app, "_govee_cloud_request", request)
    return calls


SENSOR = EnvironmentSensorDefinition(name="CO₂ Monitor", provider="govee_cloud", model="H5140",
                                     room="Bedroom", device_id="replace_me")


def test_the_card_reads_co2_with_temperature_and_humidity(monkeypatch) -> None:
    _cloud(monkeypatch, _state())
    card = web_app._environment_sensor_card(SENSOR)

    assert card["co2"] == 622 and card["co2_level"] == {"key": "fresh", "text": "Fresh"}
    assert card["temperature"] == 23.3 and card["humidity"] == 51.7
    assert card["co2_entity_id"] == "sensor.co2_monitor_co2"
    assert card["online"] is True


@pytest.mark.parametrize("bad", [0, 120, 40_000])
def test_a_reading_the_sensor_cannot_make_is_dropped(monkeypatch, bad) -> None:
    _cloud(monkeypatch, _state(co2=bad))
    card = web_app._environment_sensor_card(SENSOR)
    assert card["co2"] is None and card["temperature"] == 23.3


@pytest.mark.parametrize("ppm, key", [(420, "fresh"), (799, "fresh"), (800, "ok"), (999, "ok"),
                                      (1000, "stuffy"), (1499, "stuffy"), (1500, "poor"), (4000, "poor")])
def test_co2_levels(ppm, key) -> None:
    assert web_app.co2_level(ppm)["key"] == key
    assert web_app.co2_level(None) is None


def test_co2_is_mirrored_to_home_assistant_only_when_read(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN", "token")
    posted: list[tuple[str, dict]] = []
    monkeypatch.setattr(web_app, "_home_assistant_post", lambda config, token, path, body: posted.append((path, body)))
    config = tmp_path / "devices.yaml"
    config.write_text("home_assistant:\n  base_url: http://ha\n", encoding="utf-8")

    online = {"name": "CO₂ Monitor", "online": True, "co2": 1210, "co2_level": {"key": "stuffy"},
              "co2_entity_id": "sensor.co2_monitor_co2"}
    offline = {**online, "online": False, "co2_entity_id": "sensor.other_co2"}
    web_app._mirror_co2_to_home_assistant(config, [online, offline])

    assert [p for p, _ in posted] == ["/api/states/sensor.co2_monitor_co2"]
    body = posted[0][1]
    assert body["state"] == 1210
    assert body["attributes"]["device_class"] == "carbon_dioxide"
    assert body["attributes"]["unit_of_measurement"] == "ppm"
    assert body["attributes"]["level"] == "stuffy"

    monkeypatch.delenv("HOME_ASSISTANT_TOKEN")
    web_app._mirror_co2_to_home_assistant(config, [online])
    assert len(posted) == 1, "no token, no mirror"


def test_the_view_is_served_from_a_fresh_poll(tmp_path: Path, monkeypatch) -> None:
    calls = _cloud(monkeypatch, _state())
    monkeypatch.setattr(web_app, "_mirror_co2_to_home_assistant", lambda path, cards: None)
    config = tmp_path / "devices.yaml"
    config.write_text("environment:\n  sensors:\n    - name: CO₂ Monitor\n      model: H5140\n", encoding="utf-8")
    app = create_app(discovery_path=tmp_path / "s.json", config_path=config, check_camera_ports=False)
    client = TestClient(app)

    web_app._poll_environment_once(app)
    polled = len(calls)
    first = client.get("/api/environment-sensors").json()
    assert first["sensors"][0]["co2"] == 622
    assert len(calls) == polled, "served from the poll, no new Govee calls"

    app.state.environment_cache["at"] = time.time() - web_app.ENVIRONMENT_FRESH_S - 1
    client.get("/api/environment-sensors")
    assert len(calls) > polled, "a stale poll is not served"


def test_co2_history_is_an_allowed_group() -> None:
    assert sensor_history.validate_groups({"co2": ["sensor.co2_monitor_co2"]}) == {"co2": ["sensor.co2_monitor_co2"]}
    with pytest.raises(sensor_history.HistoryRequestError):
        sensor_history.validate_groups({"co2": ["binary_sensor.front_door"]})


def test_the_entity_id_is_a_clean_slug() -> None:
    assert web_app._environment_entity_id("CO₂ Monitor", "co2") == "sensor.co2_monitor_co2"
    assert web_app._environment_entity_id("Bedroom Thermo-Hygrometer", "co2") == "sensor.bedroom_thermo_hygrometer_co2"
    assert web_app._environment_entity_id("!!!", "co2") == "sensor.environment_co2"


HARNESS = r"""
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
globalThis.sensorTileFacet = ({ key, text }) => `<span data-facet="${key}">${text}</span>`;
globalThis.sensorTileIcon = () => '';
eval(src.match(/const CO2_TINT = [^;]+;/)[0].replace('const ', 'globalThis.'));
eval(pick('environmentSensorCard') + pick('co2SparkSvg'));
const card = environmentSensorCard({ name: 'CO₂ <Monitor>', room: 'Bedroom', model: 'H5140', online: true,
  co2: 1210, co2_level: { key: 'stuffy', text: 'Stuffy - open a window' }, temperature: 23.3, humidity: 51.7,
  co2_entity_id: 'sensor.co2_monitor_co2' });
const plain = environmentSensorCard({ name: 'Thermo', online: true, temperature: 21, humidity: 40 });
const hours = Array.from({ length: 24 }, (_, i) => (i === 5 || i === 6 ? null : 500 + i * 20));
const spark = co2SparkSvg(hours);
console.log(JSON.stringify({
  hero: /1210<span class="sdc-tile-unit">ppm CO₂/.test(card),
  level: card.includes('co2-stuffy') && card.includes('Stuffy - open a window'),
  tint: card.includes('--tint:var(--amber)'),
  facets: card.includes('data-facet="temperature">23.3°C') && card.includes('51.7%'),
  escaped: card.includes('CO₂ &lt;Monitor>'),
  spark: card.includes('data-co2-spark="sensor.co2_monitor_co2"'),
  plainHero: /21<span class="sdc-tile-unit">°C/.test(plain) && !plain.includes('data-co2-spark'),
  peak: /peak 960 ppm/.test(spark),
  empty: co2SparkSvg([null, 700, null]).includes('History fills in'),
}));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_the_card_leads_with_co2(tmp_path: Path) -> None:
    harness = tmp_path / "harness.js"
    harness.write_text(HARNESS, encoding="utf-8")
    out = subprocess.run(["node", str(harness), str(APP_JS)], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout) == {k: True for k in (
        "hero", "level", "tint", "facets", "escaped", "spark", "plainHero", "peak", "empty")}
