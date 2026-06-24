from pathlib import Path

from fastapi.testclient import TestClient

from src.python import web_app as web_app_module
from src.python.tplink_switch import SwitchState
from src.python.web_app import TuyaDefinition, _govee_ble_command_bytes, _rtsp_url_from_config, _tuya_card, _tuya_direct_sensor_supplements, create_app


class FakeController:
    def __init__(self) -> None:
        self.commands: list[tuple[str, str]] = []

    async def status(self, switch):
        return SwitchState(
            name=switch.name,
            host=switch.host,
            is_on=switch.host.endswith(".61"),
            alias=switch.name,
            model=switch.model,
        )

    async def turn_on(self, switch):
        self.commands.append(("on", switch.host))
        return SwitchState(name=switch.name, host=switch.host, is_on=True, alias=switch.name, model=switch.model)

    async def turn_off(self, switch):
        self.commands.append(("off", switch.host))
        return SwitchState(name=switch.name, host=switch.host, is_on=False, alias=switch.name, model=switch.model)

    async def toggle(self, switch):
        self.commands.append(("toggle", switch.host))
        return SwitchState(name=switch.name, host=switch.host, is_on=True, alias=switch.name, model=switch.model)


def _write_discovery(path: Path) -> None:
    path.write_text(
        """
{
  "count": 2,
  "switches": [
    {
      "alias": "Family room switch",
      "device_type": "DeviceType.Dimmer",
      "host": "192.168.0.61",
      "is_on": false,
      "model": "HS220",
      "name": "Family room switch"
    },
    {
      "alias": "Living room switch 2",
      "device_type": "DeviceType.WallSwitch",
      "host": "192.168.0.73",
      "is_on": true,
      "model": "HS200",
      "name": "Living room switch 2"
    },
    {
      "alias": "Office plug",
      "device_type": "DeviceType.Plug",
      "host": "192.168.0.51",
      "is_on": true,
      "model": "HS103",
      "name": "Office plug"
    }
  ]
}
""",
        encoding="utf-8",
    )


def _write_config(path: Path) -> None:
    path.write_text(
        """
tplink:
  cameras:
    - name: Front door camera
      host: 192.168.0.201
      model: Tapo C120
      room: Front Door
      snapshot_url: http://192.168.0.201/snapshot.jpg
    - name: Garage camera
      host: 192.168.0.202
      model: Tapo C210
      room: Garage
      stream_url: rtsp://camera-user:camera-password@192.168.0.202:554/stream1
media_gateway:
  go2rtc_url: http://192.168.0.10:1984
""",
        encoding="utf-8",
    )


def _write_env_config(path: Path) -> None:
    path.write_text(
        """
tplink:
  cameras:
    - name: Family room camera
      host: 192.168.0.24
      model: Tapo C200
      room: Family Room
      username_env: TAPO_CAMERA_USERNAME
      password_env: TAPO_CAMERA_PASSWORD
      stream_path: /stream1
      stream_name: family_room_camera
media_gateway:
  go2rtc_url: http://192.168.0.10:1984
""",
        encoding="utf-8",
    )


def _write_camera_missing_secret_config(path: Path) -> None:
    path.write_text(
        """
cameras:
  - name: Wyze camera
    provider: wyze
    host: 192.168.0.95
    model: Wyze RTSP
    room: Home
    stream_name: wyze_camera
    go2rtc_url: http://192.168.0.10:1984
    username_env: WYZE_RTSP_USERNAME
    password_env: WYZE_RTSP_PASSWORD
    rtsp_scheme: rtsps
    rtsp_port: 322
    stream_path: /stream0
""",
        encoding="utf-8",
    )


def _write_go2rtc_disabled_camera_config(path: Path) -> None:
    path.write_text(
        """
media_gateway:
  go2rtc_url: http://192.168.0.10:1984
cameras:
  - name: Chortau camera
    provider: chortau
    host: 192.168.0.191
    model: Hipcam RealServer
    room: Home
    stream_name: chortau_camera_2
    stream_url: rtsp://192.168.0.191:554/11
    go2rtc_enabled: false
""",
        encoding="utf-8",
    )


def _write_tuya_config(path: Path) -> None:
    path.write_text(
        """
tuya:
  devices:
    - name: Hallway motion sensor
      device_id: tuya-sensor-1
      host: 192.168.0.210
      local_key_env: TUYA_SENSOR_KEY
      category: tuya_sensor
      room: Hallway
      model: Motion
      dps:
        motion: "1"
        battery: "4"
    - name: Porch outlet
      device_id: tuya-switch-1
      host: 192.168.0.211
      local_key_env: TUYA_SWITCH_KEY
      category: tuya_switch
      room: Porch
      model: Outdoor Plug
      power_dp: "1"
""",
        encoding="utf-8",
    )


def _write_tuya_camera_config(path: Path) -> None:
    path.write_text(
        """
tuya:
  devices:
    - name: Living Room Camera
      device_id: tuya-camera-1
      host: 192.168.0.45
      local_key_env: TUYA_CAMERA_KEY
      category: tuya_camera
      room: Living Room
      model: Smart Camera
""",
        encoding="utf-8",
    )


def _write_cloud_linked_tuya_config(path: Path) -> None:
    path.write_text(
        """
tuya:
  devices:
    - name: Door sensor
      device_id: tuya-door-1
      local_key_env: TUYA_DOOR_KEY
      category: tuya_sensor
      room: Hallway
      model: Door Sensor
""",
        encoding="utf-8",
    )


def _write_weather_config(path: Path) -> None:
    path.write_text(
        """
weather:
  name: Home
  latitude: 49.2827
  longitude: -123.1207
  timezone: America/Vancouver
  temperature_unit: fahrenheit
""",
        encoding="utf-8",
    )


