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
    _match_govee_thermometer,
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


# A device that also advertises the built-in night light (toggle/brightness/colour).
NIGHTLIGHT_ENTRY = {
    "sku": "H7140",
    "device": "AA:BB:CC:DD:EE:FF:11:22",
    "capabilities": [
        {"type": "devices.capabilities.on_off", "instance": "powerSwitch"},
        {"type": "devices.capabilities.toggle", "instance": "nightlightToggle"},
        {
            "type": "devices.capabilities.range",
            "instance": "brightness",
            "parameters": {"range": {"min": 1, "max": 100}},
        },
        {"type": "devices.capabilities.color_setting", "instance": "colorRgb"},
        {
            "type": "devices.capabilities.mode",
            "instance": "nightlightScene",
            "parameters": {"options": [
                {"name": "Forest", "value": 1},
                {"name": "Ocean", "value": 2},
                {"name": "Sleep", "value": 5},
            ]},
        },
    ],
}


def test_nightlight_caps_detected_from_device() -> None:
    caps = web_app._govee_nightlight_caps(NIGHTLIGHT_ENTRY)
    assert caps["toggle"]["instance"] == "nightlightToggle"
    assert caps["color"]["instance"] == "colorRgb"
    assert caps["brightness"] == {
        "type": "devices.capabilities.range",
        "instance": "brightness",
        "min": 1,
        "max": 100,
    }
    # A device without a night light reports nothing.
    assert web_app._govee_nightlight_caps(FAKE_DEVICE_LIST[0]) == {}


def test_rgb_int_from_body() -> None:
    assert web_app._rgb_int_from_body({"red": 255, "green": 0, "blue": 0}) == 0xFF0000
    assert web_app._rgb_int_from_body({"r": 0, "g": 255, "b": 0}) == 0x00FF00
    assert web_app._rgb_int_from_body({"value": 0x123456}) == 0x123456
    assert web_app._rgb_int_from_body({"value": 99999999}) == 0xFFFFFF


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
    assert card["capabilities"] == {
        "power": True,
        "mist_level": {"min": 1, "max": 3},
        "nightlight": None,
    }


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


def _nightlight_cloud(monkeypatch, control_log):
    monkeypatch.setenv("GOVEE_API_KEY", "test-key")

    def fake_request(path, payload=None):
        if path == "/router/api/v1/user/devices":
            return {"code": 200, "data": [NIGHTLIGHT_ENTRY]}
        if path == "/router/api/v1/device/control":
            control_log.append(payload["payload"]["capability"])
            return {"code": 200}
        if path == "/router/api/v1/device/state":
            return {"payload": {"capabilities": []}}
        raise AssertionError(f"unexpected path {path}")

    monkeypatch.setattr(web_app, "_govee_cloud_request", fake_request)


def test_humidifier_nightlight_commands(tmp_path: Path, monkeypatch) -> None:
    control_log = []
    _nightlight_cloud(monkeypatch, control_log)
    client = _client(tmp_path)

    base = "/api/humidifiers/Bedroom%20Humidifier/commands/"
    assert client.post(base + "nightlight_on").status_code == 200
    assert client.post(base + "nightlight_off").status_code == 200
    assert client.post(base + "nightlight_brightness", json={"level": 250}).status_code == 200
    assert client.post(base + "nightlight_color", json={"red": 255, "green": 0, "blue": 128}).status_code == 200
    assert client.post(base + "nightlight_scene", json={"value": 2}).status_code == 200

    assert control_log == [
        {"type": "devices.capabilities.toggle", "instance": "nightlightToggle", "value": 1},
        {"type": "devices.capabilities.toggle", "instance": "nightlightToggle", "value": 0},
        {"type": "devices.capabilities.range", "instance": "brightness", "value": 100},
        {"type": "devices.capabilities.color_setting", "instance": "colorRgb", "value": 0xFF0080},
        {"type": "devices.capabilities.mode", "instance": "nightlightScene", "value": 2},
    ]

    # An unknown scene value is rejected before reaching the cloud.
    assert client.post(base + "nightlight_scene", json={"value": 99}).status_code == 400

    # The card surfaces the night-light capabilities so the dashboard renders controls.
    card = client.get("/api/humidifiers").json()["humidifiers"][0]
    assert card["capabilities"]["nightlight"] == {
        "toggle": True,
        "color": True,
        "brightness": {"min": 1, "max": 100},
        "scene": [
            {"name": "Forest", "value": 1},
            {"name": "Ocean", "value": 2},
            {"name": "Sleep", "value": 5},
        ],
    }


