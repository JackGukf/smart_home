import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.python.web_app import (
    EnvironmentSensorDefinition,
    _load_environment_sensors,
    _match_environment_sensor,
    create_app,
)
from src.python import web_app


@pytest.fixture(autouse=True)
def _reset_environment_state():
    # Mirrors test_humidifiers.py's _reset_govee_cloud_state: ENVIRONMENT_RUNTIME_STATE
    # and _GOVEE_CLOUD_CACHE are module-level globals shared across tests (and with the
    # humidifier test module), so each test needs a clean slate on both ends.
    web_app._GOVEE_CLOUD_CACHE.update({"devices": None, "fetched": 0.0})
    web_app.ENVIRONMENT_RUNTIME_STATE.clear()
    yield
    web_app._GOVEE_CLOUD_CACHE.update({"devices": None, "fetched": 0.0})
    web_app.ENVIRONMENT_RUNTIME_STATE.clear()


def _write_environment_config(path: Path) -> None:
    path.write_text(
        """
environment:
  sensors:
    - name: Bedroom Thermo-Hygrometer
      provider: govee_cloud
      model: H5140
      room: Bedroom
      device_id: replace_me
    - name: Disabled Sensor
      provider: govee_cloud
      model: H5179
      enabled: false
""",
        encoding="utf-8",
    )


class FakeController:
    async def gather_status(self, *args, **kwargs):
        return []


def _client(tmp_path: Path) -> TestClient:
    discovery = tmp_path / "tplink.json"
    discovery.write_text(json.dumps({"switches": []}), encoding="utf-8")
    config = tmp_path / "devices.local.yaml"
    _write_environment_config(config)
    return TestClient(
        create_app(discovery_path=discovery, config_path=config, controller=FakeController())
    )


def test_load_parses_entries_and_skips_disabled(tmp_path: Path) -> None:
    config = tmp_path / "devices.local.yaml"
    _write_environment_config(config)

    sensors = _load_environment_sensors(config)

    assert len(sensors) == 1
    assert sensors[0].name == "Bedroom Thermo-Hygrometer"
    assert sensors[0].model == "H5140"
    assert sensors[0].room == "Bedroom"
    assert sensors[0].provider == "govee_cloud"


def test_load_tolerates_missing_file_null_and_absent_section(tmp_path: Path) -> None:
    assert _load_environment_sensors(tmp_path / "nope.yaml") == []

    absent = tmp_path / "absent.yaml"
    absent.write_text("tplink: {}\n", encoding="utf-8")
    assert _load_environment_sensors(absent) == []

    null = tmp_path / "null.yaml"
    null.write_text("environment:\n", encoding="utf-8")
    assert _load_environment_sensors(null) == []

    null_sensors = tmp_path / "null_sensors.yaml"
    null_sensors.write_text("environment:\n  sensors:\n", encoding="utf-8")
    assert _load_environment_sensors(null_sensors) == []


def test_match_prefers_device_id_then_unique_model() -> None:
    devices = [
        {"sku": "H5140", "device": "AA:BB", "capabilities": []},
        {"sku": "H5179", "device": "CC:DD", "capabilities": []},
    ]

    by_id = EnvironmentSensorDefinition(
        name="s", provider="govee_cloud", model="H5179", room=None, device_id="AA:BB"
    )
    assert _match_environment_sensor(by_id, devices)["device"] == "AA:BB"

    by_model = EnvironmentSensorDefinition(
        name="s", provider="govee_cloud", model="H5140", room=None, device_id="replace_me"
    )
    assert _match_environment_sensor(by_model, devices)["device"] == "AA:BB"


def test_match_returns_none_for_ambiguous_model() -> None:
    devices = [
        {"sku": "H5140", "device": "AA:BB", "capabilities": []},
        {"sku": "H5140", "device": "CC:DD", "capabilities": []},
    ]
    sensor = EnvironmentSensorDefinition(
        name="s", provider="govee_cloud", model="H5140", room=None, device_id="replace_me"
    )

    assert _match_environment_sensor(sensor, devices) is None


def test_endpoint_without_api_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GOVEE_API_KEY", raising=False)

    payload = _client(tmp_path).get("/api/environment-sensors").json()

    assert len(payload["sensors"]) == 1
    assert payload["sensors"][0]["status"] == "needs_api_key"
    assert payload["sensors"][0]["temperature"] is None


def test_endpoint_converts_fahrenheit_to_celsius(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GOVEE_API_KEY", "test-key")
    web_app._GOVEE_CLOUD_CACHE["devices"] = None
    web_app._GOVEE_CLOUD_CACHE["fetched"] = 0

    def fake_request(path, payload=None):
        if path.endswith("/user/devices"):
            return {"data": [{
                "sku": "H5140", "device": "AA:BB", "deviceName": "Bedroom",
                "capabilities": [
                    {"type": "devices.capabilities.property", "instance": "sensorTemperature"},
                    {"type": "devices.capabilities.property", "instance": "sensorHumidity"},
                ],
            }]}
        return {"payload": {"capabilities": [
            {"instance": "sensorTemperature", "state": {"value": 71.6}},
            {"instance": "sensorHumidity", "state": {"value": 48}},
        ]}}

    monkeypatch.setattr(web_app, "_govee_cloud_request", fake_request)

    sensor = _client(tmp_path).get("/api/environment-sensors").json()["sensors"][0]

    assert sensor["temperature"] == 22.0  # 71.6 F
    assert sensor["humidity"] == 48
    assert sensor["online"] is True


def test_endpoint_reports_offline_when_cloud_fails(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GOVEE_API_KEY", "test-key")
    web_app._GOVEE_CLOUD_CACHE["devices"] = None
    web_app._GOVEE_CLOUD_CACHE["fetched"] = 0

    def fake_request(path, payload=None):
        raise RuntimeError("cloud down")

    monkeypatch.setattr(web_app, "_govee_cloud_request", fake_request)

    sensor = _client(tmp_path).get("/api/environment-sensors").json()["sensors"][0]

    assert sensor["online"] is False
    assert sensor["temperature"] is None