def _write_ecobee_config(path: Path) -> None:
    path.write_text(
        """
ecobee:
  temperature_unit: celsius
  thermostats:
    - name: Main thermostat
      thermostat_id: ecobee-1
      room: Hallway
""",
        encoding="utf-8",
    )


def _write_home_assistant_config(path: Path) -> None:
    path.write_text(
        """
home_assistant:
  base_url: http://127.0.0.1:8123
  token_env: HOME_ASSISTANT_TOKEN
  include_domains:
    - climate
    - light
    - sensor
""",
        encoding="utf-8",
    )


def test_devices_endpoint_loads_discovered_switches_and_plugs(tmp_path: Path) -> None:
    discovery = tmp_path / "tplink_switches.json"
    _write_discovery(discovery)
    client = TestClient(create_app(discovery_path=discovery, controller=FakeController()))

    response = client.get("/api/devices")

    assert response.status_code == 200
    assert response.json()["devices"] == [
        {
            "id": "192.168.0.61",
            "name": "Family room switch",
            "host": "192.168.0.61",
            "model": "HS220",
            "type": "Dimmer",
            "category": "light_switch",
            "room": "Family Room",
            "is_on": True,
        },
        {
            "id": "192.168.0.73",
            "name": "Living room switch 2",
            "host": "192.168.0.73",
            "model": "HS200",
            "type": "WallSwitch",
            "category": "light_switch",
            "room": "Living Room",
            "is_on": False,
        },
        {
            "id": "192.168.0.51",
            "name": "Office plug",
            "host": "192.168.0.51",
            "model": "HS103",
            "type": "Plug",
            "category": "smart_plug",
            "room": "Office Plug",
            "is_on": False,
        },
    ]


def test_command_endpoint_controls_switch_by_host(tmp_path: Path) -> None:
    discovery = tmp_path / "tplink_switches.json"
    _write_discovery(discovery)
    controller = FakeController()
    client = TestClient(create_app(discovery_path=discovery, controller=controller))

    response = client.post("/api/devices/192.168.0.61/commands/on")

    assert response.status_code == 200
    assert response.json()["is_on"] is True
    assert controller.commands == [("on", "192.168.0.61")]


def test_cameras_endpoint_loads_configured_tplink_cameras(tmp_path: Path) -> None:
    discovery = tmp_path / "tplink_switches.json"
    config = tmp_path / "devices.local.yaml"
    _write_discovery(discovery)
    _write_config(config)
    client = TestClient(
        create_app(discovery_path=discovery, config_path=config, controller=FakeController(), check_camera_ports=False)
    )

    response = client.get("/api/cameras")

    assert response.status_code == 200
    assert response.json()["cameras"] == [
        {
            "id": "192.168.0.201",
            "name": "Front door camera",
            "host": "192.168.0.201",
            "provider": "tplink",
            "model": "Tapo C120",
            "room": "Front Door",
            "snapshot_url": "http://192.168.0.201/snapshot.jpg",
            "stream_url": None,
            "view_url": "http://192.168.0.201/snapshot.jpg",
            "view_type": "snapshot",
            "requires_proxy": False,
            "status": "ready",
            "status_detail": "Camera source is configured.",
            "stream_name": "front_door_camera",
            "webrtc_url": "http://192.168.0.10:1984/webrtc.html?src=front_door_camera",
            "hls_url": "http://192.168.0.10:1984/stream.html?src=front_door_camera&mode=hls",
        },
        {
            "id": "192.168.0.202",
            "name": "Garage camera",
            "host": "192.168.0.202",
            "provider": "tplink",
            "model": "Tapo C210",
            "room": "Garage",
            "snapshot_url": None,
            "stream_url": None,
            "view_url": "http://192.168.0.10:1984/webrtc.html?src=garage_camera",
            "view_type": "webrtc",
            "requires_proxy": False,
            "status": "ready",
            "status_detail": "Camera source is configured.",
            "stream_name": "garage_camera",
            "webrtc_url": "http://192.168.0.10:1984/webrtc.html?src=garage_camera",
            "hls_url": "http://192.168.0.10:1984/stream.html?src=garage_camera&mode=hls",
        },
    ]


def test_camera_mjpeg_endpoint_rejects_unknown_camera(tmp_path: Path) -> None:
    discovery = tmp_path / "tplink_switches.json"
    config = tmp_path / "devices.local.yaml"
    _write_discovery(discovery)
    _write_config(config)
    client = TestClient(
        create_app(discovery_path=discovery, config_path=config, controller=FakeController(), check_camera_ports=False)
    )

    response = client.get("/api/cameras/192.168.0.250/mjpeg")

    assert response.status_code == 404


def test_camera_patch_endpoint_renames_configured_camera(tmp_path: Path) -> None:
    discovery = tmp_path / "tplink_switches.json"
    config = tmp_path / "devices.local.yaml"
    _write_discovery(discovery)
    _write_config(config)
    client = TestClient(
        create_app(discovery_path=discovery, config_path=config, controller=FakeController(), check_camera_ports=False)
    )

    response = client.patch("/api/cameras/192.168.0.201", json={"name": "Front Porch"})

    assert response.status_code == 200
    assert response.json()["name"] == "Front Porch"
    assert "name: Front Porch" in config.read_text(encoding="utf-8")
    assert "stream_name:" not in response.text


def test_camera_patch_endpoint_renames_tuya_camera(tmp_path: Path, monkeypatch) -> None:
    discovery = tmp_path / "tplink_switches.json"
    config = tmp_path / "devices.local.yaml"
    _write_discovery(discovery)
    _write_tuya_camera_config(config)
    monkeypatch.setenv("TUYA_CAMERA_KEY", "camera-secret")
    client = TestClient(
        create_app(discovery_path=discovery, config_path=config, controller=FakeController(), check_camera_ports=False)
    )

    response = client.patch("/api/cameras/tuya-camera-1", json={"name": "Living Room View"})

    assert response.status_code == 200
    assert response.json()["name"] == "Living Room View"
    assert "name: Living Room View" in config.read_text(encoding="utf-8")
    assert "camera-secret" not in response.text


