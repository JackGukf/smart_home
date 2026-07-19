import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.python.web_app import (
    _govee_cloud_devices,
    _govee_gear_mode_value,
    _govee_humidifier_state,
    _govee_mist_range,
    _load_humidifiers,
    _match_govee_cloud_device,
    create_app,
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


def test_govee_cloud_request_raises_on_api_error_code(monkeypatch) -> None:
    class FakeResponse:
        def read(self):
            return json.dumps({"code": 429, "message": "rate limited"}).encode()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setenv("GOVEE_API_KEY", "test-key")
    monkeypatch.setattr(web_app, "urlopen", lambda request, timeout: FakeResponse())

    with pytest.raises(RuntimeError, match="429"):
        web_app._govee_cloud_request("/router/api/v1/user/devices")


class FakeController:
    async def statuses(self, definitions):
        return []


def _write_discovery(path: Path) -> None:
    path.write_text(json.dumps({"switches": []}), encoding="utf-8")


def _client(tmp_path: Path) -> TestClient:
    discovery = tmp_path / "tplink.json"
    config = tmp_path / "devices.local.yaml"
    _write_discovery(discovery)
    _write_humidifier_config(config)
    return TestClient(
        create_app(discovery_path=discovery, config_path=config, controller=FakeController())
    )


def test_humidifiers_endpoint_without_api_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GOVEE_API_KEY", raising=False)
    client = _client(tmp_path)

    payload = client.get("/api/humidifiers").json()

    card = payload["humidifiers"][0]
    assert card["status"] == "needs_api_key"
    assert card["controllable"] is False
    assert "GOVEE_API_KEY" in card["note"]


def test_humidifiers_endpoint_healthy(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GOVEE_API_KEY", "test-key")

    def fake_request(path, payload=None):
        if path == "/router/api/v1/user/devices":
            return {"code": 200, "data": FAKE_DEVICE_LIST}
        if path == "/router/api/v1/device/state":
            return {
                "payload": {
                    "capabilities": [
                        {"instance": "online", "state": {"value": True}},
                        {"instance": "powerSwitch", "state": {"value": 1}},
                        {"instance": "workMode", "state": {"value": {"workMode": 1, "modeValue": 2}}},
                    ]
                }
            }
        raise AssertionError(f"unexpected path {path}")

    monkeypatch.setattr(web_app, "_govee_cloud_request", fake_request)
    client = _client(tmp_path)

    card = client.get("/api/humidifiers").json()["humidifiers"][0]

    assert card["status"] == "configured"
    assert card["controllable"] is True
    assert card["is_on"] is True
    assert card["mist_level"] == 2
    assert card["capabilities"] == {"power": True, "mist_level": {"min": 1, "max": 3}}


def test_humidifiers_endpoint_serves_cache_when_cloud_unreachable(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GOVEE_API_KEY", "test-key")
    # With the cloud down no device entry can be matched, so the runtime-state
    # key falls back to the humidifier name (see _humidifier_runtime_key).
    web_app.HUMIDIFIER_RUNTIME_STATE["Bedroom Humidifier"] = {"is_on": True, "mist_level": 1}

    def fake_request(path, payload=None):
        raise OSError("rate limited")

    monkeypatch.setattr(web_app, "_govee_cloud_request", fake_request)
    client = _client(tmp_path)

    card = client.get("/api/humidifiers").json()["humidifiers"][0]

    assert card["status"] == "cloud_unreachable"
    assert card["controllable"] is False
    assert card["is_on"] is True  # served from cache


def test_cached_state_survives_cloud_outage_after_successful_poll(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GOVEE_API_KEY", "test-key")
    healthy = True

    def fake_request(path, payload=None):
        if not healthy:
            raise OSError("rate limited")
        if path == "/router/api/v1/user/devices":
            return {"code": 200, "data": FAKE_DEVICE_LIST}
        if path == "/router/api/v1/device/state":
            return {
                "payload": {
                    "capabilities": [
                        {"instance": "powerSwitch", "state": {"value": 1}},
                        {"instance": "workMode", "state": {"value": {"workMode": 1, "modeValue": 2}}},
                    ]
                }
            }
        raise AssertionError(f"unexpected path {path}")

    monkeypatch.setattr(web_app, "_govee_cloud_request", fake_request)
    client = _client(tmp_path)

    first = client.get("/api/humidifiers").json()["humidifiers"][0]
    assert first["status"] == "configured"
    assert first["is_on"] is True

    healthy = False
    web_app._GOVEE_CLOUD_CACHE.update({"devices": None, "fetched": 0.0})  # expire device-list cache

    second = client.get("/api/humidifiers").json()["humidifiers"][0]
    assert second["status"] == "cloud_unreachable"
    assert second["is_on"] is True  # last known state survives the outage
    assert second["mist_level"] == 2


def _healthy_cloud(monkeypatch, control_log):
    monkeypatch.setenv("GOVEE_API_KEY", "test-key")

    def fake_request(path, payload=None):
        if path == "/router/api/v1/user/devices":
            return {"code": 200, "data": FAKE_DEVICE_LIST}
        if path == "/router/api/v1/device/control":
            control_log.append(payload["payload"]["capability"])
            return {"code": 200}
        if path == "/router/api/v1/device/state":
            return {"payload": {"capabilities": []}}
        raise AssertionError(f"unexpected path {path}")

    monkeypatch.setattr(web_app, "_govee_cloud_request", fake_request)


def test_humidifier_on_off_commands(tmp_path: Path, monkeypatch) -> None:
    control_log = []
    _healthy_cloud(monkeypatch, control_log)
    client = _client(tmp_path)

    assert client.post("/api/humidifiers/Bedroom%20Humidifier/commands/on").status_code == 200
    assert client.post("/api/humidifiers/Bedroom%20Humidifier/commands/off").status_code == 200

    assert control_log == [
        {"type": "devices.capabilities.on_off", "instance": "powerSwitch", "value": 1},
        {"type": "devices.capabilities.on_off", "instance": "powerSwitch", "value": 0},
    ]


def test_humidifier_mist_level_clamped_to_reported_range(tmp_path: Path, monkeypatch) -> None:
    control_log = []
    _healthy_cloud(monkeypatch, control_log)
    client = _client(tmp_path)

    response = client.post(
        "/api/humidifiers/Bedroom%20Humidifier/commands/mist_level", json={"level": 99}
    )

    assert response.status_code == 200
    # FAKE_DEVICE_LIST reports gearMode range 1-3; workMode value 1 is gearMode.
    assert control_log == [
        {
            "type": "devices.capabilities.work_mode",
            "instance": "workMode",
            "value": {"workMode": 1, "modeValue": 3},
        }
    ]


def test_humidifier_command_error_paths(tmp_path: Path, monkeypatch) -> None:
    control_log = []
    _healthy_cloud(monkeypatch, control_log)
    client = _client(tmp_path)

    assert client.post("/api/humidifiers/Nope/commands/on").status_code == 404
    assert client.post("/api/humidifiers/Bedroom%20Humidifier/commands/dance").status_code == 400
    assert (
        client.post("/api/humidifiers/Bedroom%20Humidifier/commands/mist_level", json={}).status_code
        == 400
    )

    monkeypatch.delenv("GOVEE_API_KEY")
    assert client.post("/api/humidifiers/Bedroom%20Humidifier/commands/on").status_code == 503


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML = PROJECT_ROOT / "src" / "python" / "web_static" / "index.html"
APP_JS = PROJECT_ROOT / "src" / "python" / "web_static" / "app.js"


def test_humidifier_view_exists_in_sidebar_and_panels() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'data-view="humidifier"' in html
    assert 'id="humidifierCount"' in html
    assert 'data-view-panel="humidifier"' in html
    assert 'id="humidifierGrid"' in html


def test_app_js_wires_humidifier_api() -> None:
    js = APP_JS.read_text(encoding="utf-8")

    assert '"/api/humidifiers"' in js
    assert "data-humidifier-command" in js
    assert "data-humidifier-mist" in js
    assert "loadHumidifiers()" in js


def test_load_humidifiers_tolerates_null_sections(tmp_path: Path) -> None:
    null_section = tmp_path / "null_section.yaml"
    null_section.write_text("humidifiers:\n", encoding="utf-8")
    assert _load_humidifiers(null_section) == []

    null_devices = tmp_path / "null_devices.yaml"
    null_devices.write_text("humidifiers:\n  devices:\n", encoding="utf-8")
    assert _load_humidifiers(null_devices) == []
