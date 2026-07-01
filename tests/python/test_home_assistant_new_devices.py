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