def test_camera_endpoint_builds_rtsp_stream_from_env_without_exposing_secret(tmp_path: Path, monkeypatch) -> None:
    discovery = tmp_path / "tplink_switches.json"
    config = tmp_path / "devices.local.yaml"
    _write_discovery(discovery)
    _write_env_config(config)
    monkeypatch.setenv("TAPO_CAMERA_USERNAME", "camera user")
    monkeypatch.setenv("TAPO_CAMERA_PASSWORD", "camera/password")
    client = TestClient(
        create_app(discovery_path=discovery, config_path=config, controller=FakeController(), check_camera_ports=False)
    )

    response = client.get("/api/cameras")

    assert response.status_code == 200
    assert response.json()["cameras"] == [
        {
            "id": "192.168.0.24",
            "name": "Family room camera",
            "host": "192.168.0.24",
            "provider": "tplink",
            "model": "Tapo C200",
            "room": "Family Room",
            "snapshot_url": None,
            "stream_url": None,
            "view_url": "http://192.168.0.10:1984/webrtc.html?src=family_room_camera",
            "view_type": "webrtc",
            "requires_proxy": False,
            "status": "ready",
            "status_detail": "Camera source is configured.",
            "stream_name": "family_room_camera",
            "webrtc_url": "http://192.168.0.10:1984/webrtc.html?src=family_room_camera",
            "hls_url": "http://192.168.0.10:1984/stream.html?src=family_room_camera&mode=hls",
        }
    ]


def test_camera_endpoint_marks_go2rtc_camera_not_configured_without_rtsp_secret(tmp_path: Path) -> None:
    discovery = tmp_path / "tplink_switches.json"
    config = tmp_path / "devices.local.yaml"
    _write_discovery(discovery)
    _write_camera_missing_secret_config(config)
    client = TestClient(
        create_app(discovery_path=discovery, config_path=config, controller=FakeController(), check_camera_ports=False)
    )

    response = client.get("/api/cameras")

    assert response.status_code == 200
    assert response.json()["cameras"][0]["provider"] == "wyze"
    assert response.json()["cameras"][0]["view_url"] is None
    assert response.json()["cameras"][0]["view_type"] == "unknown"
    assert response.json()["cameras"][0]["status"] == "not_configured"


def test_rtsp_builder_supports_wyze_secure_rtsp(monkeypatch) -> None:
    monkeypatch.setenv("WYZE_RTSP_USERNAME", "wyze user")
    monkeypatch.setenv("WYZE_RTSP_PASSWORD", "wyze/password")

    url = _rtsp_url_from_config(
        {
            "host": "192.168.0.95",
            "username_env": "WYZE_RTSP_USERNAME",
            "password_env": "WYZE_RTSP_PASSWORD",
            "rtsp_scheme": "rtsps",
            "rtsp_port": 322,
            "stream_path": "/stream0",
        }
    )

    assert url == "rtsps://wyze%20user:wyze%2Fpassword@192.168.0.95:322/stream0"


def test_camera_can_disable_global_go2rtc_gateway(tmp_path: Path) -> None:
    discovery = tmp_path / "tplink_switches.json"
    config = tmp_path / "devices.local.yaml"
    _write_discovery(discovery)
    _write_go2rtc_disabled_camera_config(config)
    client = TestClient(
        create_app(discovery_path=discovery, config_path=config, controller=FakeController(), check_camera_ports=False)
    )

    response = client.get("/api/cameras")

    assert response.status_code == 200
    camera = response.json()["cameras"][0]
    assert camera["view_type"] == "mjpeg"
    assert camera["view_url"] == "/api/cameras/192.168.0.191/mjpeg"
    assert camera["webrtc_url"] is None


def test_tuya_endpoint_loads_configured_devices_without_exposing_keys(tmp_path: Path, monkeypatch) -> None:
    discovery = tmp_path / "tplink_switches.json"
    config = tmp_path / "devices.local.yaml"
    _write_discovery(discovery)
    _write_tuya_config(config)
    monkeypatch.setenv("TUYA_SENSOR_KEY", "sensor-secret")
    monkeypatch.setenv("TUYA_SWITCH_KEY", "switch-secret")
    client = TestClient(create_app(discovery_path=discovery, config_path=config, controller=FakeController()))

    response = client.get("/api/tuya/devices")

    assert response.status_code == 200
    payload = response.json()
    assert payload["devices"] == [
        {
            "id": "tuya-sensor-1",
            "name": "Hallway motion sensor",
            "host": "192.168.0.210",
            "model": "Motion",
            "type": "Tuya Sensor",
            "category": "tuya_sensor",
            "room": "Hallway",
            "is_on": None,
            "online": False,
            "status": "configured",
            "source": None,
            "values": {},
            "controllable": False,
        },
        {
            "id": "tuya-switch-1",
            "name": "Porch outlet",
            "host": "192.168.0.211",
            "model": "Outdoor Plug",
            "type": "Tuya Switch",
            "category": "tuya_switch",
            "room": "Porch",
            "is_on": None,
            "online": False,
            "status": "configured",
            "source": None,
            "values": {},
            "controllable": True,
        },
    ]
    assert "sensor-secret" not in response.text
    assert "switch-secret" not in response.text


