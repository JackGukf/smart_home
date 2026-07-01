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