def test_humidifier_nightlight_rejected_without_capability(tmp_path: Path, monkeypatch) -> None:
    control_log = []
    _healthy_cloud(monkeypatch, control_log)  # FAKE_DEVICE_LIST has no night light
    client = _client(tmp_path)

    resp = client.post("/api/humidifiers/Bedroom%20Humidifier/commands/nightlight_on")
    assert resp.status_code == 400
    assert control_log == []


# A linked Govee thermometer (H5179) supplies ambient humidity + temperature.
THERMOMETER_ENTRY = {
    "sku": "H5179",
    "device": "31:9E:E7:76:46:06:6C:49",
    "deviceName": "Govee Thermometer",
    "capabilities": [
        {"type": "devices.capabilities.property", "instance": "sensorHumidity"},
        {"type": "devices.capabilities.property", "instance": "sensorTemperature"},
    ],
}


CO2_MONITOR_ENTRY = {
    "sku": "H5140",
    "device": "AA:00:11:22:33:44:55:66",
    "deviceName": "Smart CO2 Monitor",
    "capabilities": [
        {"type": "devices.capabilities.property", "instance": "carbonDioxideConcentration"},
        {"type": "devices.capabilities.property", "instance": "sensorTemperature"},
        {"type": "devices.capabilities.property", "instance": "sensorHumidity"},
    ],
}


def test_match_thermometer_prefers_unique_sensor() -> None:
    devices = [FAKE_DEVICE_LIST[0], THERMOMETER_ENTRY]
    match = _match_govee_thermometer(_definition(device_id="replace_me"), devices)
    assert match["sku"] == "H5179"
    # No ambient-humidity sensor on the account -> no link.
    assert _match_govee_thermometer(_definition(), [FAKE_DEVICE_LIST[0]]) is None


def test_match_thermometer_prefers_thermo_hygrometer_over_co2_monitor() -> None:
    # Both the thermometer and the CO2 monitor report sensorHumidity; the plain
    # thermo-hygrometer wins so the humidifier links to the right device.
    devices = [FAKE_DEVICE_LIST[0], CO2_MONITOR_ENTRY, THERMOMETER_ENTRY]
    match = _match_govee_thermometer(_definition(), devices)
    assert match["sku"] == "H5179"


def test_match_thermometer_explicit_model_wins() -> None:
    devices = [FAKE_DEVICE_LIST[0], CO2_MONITOR_ENTRY, THERMOMETER_ENTRY]
    # An explicit thermometer_model overrides the auto-detect heuristic.
    explicit = HumidifierDefinition(
        name="Bedroom Humidifier", provider="govee_cloud", model="H7140", room="Bedroom",
        device_id=None, thermometer_model="H5140",
    )
    assert _match_govee_thermometer(explicit, devices)["sku"] == "H5140"