def test_tuya_endpoint_marks_keyed_device_without_host_as_cloud_linked(tmp_path: Path, monkeypatch) -> None:
    discovery = tmp_path / "tplink_switches.json"
    config = tmp_path / "devices.local.yaml"
    _write_discovery(discovery)
    _write_cloud_linked_tuya_config(config)
    monkeypatch.setenv("TUYA_DOOR_KEY", "door-secret")
    client = TestClient(create_app(discovery_path=discovery, config_path=config, controller=FakeController()))

    response = client.get("/api/tuya/devices")

    assert response.status_code == 200
    assert response.json()["devices"][0]["status"] == "cloud_linked"
    assert response.json()["devices"][0]["controllable"] is False
    assert response.json()["devices"][0]["source"] is None
    assert "door-secret" not in response.text


def test_tuya_card_uses_cloud_power_code_for_status_and_control() -> None:
    device = TuyaDefinition(
        name="Cabinet LED",
        device_id="tuya-light-1",
        host=None,
        local_key="secret",
        version=3.4,
        category="tuya_device",
        room="Cabinet",
        model="Light",
        power_dp=None,
        cloud_power_code="switch_led",
        dps={},
    )

    card = _tuya_card(device, {"result": [{"code": "switch_led", "value": True}]}, "cloud")

    assert card["is_on"] is True
    assert card["status"] == "online"
    assert card["source"] == "cloud"
    assert card["controllable"] is True


def test_weather_endpoint_returns_not_configured_without_location(tmp_path: Path) -> None:
    discovery = tmp_path / "tplink_switches.json"
    config = tmp_path / "devices.local.yaml"
    _write_discovery(discovery)
    config.write_text("{}", encoding="utf-8")
    client = TestClient(create_app(discovery_path=discovery, config_path=config, controller=FakeController()))

    response = client.get("/api/weather")

    assert response.status_code == 200
    assert response.json()["status"] == "not_configured"


def test_weather_endpoint_returns_configured_weather(tmp_path: Path, monkeypatch) -> None:
    discovery = tmp_path / "tplink_switches.json"
    config = tmp_path / "devices.local.yaml"
    _write_discovery(discovery)
    _write_weather_config(config)

    def fake_weather_payload(weather_config):
        return {
            "status": "ok",
            "source": "Open-Meteo",
            "location": weather_config.name,
            "time": "2026-06-11T10:00",
            "temperature": 72.4,
            "temperature_unit": "degF",
            "feels_like": 71.8,
            "humidity": 44,
            "wind_speed": 5.2,
            "wind_unit": "mp/h",
            "condition": "Clear",
            "weather_code": 0,
            "high": 78.0,
            "low": 58.0,
            "precipitation_probability": 10,
        }

    monkeypatch.setattr("src.python.web_app._weather_payload", fake_weather_payload)
    client = TestClient(create_app(discovery_path=discovery, config_path=config, controller=FakeController()))

    response = client.get("/api/weather")

    assert response.status_code == 200
    assert response.json()["temperature"] == 72.4
    assert response.json()["location"] == "Home"


def test_ecobee_endpoint_returns_not_configured_without_thermostats(tmp_path: Path) -> None:
    discovery = tmp_path / "tplink_switches.json"
    config = tmp_path / "devices.local.yaml"
    _write_discovery(discovery)
    config.write_text("{}", encoding="utf-8")
    client = TestClient(create_app(discovery_path=discovery, config_path=config, controller=FakeController()))

    response = client.get("/api/ecobee/thermostats")

    assert response.status_code == 200
    assert response.json()["status"] == "not_configured"
    assert response.json()["thermostats"] == []


def test_ecobee_endpoint_returns_setup_card_without_credentials(tmp_path: Path, monkeypatch) -> None:
    discovery = tmp_path / "tplink_switches.json"
    config = tmp_path / "devices.local.yaml"
    _write_discovery(discovery)
    _write_ecobee_config(config)
    monkeypatch.delenv("ECOBEE_CLIENT_ID", raising=False)
    client = TestClient(create_app(discovery_path=discovery, config_path=config, controller=FakeController()))

    response = client.get("/api/ecobee/thermostats")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "needs_auth"
    assert payload["thermostats"][0]["name"] == "Main thermostat"
    assert payload["thermostats"][0]["status"] == "needs_auth"


def test_ecobee_endpoint_uses_home_assistant_climate_when_direct_auth_missing(tmp_path: Path, monkeypatch) -> None:
    discovery = tmp_path / "tplink_switches.json"
    config = tmp_path / "devices.local.yaml"
    _write_discovery(discovery)
    _write_ecobee_config(config)
    monkeypatch.delenv("ECOBEE_CLIENT_ID", raising=False)
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN", "token")

    def fake_home_assistant_get(home_assistant_config, token, path):
        return [
            {
                "entity_id": "climate.my_ecobee",
                "state": "heat",
                "attributes": {
                    "friendly_name": "My ecobee",
                    "current_temperature": 25.8,
                    "temperature": 17.0,
                    "current_humidity": 49.0,
                    "hvac_action": "idle",
                    "preset_mode": "away",
                    "preset_modes": ["home", "away"],
                    "temperature_unit": "°C",
                },
            },
            {
                "entity_id": "select.my_ecobee_current_mode",
                "state": "away",
                "attributes": {
                    "friendly_name": "Current Mode",
                    "options": ["home", "away"],
                },
            },
        ]

    monkeypatch.setattr("src.python.web_app._home_assistant_get", fake_home_assistant_get)
    client = TestClient(create_app(discovery_path=discovery, config_path=config, controller=FakeController()))

    response = client.get("/api/ecobee/thermostats")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["source"] == "Home Assistant"
    assert payload["thermostats"][0]["name"] == "My ecobee"
    assert payload["thermostats"][0]["temperature"] == 25.8
    assert payload["thermostats"][0]["preset_entity_id"] == "select.my_ecobee_current_mode"
    assert payload["thermostats"][0]["preset_mode"] == "away"
    assert payload["thermostats"][0]["preset_modes"] == ["home", "away"]


