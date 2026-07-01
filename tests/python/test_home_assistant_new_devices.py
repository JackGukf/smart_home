from __future__ import annotations

import json
from pathlib import Path

from src.python.web_app import (
    _load_known_ha_entities,
    _save_known_ha_entities,
    _seed_known_ha_entities_if_missing,
    _mark_ha_entity_known,
)


def test_load_known_ha_entities_missing_file_returns_empty_set(tmp_path: Path) -> None:
    assert _load_known_ha_entities(tmp_path / "missing.json") == set()


def test_save_and_load_known_ha_entities_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "known.json"
    _save_known_ha_entities(path, {"light.a", "switch.b"})
    assert _load_known_ha_entities(path) == {"light.a", "switch.b"}


def test_load_known_ha_entities_survives_corrupt_file(tmp_path: Path) -> None:
    path = tmp_path / "known.json"
    path.write_text("not json", encoding="utf-8")
    assert _load_known_ha_entities(path) == set()


def test_seed_known_ha_entities_only_seeds_light_and_switch_domains(tmp_path: Path) -> None:
    path = tmp_path / "known.json"
    states = [
        {"entity_id": "light.kitchen", "state": "on"},
        {"entity_id": "switch.north_bedroom_light_switch", "state": "off"},
        {"entity_id": "sensor.hallway_temp", "state": "21"},
        {"entity_id": "climate.living_room", "state": "heat"},
    ]
    _seed_known_ha_entities_if_missing(path, states)
    assert _load_known_ha_entities(path) == {"light.kitchen", "switch.north_bedroom_light_switch"}


def test_seed_known_ha_entities_skips_if_file_already_exists(tmp_path: Path) -> None:
    path = tmp_path / "known.json"
    _save_known_ha_entities(path, {"light.existing"})
    _seed_known_ha_entities_if_missing(path, [{"entity_id": "light.new_one", "state": "on"}])
    assert _load_known_ha_entities(path) == {"light.existing"}


def test_mark_ha_entity_known_adds_to_existing_set(tmp_path: Path) -> None:
    path = tmp_path / "known.json"
    _save_known_ha_entities(path, {"light.a"})
    _mark_ha_entity_known(path, "switch.b")
    assert _load_known_ha_entities(path) == {"light.a", "switch.b"}


def test_mark_new_light_switch_entities_flags_only_unknown_light_and_switch() -> None:
    from src.python.web_app import _mark_new_light_switch_entities

    entities = [
        {"entity_id": "light.kitchen", "domain": "light"},
        {"entity_id": "switch.north_bedroom_light_switch", "domain": "switch"},
        {"entity_id": "sensor.hallway_temp", "domain": "sensor"},
    ]
    known_ids = {"light.kitchen"}

    _mark_new_light_switch_entities(entities, known_ids)

    assert entities[0]["is_new"] is False
    assert entities[1]["is_new"] is True
    assert "is_new" not in entities[2]


# End-to-end test for is_new flagging


class _FakeController:
    async def status(self, switch):
        raise AssertionError("not used in this test")


def _write_ha_config(path: Path) -> None:
    path.write_text(
        "home_assistant:\n"
        "  base_url: http://127.0.0.1:8123\n"
        "  token_env: HOME_ASSISTANT_TOKEN\n"
        "  include_domains: [light, switch]\n"
    )


