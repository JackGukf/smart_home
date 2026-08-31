"""Planning logic for rename-zigbee-entities.py.

The rename itself needs a live Home Assistant, but working out *what* to rename is
pure and worth pinning down: a wrong target here silently renames an entity onto
a name nothing references, and every automation pointing at the old id breaks.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "rename-zigbee-entities.py"

# Hyphenated filename, so it cannot be imported by name.
_spec = importlib.util.spec_from_file_location("rename_zigbee_entities", SCRIPT)
_module = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_module)

plan_renames = _module.plan_renames
slugify = _module.slugify


def _entity(entity_id: str, original_name: str | None, device_id: str = "d1", platform: str = "mqtt") -> dict:
    return {"entity_id": entity_id, "original_name": original_name,
            "device_id": device_id, "platform": platform}


def _device(device_id: str = "d1", name: str = "Temperature and humidity living room", **kw) -> dict:
    return {"id": device_id, "name": name, **kw}


def test_slugify_matches_home_assistant_conventions() -> None:
    assert slugify("Temperature and humidity living room") == "temperature_and_humidity_living_room"
    assert slugify("Smart button at office") == "smart_button_at_office"
    assert slugify("Motion Sensor&TH 2") == "motion_sensor_th_2"
    assert slugify("  spaced  out  ") == "spaced_out"


def test_ieee_named_entity_is_renamed_after_its_device() -> None:
    plan = plan_renames(
        [_entity("sensor.0xa4c138829671ddd5_temperature", "Temperature")],
        [_device()], platform="mqtt", name_filter=None,
    )
    assert plan == [(
        "sensor.0xa4c138829671ddd5_temperature",
        "sensor.temperature_and_humidity_living_room_temperature",
        "",
    )]


def test_correctly_named_entities_are_left_alone() -> None:
    """The dry run has to be quiet when there is nothing to do.

    A planner that proposes a no-op rename for every entity would be worse than
    useless - it would orphan the history of a correctly named entity.
    """
    plan = plan_renames(
        [_entity("sensor.temperature_and_humidity_living_room_temperature", "Temperature")],
        [_device()], platform="mqtt", name_filter=None,
    )
    assert plan == []


def test_diagnostic_entities_are_covered_too() -> None:
    """Zigbee2MQTT omits object_id for these, so rediscovery cannot fix them."""
    plan = plan_renames(
        [_entity("sensor.0xa4c138829671ddd5_linkquality", "Linkquality"),
         _entity("sensor.0xa4c138829671ddd5_last_seen", "Last seen")],
        [_device()], platform="mqtt", name_filter=None,
    )
    assert [target for _, target, _ in plan] == [
        "sensor.temperature_and_humidity_living_room_linkquality",
        "sensor.temperature_and_humidity_living_room_last_seen",
    ]


def test_a_user_supplied_device_name_wins_over_the_discovered_one() -> None:
    plan = plan_renames(
        [_entity("sensor.0xa4c138829671ddd5_temperature", "Temperature")],
        [_device(name="Zbeacon TH01", name_by_user="Living room sensor")],
        platform="mqtt", name_filter=None,
    )
    assert plan[0][1] == "sensor.living_room_sensor_temperature"


def test_other_integrations_are_untouched() -> None:
    """Only the named platform. A Tuya or TP-Link entity is not ours to rename."""
    plan = plan_renames(
        [_entity("sensor.0xdeadbeef_temperature", "Temperature", platform="tuya")],
        [_device()], platform="mqtt", name_filter=None,
    )
    assert plan == []


def test_filter_limits_the_blast_radius() -> None:
    entities = [
        _entity("sensor.0xaaa_temperature", "Temperature", device_id="d1"),
        _entity("sensor.0xbbb_temperature", "Temperature", device_id="d2"),
    ]
    devices = [_device("d1", "Living room sensor"), _device("d2", "Office sensor")]
    plan = plan_renames(entities, devices, platform="mqtt", name_filter="office")
    assert [current for current, _, _ in plan] == ["sensor.0xbbb_temperature"]


def test_a_collision_is_reported_rather_than_clobbering() -> None:
    """Renaming onto an id already in use would destroy the other entity."""
    entities = [
        _entity("sensor.0xaaa_temperature", "Temperature", device_id="d1"),
        _entity("sensor.living_room_sensor_temperature", "Temperature", device_id="d2"),
    ]
    devices = [_device("d1", "Living room sensor"), _device("d2", "Something else")]
    plan = plan_renames(entities, devices, platform="mqtt", name_filter=None)
    assert plan[0][2] == "target id already in use"


def test_two_entities_cannot_be_renamed_onto_one_id() -> None:
    """Two devices sharing a name would otherwise both claim the same target."""
    entities = [
        _entity("sensor.0xaaa_temperature", "Temperature", device_id="d1"),
        _entity("sensor.0xbbb_temperature", "Temperature", device_id="d2"),
    ]
    devices = [_device("d1", "Hallway"), _device("d2", "Hallway")]
    plan = plan_renames(entities, devices, platform="mqtt", name_filter=None)
    assert plan[0][2] == ""
    assert plan[1][2] == "target id already in use"


def test_a_name_with_no_ascii_is_skipped_not_mangled() -> None:
    """Several Tuya devices here are named in Chinese; an empty slug is not an id."""
    plan = plan_renames(
        [_entity("sensor.0xccc_battery", "Battery")],
        [_device(name="智能门铃")], platform="mqtt", name_filter=None,
    )
    assert plan[0][2] == "device name has no ASCII characters"


def test_an_entity_with_no_device_is_ignored() -> None:
    plan = plan_renames(
        [_entity("sensor.orphan", "Battery", device_id="")],
        [_device()], platform="mqtt", name_filter=None,
    )
    assert plan == []