def test_ecobee_endpoint_returns_live_thermostat_card(tmp_path: Path, monkeypatch) -> None:
    discovery = tmp_path / "tplink_switches.json"
    config = tmp_path / "devices.local.yaml"
    _write_discovery(discovery)
    _write_ecobee_config(config)
    monkeypatch.setenv("ECOBEE_CLIENT_ID", "client-id")

    def fake_ecobee_api_thermostats():
        return [
            {
                "identifier": "ecobee-1",
                "name": "Home",
                "equipmentStatus": "heatPump",
                "runtime": {
                    "actualTemperature": 715,
                    "actualHumidity": 43,
                    "desiredHeat": 690,
                    "desiredCool": 740,
                },
                "settings": {"hvacMode": "auto"},
            }
        ]

    monkeypatch.setattr("src.python.web_app._ecobee_api_thermostats", fake_ecobee_api_thermostats)
    client = TestClient(create_app(discovery_path=discovery, config_path=config, controller=FakeController()))

    response = client.get("/api/ecobee/thermostats")

    assert response.status_code == 200
    thermostat = response.json()["thermostats"][0]
    assert thermostat["status"] == "online"
    assert thermostat["temperature"] == 21.9
    assert thermostat["temperature_unit"] == "°C"
    assert thermostat["humidity"] == 43
    assert thermostat["hvac_mode"] == "auto"


def test_cameras_endpoint_includes_home_assistant_tuya_cameras(tmp_path: Path, monkeypatch) -> None:
    discovery = tmp_path / "tplink_switches.json"
    config = tmp_path / "devices.local.yaml"
    _write_discovery(discovery)
    _write_home_assistant_config(config)
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN", "token")

    def fake_home_assistant_get(home_assistant_config, token, path):
        assert token == "token"
        assert path == "/api/states"
        return [
            {
                "entity_id": "camera.living_room_camera",
                "state": "recording",
                "attributes": {"friendly_name": "Living Room Camera", "access_token": "camera-token"},
            },
            {
                "entity_id": "camera.zhi_neng_men_ling",
                "state": "idle",
                "attributes": {"friendly_name": "智能门铃", "access_token": "doorbell-token"},
            },
            {
                "entity_id": "sensor.zhi_neng_men_ling_battery",
                "state": "73",
                "attributes": {"friendly_name": "智能门铃 Battery"},
            },
        ]

    monkeypatch.setattr("src.python.web_app._home_assistant_get", fake_home_assistant_get)
    client = TestClient(create_app(discovery_path=discovery, config_path=config, controller=FakeController()))

    response = client.get("/api/cameras")

    assert response.status_code == 200
    cameras = response.json()["cameras"]
    assert [camera["id"] for camera in cameras] == ["camera.living_room_camera", "camera.zhi_neng_men_ling"]
    assert cameras[0]["provider"] == "home_assistant"
    assert cameras[0]["view_type"] == "mjpeg"
    assert cameras[0]["view_url"] == "/api/home-assistant/cameras/camera.living_room_camera/stream"
    assert cameras[1]["view_type"] == "doorbell"
    assert cameras[1]["battery"] == 73

def test_home_assistant_endpoint_requires_token(tmp_path: Path, monkeypatch) -> None:
    discovery = tmp_path / "tplink_switches.json"
    config = tmp_path / "devices.local.yaml"
    _write_discovery(discovery)
    _write_home_assistant_config(config)
    monkeypatch.delenv("HOME_ASSISTANT_TOKEN", raising=False)
    client = TestClient(create_app(discovery_path=discovery, config_path=config, controller=FakeController()))

    response = client.get("/api/home-assistant/entities")

    assert response.status_code == 200
    assert response.json()["status"] == "needs_auth"
    assert response.json()["entities"] == []


def test_home_assistant_endpoint_maps_climate_and_light_entities(tmp_path: Path, monkeypatch) -> None:
    discovery = tmp_path / "tplink_switches.json"
    config = tmp_path / "devices.local.yaml"
    _write_discovery(discovery)
    _write_home_assistant_config(config)
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN", "token")

    def fake_home_assistant_get(home_assistant_config, token, path):
        assert token == "token"
        assert path == "/api/states"
        return [
            {
                "entity_id": "climate.ecobee",
                "state": "heat_cool",
                "attributes": {
                    "friendly_name": "Ecobee",
                    "current_temperature": 21.5,
                    "temperature": 22,
                    "current_humidity": 44,
                    "hvac_action": "idle",
                    "preset_mode": "home",
                    "preset_modes": ["home", "away"],
                    "temperature_unit": "°C",
                },
            },
            {
                "entity_id": "light.family_room",
                "state": "on",
                "attributes": {"friendly_name": "Family Room Light"},
            },
            {
                "entity_id": "camera.front_door",
                "state": "idle",
                "attributes": {"friendly_name": "Front Door"},
            },
        ]

    monkeypatch.setattr("src.python.web_app._home_assistant_get", fake_home_assistant_get)
    client = TestClient(create_app(discovery_path=discovery, config_path=config, controller=FakeController()))

    response = client.get("/api/home-assistant/entities")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert [entity["entity_id"] for entity in payload["entities"]] == ["climate.ecobee", "light.family_room"]
    assert payload["entities"][0]["unit"] == "°C"
    assert payload["entities"][0]["attributes"]["current_temperature"] == 21.5
    assert payload["entities"][0]["attributes"]["preset_mode"] == "home"
    assert payload["entities"][0]["attributes"]["preset_modes"] == ["home", "away"]
    assert payload["entities"][1]["controllable"] is True