def test_entities_endpoint_flags_is_new_for_unseen_light_switch(tmp_path: Path, monkeypatch) -> None:
    from fastapi.testclient import TestClient
    from src.python.web_app import create_app

    discovery = tmp_path / "tplink_switches.json"
    discovery.write_text('{"switches": []}')
    config = tmp_path / "devices.local.yaml"
    _write_ha_config(config)
    known_path = tmp_path / "known.json"
    monkeypatch.setattr("src.python.web_app.DEFAULT_HA_KNOWN_ENTITIES_PATH", known_path)
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN", "token")

    def fake_home_assistant_get(home_assistant_config, token, path):
        return [
            {"entity_id": "light.kitchen", "state": "on", "attributes": {"friendly_name": "Kitchen"}},
            {
                "entity_id": "switch.north_bedroom_light_switch",
                "state": "off",
                "attributes": {"friendly_name": "North bedroom light switch"},
            },
        ]

    monkeypatch.setattr("src.python.web_app._home_assistant_get", fake_home_assistant_get)
    client = TestClient(create_app(discovery_path=discovery, config_path=config, controller=_FakeController()))

    first = client.get("/api/home-assistant/entities").json()
    assert {e["entity_id"]: e["is_new"] for e in first["entities"]} == {
        "light.kitchen": False,
        "switch.north_bedroom_light_switch": False,
    }

    def fake_home_assistant_get_with_new_device(home_assistant_config, token, path):
        return fake_home_assistant_get(home_assistant_config, token, path) + [
            {"entity_id": "switch.garage_plug", "state": "on", "attributes": {"friendly_name": "Garage Plug"}},
        ]

    monkeypatch.setattr("src.python.web_app._home_assistant_get", fake_home_assistant_get_with_new_device)
    second = client.get("/api/home-assistant/entities").json()
    flags = {e["entity_id"]: e["is_new"] for e in second["entities"]}
    assert flags["switch.garage_plug"] is True
    assert flags["light.kitchen"] is False


import yaml
from unittest.mock import patch

from src.python.web_app import (
    _ha_light_switch_dashboard_category,
    _load_home_assistant_devices,
    _write_home_assistant_device_to_config,
)


def test_ha_light_switch_dashboard_category_outlet_is_plug() -> None:
    assert _ha_light_switch_dashboard_category("outlet") == "smart_plug"


def test_ha_light_switch_dashboard_category_defaults_to_light() -> None:
    assert _ha_light_switch_dashboard_category(None) == "light_switch"
    assert _ha_light_switch_dashboard_category("switch") == "light_switch"


def test_load_home_assistant_devices_missing_file_returns_empty(tmp_path: Path) -> None:
    assert _load_home_assistant_devices(tmp_path / "missing.yaml") == []


def test_write_home_assistant_device_creates_section(tmp_path: Path) -> None:
    config = tmp_path / "devices.local.yaml"
    with patch("src.python.web_app.DEFAULT_CONFIG_PATH", config):
        _write_home_assistant_device_to_config(
            "switch.north_bedroom_light_switch", "North bedroom light switch", "North Bedroom", "light_switch"
        )
    data = yaml.safe_load(config.read_text())
    assert data["home_assistant_devices"][0] == {
        "entity_id": "switch.north_bedroom_light_switch",
        "name": "North bedroom light switch",
        "room": "North Bedroom",
        "category": "light_switch",
    }


def test_write_home_assistant_device_overwrites_existing_entry(tmp_path: Path) -> None:
    config = tmp_path / "devices.local.yaml"
    config.write_text(
        "home_assistant_devices:\n"
        "- {entity_id: switch.a, name: Old, category: light_switch}\n"
    )
    with patch("src.python.web_app.DEFAULT_CONFIG_PATH", config):
        _write_home_assistant_device_to_config("switch.a", "New Name", None, "smart_plug")
    data = yaml.safe_load(config.read_text())
    assert len(data["home_assistant_devices"]) == 1
    assert data["home_assistant_devices"][0]["name"] == "New Name"
    assert data["home_assistant_devices"][0]["category"] == "smart_plug"
    assert "room" not in data["home_assistant_devices"][0]


