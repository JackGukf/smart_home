"""The house modes: Away, Home again, Vacation, and the alarm's night arm and morning disarm."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def _load(name: str, file: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


modes = _load("house_modes", "install-house-modes.py")
living_room = _load("living_room_for_modes", "install-living-room-lighting.py")
BY_ID = {body["id"]: body for body in modes.automations()}


def _walk(node):
    """Every dict inside an automation, depth first."""
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


def test_ids_are_fixed_and_unique_so_re_running_replaces():
    ids = [body["id"] for body in modes.automations()]
    assert len(ids) == len(set(ids)) and all(i.startswith("house_mode_") for i in ids)


def test_nothing_is_ever_turned_on_without_checking_it_is_off():
    """The owner's rule: "on" sent to a light that is on makes some flash."""
    for body in modes.automations():
        for node in _walk(body["actions"]):
            then = node.get("then") or []
            guarded = {a["target"]["entity_id"] for a in then
                       if str(a.get("action", "")).endswith(".turn_on")}
            for entity in guarded:
                assert node["if"] == [{"condition": "state", "entity_id": entity, "state": "off"}]
        turn_ons = [n for n in _walk(body["actions"]) if str(n.get("action", "")).endswith(".turn_on")]
        wrapped = [a for n in _walk(body["actions"]) for a in (n.get("then") or [])
                   if str(a.get("action", "")).endswith(".turn_on")]
        assert len(turn_ons) == len(wrapped), body["id"]


def test_away_needs_the_phones_gone_and_the_house_still():
    body = BY_ID["house_mode_goes_away"]
    assert modes.nobody_home() in body["conditions"]
    still = next(c for c in body["conditions"] if c.get("for") == modes.EMPTY_FOR)
    assert set(still["entity_id"]) == set(modes.INDOOR) and "off" in still["state"]
    assert modes.mode_is(modes.HOME) in body["conditions"]
    assert body["actions"] == [modes.set_mode(modes.AWAY)]


def test_outdoor_sensors_do_not_count_as_someone_home():
    outdoor = {"binary_sensor.0xa4c138f3061bad8d_presence",   # front door TH
               "binary_sensor.0xa4c1382ad5555219_presence",   # backyard
               "binary_sensor.0xa4c138b9f255ff1b_presence"}   # fence south
    assert not outdoor & set(modes.INDOOR)


def test_leaving_turns_everything_off_then_the_living_room_on_only_in_the_evening():
    actions = BY_ID["house_mode_leaving"]["actions"]
    assert {"action": modes.ALL_LIGHTS_OFF} in actions
    evening = next(a for a in actions if "if" in a)
    assert evening["if"] == [modes.living_room_evening()]
    assert evening["then"] == [modes.turn_on_if_off(modes.LIVING_ROOM)]
    assert actions.index({"action": modes.ALL_LIGHTS_OFF}) < actions.index(evening)


def test_a_person_home_without_a_phone_is_never_ended_on_vacation_by_motion():
    body = BY_ID["house_mode_arrival"]
    either = next(c for c in body["conditions"] if c["condition"] == "or")
    assert {"condition": "trigger", "id": "phone"} in either["conditions"]
    motion_path = next(c for c in either["conditions"] if c["condition"] == "and")
    assert modes.mode_is(modes.AWAY) in motion_path["conditions"]
    assert modes.mode_is(modes.VACATION) not in motion_path["conditions"]
    motion = next(t for t in body["triggers"] if t.get("id") == "motion")
    # Radar sensors hold "occupied" on nothing; only PIR ends an Away.
    assert not set(motion["entity_id"]) & set(modes.RADAR_FIRST_FLOOR + modes.RADAR_UPSTAIRS)


def test_home_again_lights_follow_the_mode_so_picking_home_by_hand_does_the_same():
    body = BY_ID["house_mode_coming_home"]
    assert body["triggers"] == [{"trigger": "state", "entity_id": modes.MODE,
                                 "from": [modes.AWAY, modes.VACATION], "to": modes.HOME}]
    assert body["conditions"] == [modes.dark()]
    assert body["actions"] == [modes.turn_on_if_off(e) for e in modes.AMBIENT_LIGHTS]
    # Arrival only changes the mode; the lights are the mode's.
    assert BY_ID["house_mode_arrival"]["actions"] == [modes.set_mode(modes.HOME)]


def test_motion_does_not_undo_an_away_picked_by_hand_on_the_way_out():
    either = next(c for c in BY_ID["house_mode_arrival"]["conditions"] if c["condition"] == "or")
    motion_path = next(c for c in either["conditions"] if c["condition"] == "and")
    assert modes.away_for(600) in motion_path["conditions"]


def test_vacation_arms_away_and_its_end_disarms_only_armed_away():
    start = BY_ID["house_mode_vacation_starts"]["actions"]
    arm = start[0]
    assert arm["then"][0]["action"] == "alarm_control_panel.alarm_arm_away"
    assert "disarmed" in arm["if"][0]["state"]
    assert any(a.get("action") == "ecobee.create_vacation" and a.get("continue_on_error") for a in start)
    end = BY_ID["house_mode_vacation_ends"]
    assert end["triggers"][0]["from"] == modes.VACATION
    disarm = end["actions"][0]
    assert disarm["if"][0]["state"] == "armed_away"


def test_vacation_after_a_day_away_reads_a_timestamp_that_survives_restarts():
    body = BY_ID["house_mode_becomes_vacation"]
    template = next(c["value_template"] for c in body["conditions"] if c["condition"] == "template")
    assert modes.AWAY_SINCE in template and "timestamp" in template and "86400" in template
    assert body["triggers"] == [{"trigger": "time_pattern", "minutes": "/10"}]


def test_night_arm_and_morning_disarm_leave_a_vacation_alone():
    arm = BY_ID["house_mode_night_arm"]
    disarm = BY_ID["house_mode_morning_disarm"]
    never_on_vacation = {"condition": "not", "conditions": [modes.mode_is(modes.VACATION)]}
    assert never_on_vacation in arm["conditions"] and never_on_vacation in disarm["conditions"]
    assert {"condition": "state", "entity_id": modes.ALARM, "state": "armed_home"} in disarm["conditions"]
    assert disarm["triggers"] == [{"trigger": "time", "at": "07:00:00"}]
    window = next(c for c in arm["conditions"] if c["condition"] == "time")
    assert window["after"] == "01:30:00"
    assert modes.still(modes.FIRST_FLOOR) in arm["conditions"]
    assert not set(modes.FIRST_FLOOR) & set(modes.PIR_UPSTAIRS + modes.RADAR_UPSTAIRS)


def test_no_template_uses_the_attribute_form_for_a_zigbee_id():
    """ids starting with a digit are a Jinja syntax error as states.binary_sensor.0x..."""
    text = json.dumps(modes.automations())
    assert "states.binary_sensor.0x" not in text
    for body in modes.automations():
        for node in _walk(body):
            for value in node.values():
                if isinstance(value, str) and "{" in value:
                    assert value.count("{{") == value.count("}}") and value.count("{%") == value.count("%}")


def test_the_living_room_late_off_leaves_the_away_light_to_the_modes():
    bodies = next(v for k, v in living_room.automations().items() if k == "living_room_off_late_and_quiet")
    guard = {"condition": "not", "conditions": [
        {"condition": "state", "entity_id": modes.MODE, "state": ["Away", "Vacation"]}]}
    assert guard in bodies["conditions"]


def test_the_script_writes_nothing_without_apply(capsys):
    assert modes.main([]) == 0
    assert "Nothing was written" in capsys.readouterr().out