def test_home_assistant_endpoint_hides_iphone_and_sun_entities(tmp_path: Path, monkeypatch) -> None:
    discovery = tmp_path / "tplink_switches.json"
    config = tmp_path / "devices.local.yaml"
    _write_discovery(discovery)
    _write_home_assistant_config(config)
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN", "token")

    def fake_home_assistant_get(home_assistant_config, token, path):
        return [
            {
                "entity_id": "sensor.iphone_15_battery_level",
                "state": "45",
                "attributes": {"friendly_name": "iPhone 15 Battery Level", "device_class": "battery"},
            },
            {
                "entity_id": "sensor.sun_next_rising",
                "state": "2026-06-14T12:05:18+00:00",
                "attributes": {"friendly_name": "Sun Next rising", "device_class": "timestamp"},
            },
            {
                "entity_id": "sensor.temperature_and_humidity_sensor_temperature",
                "state": "26.0",
                "attributes": {
                    "friendly_name": "Temperature and humidity sensor Temperature",
                    "device_class": "temperature",
                    "unit_of_measurement": "°C",
                },
            },
        ]

    monkeypatch.setattr("src.python.web_app._home_assistant_get", fake_home_assistant_get)
    client = TestClient(create_app(discovery_path=discovery, config_path=config, controller=FakeController()))

    response = client.get("/api/home-assistant/entities")

    assert response.status_code == 200
    assert [entity["entity_id"] for entity in response.json()["entities"]] == [
        "sensor.temperature_and_humidity_sensor_temperature"
    ]


def test_tuya_endpoint_prefers_home_assistant_entities(tmp_path: Path, monkeypatch) -> None:
    discovery = tmp_path / "tplink_switches.json"
    config = tmp_path / "devices.local.yaml"
    _write_discovery(discovery)
    _write_home_assistant_config(config)
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN", "token")

    def fake_home_assistant_get(home_assistant_config, token, path):
        return [
            {
                "entity_id": "light.family_room_led",
                "state": "on",
                "attributes": {"friendly_name": "Family room LED"},
            },
            {
                "entity_id": "sensor.temperature_and_humidity_sensor_temperature",
                "state": "26.0",
                "attributes": {
                    "friendly_name": "Temperature and humidity sensor Temperature",
                    "device_class": "temperature",
                    "unit_of_measurement": "°C",
                },
            },
            {
                "entity_id": "sensor.motion_sensor_th_temperature",
                "state": "22.4",
                "attributes": {
                    "friendly_name": "Motion Sensor&TH Temperature",
                    "device_class": "temperature",
                    "unit_of_measurement": "°C",
                },
            },
            {
                "entity_id": "sensor.motion_sensor_th_humidity",
                "state": "46",
                "attributes": {
                    "friendly_name": "Motion Sensor&TH Humidity",
                    "device_class": "humidity",
                    "unit_of_measurement": "%",
                },
            },
            {
                "entity_id": "sensor.motion_sensor_th_illuminance",
                "state": "410",
                "attributes": {
                    "friendly_name": "Motion Sensor&TH Illuminance",
                    "device_class": "illuminance",
                    "unit_of_measurement": "lx",
                },
            },
            {
                "entity_id": "binary_sensor.motion_sensor_th_occupancy",
                "state": "off",
                "attributes": {
                    "friendly_name": "Motion Sensor&TH Occupancy",
                    "device_class": "occupancy",
                },
            },
            {
                "entity_id": "sensor.my_ecobee_current_temperature",
                "state": "25.8",
                "attributes": {
                    "friendly_name": "My ecobee Current Temperature",
                    "device_class": "temperature",
                    "unit_of_measurement": "°C",
                },
            },
            {
                "entity_id": "sensor.iphone_15_battery_level",
                "state": "45",
                "attributes": {"friendly_name": "iPhone 15 Battery Level", "device_class": "battery"},
            },
            {
                "entity_id": "switch.living_room_camera_privacy_mode",
                "state": "off",
                "attributes": {"friendly_name": "Living Room Camera Privacy mode"},
            },
        ]

    monkeypatch.setattr("src.python.web_app._home_assistant_get", fake_home_assistant_get)
    client = TestClient(create_app(discovery_path=discovery, config_path=config, controller=FakeController()))

    response = client.get("/api/tuya/devices")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "home_assistant"
    assert [device["id"] for device in payload["devices"]] == [
        "sensor.motion_sensor_th_humidity",
        "sensor.motion_sensor_th_illuminance",
        "light.family_room_led",
        "binary_sensor.motion_sensor_th_occupancy",
        "sensor.motion_sensor_th_temperature",
        "sensor.temperature_and_humidity_sensor_temperature",
    ]
    family_room_led = next(device for device in payload["devices"] if device["id"] == "light.family_room_led")
    assert family_room_led["controllable"] is True
    assert family_room_led["source"] == "home_assistant"