def test_confirm_endpoint_writes_config_and_marks_known(tmp_path: Path, monkeypatch) -> None:
    discovery = tmp_path / "tplink_switches.json"
    discovery.write_text('{"switches": []}')
    config = tmp_path / "devices.local.yaml"
    known_path = tmp_path / "known.json"
    monkeypatch.setattr("src.python.web_app.DEFAULT_HA_KNOWN_ENTITIES_PATH", known_path)
    from src.python.web_app import create_app
    from fastapi.testclient import TestClient

    class _FakeController:
        async def status(self, switch):
            raise AssertionError("not used")

    with patch("src.python.web_app.DEFAULT_CONFIG_PATH", config):
        client = TestClient(create_app(discovery_path=discovery, config_path=config, controller=_FakeController()))
        response = client.post(
            "/api/home-assistant/devices/switch.north_bedroom_light_switch/confirm",
            json={"name": "North bedroom light switch", "room": "North Bedroom", "category": "light_switch"},
        )
        assert response.status_code == 200
        data = yaml.safe_load(config.read_text())
        assert data["home_assistant_devices"][0]["entity_id"] == "switch.north_bedroom_light_switch"

    assert "switch.north_bedroom_light_switch" in _load_known_ha_entities(known_path)


def test_ignore_endpoint_marks_known_without_touching_config(tmp_path: Path, monkeypatch) -> None:
    discovery = tmp_path / "tplink_switches.json"
    discovery.write_text('{"switches": []}')
    config = tmp_path / "devices.local.yaml"
    known_path = tmp_path / "known.json"
    monkeypatch.setattr("src.python.web_app.DEFAULT_HA_KNOWN_ENTITIES_PATH", known_path)
    from src.python.web_app import create_app
    from fastapi.testclient import TestClient

    class _FakeController:
        async def status(self, switch):
            raise AssertionError("not used")

    client = TestClient(create_app(discovery_path=discovery, config_path=config, controller=_FakeController()))
    response = client.post("/api/home-assistant/devices/switch.unwanted/ignore")

    assert response.status_code == 200
    assert not config.exists()
    assert "switch.unwanted" in _load_known_ha_entities(known_path)


from src.python.web_app import _home_assistant_device_cards


def test_home_assistant_device_cards_empty_when_no_confirmed_devices(tmp_path: Path) -> None:
    config = tmp_path / "devices.local.yaml"
    assert _home_assistant_device_cards(config) == []


def test_home_assistant_device_cards_shapes_card_from_config_and_live_state(tmp_path: Path, monkeypatch) -> None:
    config = tmp_path / "devices.local.yaml"
    config.write_text(
        "home_assistant:\n"
        "  base_url: http://127.0.0.1:8123\n"
        "  token_env: HOME_ASSISTANT_TOKEN\n"
        "home_assistant_devices:\n"
        "- entity_id: switch.north_bedroom_light_switch\n"
        "  name: North bedroom light switch\n"
        "  room: North Bedroom\n"
        "  category: light_switch\n"
    )
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN", "token")

    def fake_home_assistant_get(home_assistant_config, token, path):
        return [{"entity_id": "switch.north_bedroom_light_switch", "state": "on", "attributes": {}}]

    monkeypatch.setattr("src.python.web_app._home_assistant_get", fake_home_assistant_get)

    cards = _home_assistant_device_cards(config)

    assert cards == [
        {
            "id": "switch.north_bedroom_light_switch",
            "name": "North bedroom light switch",
            "host": "ha:switch.north_bedroom_light_switch",
            "model": "Home Assistant",
            "type": "Home Assistant",
            "category": "light_switch",
            "is_dimmable": False,
            "room": "North Bedroom",
            "is_on": True,
            "brightness": None,
        }
    ]


from src.python.web_app import _is_tuya_home_assistant_entity


def test_is_tuya_home_assistant_entity_excludes_confirmed_entity_ids() -> None:
    entity = {"entity_id": "switch.north_bedroom_light_switch", "attributes": {"friendly_name": "North bedroom light switch"}}
    assert _is_tuya_home_assistant_entity(entity) is True
    assert (
        _is_tuya_home_assistant_entity(entity, confirmed_entity_ids={"switch.north_bedroom_light_switch"})
        is False
    )