def test_humidifier_card_merges_linked_thermometer(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GOVEE_API_KEY", "test-key")
    devices = [FAKE_DEVICE_LIST[0], THERMOMETER_ENTRY]

    def fake_request(path, payload=None):
        if path == "/router/api/v1/user/devices":
            return {"code": 200, "data": devices}
        if path == "/router/api/v1/device/state":
            device = payload["payload"]["device"]
            if device == THERMOMETER_ENTRY["device"]:
                return {"payload": {"capabilities": [
                    {"instance": "sensorHumidity", "state": {"value": 56.7}},
                    {"instance": "sensorTemperature", "state": {"value": 84.2}},  # °F
                ]}}
            return {"payload": {"capabilities": [
                {"instance": "powerSwitch", "state": {"value": 1}},
                {"instance": "workMode", "state": {"value": {"workMode": 1, "modeValue": 2}}},
            ]}}
        raise AssertionError(f"unexpected path {path}")

    monkeypatch.setattr(web_app, "_govee_cloud_request", fake_request)
    client = _client(tmp_path)

    card = client.get("/api/humidifiers").json()["humidifiers"][0]
    assert card["humidity"] == 57  # round(56.7)
    assert card["temperature"] == 29.0  # (84.2 - 32) * 5/9, defaults to Celsius
    assert card["temperature_unit"] == "C"
    assert card["thermometer"] == "Govee Thermometer"


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


def test_humidifier_view_exists_as_a_panel() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")

    # The #humidifierCount badge lived on the sidebar item, removed with the
    # other device groups; the panel and its grid remain.
    assert 'id="humidifierCount"' not in html
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


def _humidity_sensor(sku: str, device: str, instances: list[str] | None = None) -> dict:
    """Minimal Govee device entry reporting the given capability instances.

    Defaults to a plain thermo-hygrometer (humidity + temperature, no CO2).
    Pass an explicit instances list (e.g. including "carbonDioxideConcentration")
    to build a CO2 combo monitor like the real H5140.
    """
    if instances is None:
        instances = ["sensorHumidity", "sensorTemperature"]
    return {
        "sku": sku,
        "device": device,
        "capabilities": [{"type": "devices.capabilities.property", "instance": i} for i in instances],
    }


def test_thermometer_fallback_is_ambiguous_with_two_non_co2_sensors() -> None:
    """Hypothetical configuration, NOT the current account state: two humidity
    sensors where NEITHER reports carbonDioxideConcentration. The real account
    only has one plain thermo-hygrometer (H5179) plus one CO2 combo monitor
    (H5140) — see test_co2_tiebreak_resolves_real_account_pair, which proves
    that real pair resolves fine. But if a second *plain* humidity sensor
    were ever added, the CO2 tie-break has nothing to exclude, both sensors
    stay in the running, and the 'sole sensor' fallback returns None. This
    documents why pinning thermometer_device_id is the robust choice."""
    devices = [_humidity_sensor("H5179", "AA:BB"), _humidity_sensor("H5100", "CC:DD")]
    unpinned = HumidifierDefinition(
        name="Bedroom Humidifier", provider="govee_cloud", model="H7140",
        room="Bedroom", device_id="replace_me",
    )

    assert _match_govee_thermometer(unpinned, devices) is None


def test_pinned_thermometer_device_id_is_unambiguous() -> None:
    devices = [_humidity_sensor("H5179", "AA:BB"), _humidity_sensor("H5100", "CC:DD")]
    pinned = HumidifierDefinition(
        name="Bedroom Humidifier", provider="govee_cloud", model="H7140",
        room="Bedroom", device_id="replace_me", thermometer_device_id="AA:BB",
    )

    assert _match_govee_thermometer(pinned, devices)["device"] == "AA:BB"


def test_pinned_thermometer_model_is_unambiguous() -> None:
    devices = [_humidity_sensor("H5179", "AA:BB"), _humidity_sensor("H5100", "CC:DD")]
    pinned = HumidifierDefinition(
        name="Bedroom Humidifier", provider="govee_cloud", model="H7140",
        room="Bedroom", device_id="replace_me", thermometer_model="H5179",
    )

    assert _match_govee_thermometer(pinned, devices)["device"] == "AA:BB"


def test_co2_tiebreak_resolves_real_account_pair() -> None:
    """This is the shape the real account actually has: one plain
    thermo-hygrometer (H5179) and one H5140 -- Govee's "Smart CO2 Monitor",
    which is a combo device reporting sensorHumidity AND sensorTemperature
    AND carbonDioxideConcentration. The existing tie-break in
    _match_govee_thermometer excludes sensors that report CO2 from the
    ambiguous set, so an UNPINNED humidifier still resolves correctly to the
    H5179 even with the H5140 present on the account. There is no live
    regression for this configuration; this test guards the tie-break that
    prevents one against future removal."""
    h5179 = _humidity_sensor("H5179", "AA:BB")
    h5140 = _humidity_sensor(
        "H5140", "CC:DD", ["sensorHumidity", "sensorTemperature", "carbonDioxideConcentration"]
    )
    devices = [h5179, h5140]
    unpinned = HumidifierDefinition(
        name="Bedroom Humidifier", provider="govee_cloud", model="H7140",
        room="Bedroom", device_id="replace_me",
    )

    match = _match_govee_thermometer(unpinned, devices)

    assert match is not None
    assert match["device"] == "AA:BB"