def test_alarm_endpoint_maps_home_assistant_tuya_alarm_panel(tmp_path: Path, monkeypatch) -> None:
    discovery = tmp_path / "tplink_switches.json"
    config = tmp_path / "devices.local.yaml"
    _write_discovery(discovery)
    _write_home_assistant_config(config)
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN", "token")

    def fake_home_assistant_get(home_assistant_config, token, path):
        return [
            {
                "entity_id": "alarm_control_panel.duo_gong_neng_bao_jing_zhu_ji",
                "state": "disarmed",
                "attributes": {"friendly_name": "多功能报警主机", "supported_features": 11},
            },
            {
                "entity_id": "switch.duo_gong_neng_bao_jing_zhu_ji_siren",
                "state": "off",
                "attributes": {"friendly_name": "多功能报警主机 Siren"},
            },
            {
                "entity_id": "switch.duo_gong_neng_bao_jing_zhu_ji_arm_beep",
                "state": "on",
                "attributes": {"friendly_name": "多功能报警主机 Arm beep"},
            },
            {
                "entity_id": "switch.living_room_camera_privacy_mode",
                "state": "off",
                "attributes": {"friendly_name": "Living Room Camera Privacy mode"},
            },
            {
                "entity_id": "binary_sensor.door_sensor_door",
                "state": "off",
                "attributes": {"friendly_name": "Door Sensor Door", "device_class": "door"},
            },
        ]

    monkeypatch.setattr("src.python.web_app._home_assistant_get", fake_home_assistant_get)
    client = TestClient(create_app(discovery_path=discovery, config_path=config, controller=FakeController()))

    response = client.get("/api/alarm")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["panel"]["entity_id"] == "alarm_control_panel.duo_gong_neng_bao_jing_zhu_ji"
    assert payload["panel"]["name"] == "多功能报警主机"
    assert payload["panel"]["state"] == "disarmed"
    assert payload["panel"]["supported_features"] == 11
    assert [control["entity_id"] for control in payload["controls"]] == [
        "switch.duo_gong_neng_bao_jing_zhu_ji_arm_beep",
        "switch.duo_gong_neng_bao_jing_zhu_ji_siren",
    ]
    assert payload["zones"][0]["id"] == "binary_sensor.door_sensor_door"
    assert payload["zones"][0]["state"] == "closed"

def test_alarm_command_endpoint_controls_home_assistant_alarm_panel(tmp_path: Path, monkeypatch) -> None:
    discovery = tmp_path / "tplink_switches.json"
    config = tmp_path / "devices.local.yaml"
    _write_discovery(discovery)
    _write_home_assistant_config(config)
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN", "token")
    calls = []

    def fake_home_assistant_get(home_assistant_config, token, path):
        return [
            {
                "entity_id": "alarm_control_panel.duo_gong_neng_bao_jing_zhu_ji",
                "state": "disarmed",
                "attributes": {"friendly_name": "多功能报警主机", "supported_features": 11},
            }
        ]

    def fake_home_assistant_post(home_assistant_config, token, path, body):
        calls.append((path, body))
        return []

    monkeypatch.setattr("src.python.web_app._home_assistant_get", fake_home_assistant_get)
    monkeypatch.setattr("src.python.web_app._home_assistant_post", fake_home_assistant_post)
    client = TestClient(create_app(discovery_path=discovery, config_path=config, controller=FakeController()))

    response = client.post("/api/alarm/commands/home")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert calls == [
        (
            "/api/services/alarm_control_panel/alarm_arm_home",
            {"entity_id": "alarm_control_panel.duo_gong_neng_bao_jing_zhu_ji"},
        )
    ]