def test_home_assistant_device_cards_returns_card_with_none_state_when_ha_unreachable(
    tmp_path: Path, monkeypatch
) -> None:
    config = tmp_path / "devices.local.yaml"
    config.write_text(
        "home_assistant:\n"
        "  base_url: http://127.0.0.1:8123\n"
        "  token_env: HOME_ASSISTANT_TOKEN\n"
        "home_assistant_devices:\n"
        "- entity_id: switch.north_bedroom_light_switch\n"
        "  name: North bedroom light switch\n"
        "  room: North Bedroom\n"
        "  category: light_switch\n"
    )
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN", "token")

    def fake_home_assistant_get(home_assistant_config, token, path):
        raise RuntimeError("HA down")

    monkeypatch.setattr("src.python.web_app._home_assistant_get", fake_home_assistant_get)

    cards = _home_assistant_device_cards(config)

    assert len(cards) == 1
    assert cards[0]["id"] == "switch.north_bedroom_light_switch"
    assert cards[0]["host"] == "ha:switch.north_bedroom_light_switch"
    assert cards[0]["is_on"] is None


def test_home_assistant_device_cards_returns_card_with_none_state_when_no_token(
    tmp_path: Path, monkeypatch
) -> None:
    config = tmp_path / "devices.local.yaml"
    config.write_text(
        "home_assistant:\n"
        "  base_url: http://127.0.0.1:8123\n"
        "  token_env: HOME_ASSISTANT_TOKEN\n"
        "home_assistant_devices:\n"
        "- entity_id: switch.north_bedroom_light_switch\n"
        "  name: North bedroom light switch\n"
        "  room: North Bedroom\n"
        "  category: light_switch\n"
    )
    monkeypatch.delenv("HOME_ASSISTANT_TOKEN", raising=False)

    cards = _home_assistant_device_cards(config)

    assert len(cards) == 1
    assert cards[0]["id"] == "switch.north_bedroom_light_switch"
    assert cards[0]["host"] == "ha:switch.north_bedroom_light_switch"
    assert cards[0]["is_on"] is None


def test_devices_endpoint_includes_confirmed_home_assistant_light_switch(tmp_path: Path, monkeypatch) -> None:
    discovery = tmp_path / "tplink_switches.json"
    discovery.write_text('{"switches": []}')
    config = tmp_path / "devices.local.yaml"
    config.write_text(
        "home_assistant:\n"
        "  base_url: http://127.0.0.1:8123\n"
        "  token_env: HOME_ASSISTANT_TOKEN\n"
        "home_assistant_devices:\n"
        "- entity_id: switch.north_bedroom_light_switch\n"
        "  name: North bedroom light switch\n"
        "  room: North Bedroom\n"
        "  category: light_switch\n"
    )
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN", "token")

    def fake_home_assistant_get(home_assistant_config, token, path):
        return [{"entity_id": "switch.north_bedroom_light_switch", "state": "on", "attributes": {}}]

    monkeypatch.setattr("src.python.web_app._home_assistant_get", fake_home_assistant_get)

    from src.python.web_app import create_app
    from fastapi.testclient import TestClient

    class _FakeController:
        async def status(self, switch):
            raise AssertionError("no tplink switches configured")

    client = TestClient(create_app(discovery_path=discovery, config_path=config, controller=_FakeController()))
    response = client.get("/api/devices")

    assert response.status_code == 200
    devices = response.json()["devices"]
    assert devices == [
        {
            "id": "switch.north_bedroom_light_switch",
            "name": "North bedroom light switch",
            "host": "ha:switch.north_bedroom_light_switch",
            "model": "Home Assistant",
            "type": "Home Assistant",
            "category": "light_switch",
            "is_dimmable": False,
            "room": "North Bedroom",
            "is_on": True,
            "brightness": None,
        }
    ]
