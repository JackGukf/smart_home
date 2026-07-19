from pathlib import Path

import pytest

from src.python.web_app import (
    _govee_cloud_devices,
    _govee_gear_mode_value,
    _govee_humidifier_state,
    _govee_mist_range,
    _load_humidifiers,
    _match_govee_cloud_device,
    HumidifierDefinition,
)
from src.python import web_app


def _write_humidifier_config(path: Path) -> None:
    path.write_text(
        """
humidifiers:
  devices:
    - name: Bedroom Humidifier
      provider: govee_cloud
      model: H7140
      room: Bedroom
      device_id: replace_me
    - name: Disabled Humidifier
      provider: govee_cloud
      model: H7141
      enabled: false
""",
        encoding="utf-8",
    )


def test_load_humidifiers_parses_entries_and_skips_disabled(tmp_path: Path) -> None:
    config = tmp_path / "devices.local.yaml"
    _write_humidifier_config(config)

    humidifiers = _load_humidifiers(config)

    assert len(humidifiers) == 1
    assert humidifiers[0].name == "Bedroom Humidifier"
    assert humidifiers[0].provider == "govee_cloud"
    assert humidifiers[0].model == "H7140"
    assert humidifiers[0].room == "Bedroom"
    assert humidifiers[0].device_id == "replace_me"


def test_load_humidifiers_tolerates_missing_file_and_section(tmp_path: Path) -> None:
    missing = tmp_path / "devices.local.yaml"
    assert _load_humidifiers(missing) == []

    empty = tmp_path / "empty.yaml"
    empty.write_text("tplink: {}\n", encoding="utf-8")
    assert _load_humidifiers(empty) == []


FAKE_DEVICE_LIST = [
    {
        "sku": "H7140",
        "device": "AA:BB:CC:DD:EE:FF:11:22",
        "deviceName": "Bedroom Humidifier",
        "capabilities": [
            {"type": "devices.capabilities.on_off", "instance": "powerSwitch"},
            {
                "type": "devices.capabilities.work_mode",
                "instance": "workMode",
                "parameters": {
                    "fields": [
                        {
                            "fieldName": "workMode",
                            "options": [{"name": "gearMode", "value": 1}, {"name": "Auto", "value": 3}],
                        },
                        {
                            "fieldName": "modeValue",
                            "options": [
                                {"name": "gearMode", "options": [{"value": 1}, {"value": 2}, {"value": 3}]},
                                {"name": "Auto", "value": 3},
                            ],
                        },
                    ]
                },
            },
        ],
    },
    {"sku": "H6076", "device": "11:22:33:44:55:66:77:88", "deviceName": "Floor Lamp", "capabilities": []},
]


@pytest.fixture(autouse=True)
def _reset_govee_cloud_state():
    web_app._GOVEE_CLOUD_CACHE.update({"devices": None, "fetched": 0.0})
    web_app.HUMIDIFIER_RUNTIME_STATE.clear()
    yield
    web_app._GOVEE_CLOUD_CACHE.update({"devices": None, "fetched": 0.0})
    web_app.HUMIDIFIER_RUNTIME_STATE.clear()


def _definition(device_id=None, model="H7140"):
    return HumidifierDefinition(
        name="Bedroom Humidifier", provider="govee_cloud", model=model, room="Bedroom", device_id=device_id
    )


def test_match_by_device_id_beats_model() -> None:
    match = _match_govee_cloud_device(_definition(device_id="AA:BB:CC:DD:EE:FF:11:22"), FAKE_DEVICE_LIST)
    assert match["deviceName"] == "Bedroom Humidifier"


def test_match_falls_back_to_unique_model_when_id_is_placeholder() -> None:
    match = _match_govee_cloud_device(_definition(device_id="replace_me"), FAKE_DEVICE_LIST)
    assert match["sku"] == "H7140"


def test_match_returns_none_for_ambiguous_model() -> None:
    doubled = FAKE_DEVICE_LIST + [dict(FAKE_DEVICE_LIST[0], device="other")]
    assert _match_govee_cloud_device(_definition(device_id=None), doubled) is None


def test_mist_range_and_gear_mode_come_from_capabilities() -> None:
    assert _govee_mist_range(FAKE_DEVICE_LIST[0]) == (1, 3)
    assert _govee_gear_mode_value(FAKE_DEVICE_LIST[0]) == 1
    # Unknown capability shape falls back to a safe default.
    assert _govee_mist_range(FAKE_DEVICE_LIST[1]) == (1, 8)
    assert _govee_gear_mode_value(FAKE_DEVICE_LIST[1]) == 1


def test_device_list_is_cached(monkeypatch) -> None:
    calls = []

    def fake_request(path, payload=None):
        calls.append(path)
        return {"code": 200, "data": FAKE_DEVICE_LIST}

    monkeypatch.setattr(web_app, "_govee_cloud_request", fake_request)
    monkeypatch.setenv("GOVEE_API_KEY", "test-key")

    assert _govee_cloud_devices() == FAKE_DEVICE_LIST
    assert _govee_cloud_devices() == FAKE_DEVICE_LIST
    assert calls == ["/router/api/v1/user/devices"]


def test_humidifier_state_parses_capability_values(monkeypatch) -> None:
    def fake_request(path, payload=None):
        assert path == "/router/api/v1/device/state"
        assert payload["payload"]["sku"] == "H7140"
        return {
            "payload": {
                "capabilities": [
                    {"type": "devices.capabilities.online", "instance": "online", "state": {"value": True}},
                    {"type": "devices.capabilities.on_off", "instance": "powerSwitch", "state": {"value": 1}},
                    {"type": "devices.capabilities.property", "instance": "humidity", "state": {"value": 45}},
                    {
                        "type": "devices.capabilities.work_mode",
                        "instance": "workMode",
                        "state": {"value": {"workMode": 1, "modeValue": 2}},
                    },
                ]
            }
        }

    monkeypatch.setattr(web_app, "_govee_cloud_request", fake_request)

    state = _govee_humidifier_state(FAKE_DEVICE_LIST[0])
    assert state == {"online": True, "is_on": True, "humidity": 45, "mist_level": 2}


def test_humidifier_state_returns_none_on_cloud_error(monkeypatch) -> None:
    def fake_request(path, payload=None):
        raise OSError("boom")

    monkeypatch.setattr(web_app, "_govee_cloud_request", fake_request)
    assert _govee_humidifier_state(FAKE_DEVICE_LIST[0]) is None