def test_home_assistant_climate_endpoint_sets_mode_and_temperature(tmp_path: Path, monkeypatch) -> None:
    discovery = tmp_path / "tplink_switches.json"
    config = tmp_path / "devices.local.yaml"
    _write_discovery(discovery)
    _write_home_assistant_config(config)
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN", "token")
    calls = []

    def fake_home_assistant_post(home_assistant_config, token, path, body):
        calls.append((path, body))
        return [{"entity_id": body["entity_id"], "state": "heat"}]

    monkeypatch.setattr("src.python.web_app._home_assistant_post", fake_home_assistant_post)
    client = TestClient(create_app(discovery_path=discovery, config_path=config, controller=FakeController()))

    response = client.post(
        "/api/home-assistant/climate/climate.ecobee",
        json={"hvac_mode": "heat", "preset_mode": "away", "temperature": 21.5},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert calls == [
        ("/api/services/climate/set_hvac_mode", {"entity_id": "climate.ecobee", "hvac_mode": "heat"}),
        ("/api/services/climate/set_preset_mode", {"entity_id": "climate.ecobee", "preset_mode": "away"}),
        ("/api/services/climate/set_temperature", {"entity_id": "climate.ecobee", "temperature": 21.5}),
    ]


def test_home_assistant_climate_endpoint_sets_preset_select_option(tmp_path: Path, monkeypatch) -> None:
    discovery = tmp_path / "tplink_switches.json"
    config = tmp_path / "devices.local.yaml"
    _write_discovery(discovery)
    _write_home_assistant_config(config)
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN", "token")
    calls = []

    def fake_home_assistant_post(home_assistant_config, token, path, body):
        calls.append((path, body))
        return [{"entity_id": body["entity_id"], "state": body.get("option")}]

    monkeypatch.setattr("src.python.web_app._home_assistant_post", fake_home_assistant_post)
    client = TestClient(create_app(discovery_path=discovery, config_path=config, controller=FakeController()))

    response = client.post(
        "/api/home-assistant/climate/climate.ecobee",
        json={"preset_mode": "away", "preset_entity_id": "select.my_ecobee_current_mode"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert calls == [
        (
            "/api/services/select/select_option",
            {"entity_id": "select.my_ecobee_current_mode", "option": "away"},
        ),
    ]


def test_direct_tuya_sensor_supplements_keep_combined_sensor_values() -> None:
    cards = [
        {
            "id": "motion-sensor-th",
            "name": "Motion Sensor&TH",
            "category": "tuya_sensor",
            "values": {"temperature": 22.4, "humidity": 46, "illuminance": 410, "motion": False},
            "source": "cloud",
        },
        {
            "id": "living-room-camera",
            "name": "Living Room Camera",
            "category": "tuya_camera",
            "values": {"motion": True},
            "source": "cloud",
        },
        {
            "id": "smart-plug",
            "name": "Smart Plug",
            "category": "tuya_switch",
            "values": {"switch": True},
            "source": "cloud",
        },
    ]

    supplements = _tuya_direct_sensor_supplements(cards)

    assert supplements == [cards[0]]


def _write_ambient_config(path: Path) -> None:
    path.write_text(
        """
ambient_lights:
  devices:
    - name: Govee strip H613A
      provider: govee_ble
      model: H613A
      room: Living Room
      address: AA:BB:CC:DD:EE:FF
    - name: Govee lamp H6054
      provider: govee_ble
      model: H6054
      room: Bedroom
    - name: Lepro S1 AI LED
      provider: alexa
      model: Lepro S1 AI LED
      room: Studio
      alexa_name: Lepro S1 AI LED
""",
        encoding="utf-8",
    )


def test_ambient_lights_endpoint_returns_configured_devices(tmp_path: Path) -> None:
    discovery = tmp_path / "tplink.json"
    config = tmp_path / "devices.local.yaml"
    _write_discovery(discovery)
    _write_ambient_config(config)

    client = TestClient(create_app(discovery_path=discovery, config_path=config, controller=FakeController()))
    payload = client.get("/api/ambient-lights").json()

    assert payload["lights"][0]["provider"] == "govee_ble"
    assert payload["lights"][0]["status"] == "configured"
    assert payload["lights"][1]["status"] == "needs_ble_address"
    assert payload["lights"][2]["provider"] == "alexa"
    assert payload["lights"][2]["status"] == "needs_alexa_bridge"


def test_ambient_light_command_rejects_unconfigured_or_unsupported_paths(tmp_path: Path) -> None:
    discovery = tmp_path / "tplink.json"
    config = tmp_path / "devices.local.yaml"
    _write_discovery(discovery)
    _write_ambient_config(config)

    client = TestClient(create_app(discovery_path=discovery, config_path=config, controller=FakeController()))

    assert client.post("/api/ambient-lights/Govee%20lamp%20H6054/commands/on").status_code == 400
    assert client.post("/api/ambient-lights/Lepro%20S1%20AI%20LED/commands/on").status_code == 501


def test_govee_ble_command_bytes_include_xor_checksum() -> None:
    assert _govee_ble_command_bytes("on") == bytes.fromhex("3301010000000000000000000000000000000033")
    assert _govee_ble_command_bytes("off") == bytes.fromhex("3301000000000000000000000000000000000032")
    assert _govee_ble_command_bytes("brightness", {"brightness": 50}) == bytes.fromhex("3304320000000000000000000000000000000005")
    assert _govee_ble_command_bytes("color", {"red": 255, "green": 128, "blue": 64}) == bytes.fromhex("330502ff8040000000000000000000000000000b")


class FakeGoveeBleClient:
    def __init__(self) -> None:
        self.writes = []

    async def write_gatt_char(self, characteristic, packet, response):
        self.writes.append((characteristic, packet, response))


def test_govee_power_packets_repeat_when_write_has_no_response() -> None:
    client = FakeGoveeBleClient()
    packet = _govee_ble_command_bytes("off")

    write_count = web_app_module.asyncio.run(
        web_app_module._govee_ble_write_packet(client, "power-characteristic", packet, response=False)
    )

    assert write_count == 2
    assert client.writes == [
        ("power-characteristic", packet, False),
        ("power-characteristic", packet, False),
    ]


def test_govee_non_power_packet_is_not_repeated() -> None:
    client = FakeGoveeBleClient()
    packet = _govee_ble_command_bytes("brightness", {"brightness": 50})

    write_count = web_app_module.asyncio.run(
        web_app_module._govee_ble_write_packet(client, "brightness-characteristic", packet, response=False)
    )

    assert write_count == 1
    assert client.writes == [("brightness-characteristic", packet, False)]

def test_govee_manager_retries_two_transient_connection_failures(monkeypatch) -> None:
    light = web_app_module.AmbientLightDefinition(
        name="Test Govee",
        provider="govee_ble",
        model="H6054",
        room="Test",
        address="11:22:33:44:55:66",
        alexa_name=None,
    )
    manager = object.__new__(web_app_module._GoveeBleManager)
    attempts = []

    async def fake_write_once(_light, _packet):
        attempts.append("write")
        if len(attempts) < 3:
            raise RuntimeError("transient BlueZ failure")
        return {"status": "ok"}

    async def fake_drop_client(_address):
        return None

    manager._write_once = fake_write_once
    manager._drop_client = fake_drop_client
    monkeypatch.setattr(web_app_module, "_govee_ble_forget_cached_device", lambda _address: None)

    result = web_app_module.asyncio.run(manager._write_with_retry(light, b"packet"))

    assert result == {"status": "ok"}
    assert len(attempts) == 3

def test_ambient_light_command_sends_govee_ble_command(tmp_path: Path, monkeypatch) -> None:
    discovery = tmp_path / "tplink.json"
    config = tmp_path / "devices.local.yaml"
    _write_discovery(discovery)
    _write_ambient_config(config)
    sent = []

    def fake_command(light, command, body):
        sent.append((light.address, command, body))
        return {"status": "ok", "command": command, "address": light.address}

    monkeypatch.setattr(web_app_module, "_govee_ble_command_payload", fake_command)
    client = TestClient(create_app(discovery_path=discovery, config_path=config, controller=FakeController()))

    response = client.post("/api/ambient-lights/Govee%20strip%20H613A/commands/on")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert sent == [("AA:BB:CC:DD:EE:FF", "on", {})]


def test_ambient_runtime_state_tracks_power_commands() -> None:
    light = web_app_module.AmbientLightDefinition(
        name="Test Govee",
        provider="govee_ble",
        model="H6054",
        room="Test",
        address="11:22:33:44:55:66",
        alexa_name=None,
    )
    web_app_module.AMBIENT_LIGHT_RUNTIME_STATE.clear()

    web_app_module._remember_ambient_light_command(light, "off", {})
    assert web_app_module._ambient_light_card(light)["is_on"] is False

    web_app_module._remember_ambient_light_command(light, "on", {})
    assert web_app_module._ambient_light_card(light)["is_on"] is True
