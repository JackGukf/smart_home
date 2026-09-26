"""While armed: the alarm speaker for an unexpected person downstairs, and the bedroom button."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "install-security-response.py"
spec = importlib.util.spec_from_file_location("security_response", SCRIPT)
sec = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sec)
BY_ID = {body["id"]: body for body in sec.automations()}
SIREN = BY_ID["security_intruder_siren"]


def test_only_while_armed_and_not_during_the_exit():
    conditions = SIREN["conditions"]
    assert {"condition": "state", "entity_id": sec.ALARM, "state": sec.ARMED} in conditions
    assert "disarmed" not in sec.ARMED
    assert any("last_changed" in c.get("value_template", "") for c in conditions)


def test_the_first_floor_is_pir_and_indoor_cameras_never_radar_or_outdoors():
    trigger = SIREN["triggers"][0]
    assert set(trigger["entity_id"]) == set(sec.FIRST_FLOOR_PIR + sec.INDOOR_CAMERAS)
    assert not any("8jt7" in e or "8k2g" in e for e in trigger["entity_id"])          # radar
    assert not any(c in e for e in trigger["entity_id"] for c in ("front_door_camera", "garage", "frontyard"))
    assert trigger["from"] == "off" and trigger["to"] == "on"


def test_the_household_coming_down_is_expected_only_when_the_mode_is_home():
    choose = SIREN["actions"][0]
    expected = choose["choose"][0]
    assert sec.home_mode() in expected["conditions"]
    templates = json.dumps(expected["conditions"])
    assert sec.UPSTAIRS in templates and sec.EXPECTED_UNTIL in templates
    assert expected["sequence"] == [sec.expect_for_a_while()]


def test_the_unexpected_sound_the_speaker_long_enough_and_say_why():
    default = SIREN["actions"][0]["default"]
    assert default[0]["target"]["entity_id"] == sec.REASON
    duration = next(a for a in default if a.get("action") == "number.set_value")
    assert duration["data"]["value"] == sec.SIREN_SECONDS and sec.SIREN_SECONDS <= 1800
    on = default[-1]
    assert on["if"] == [{"condition": "state", "entity_id": sec.SPEAKER, "state": "off"}]
    assert on["then"] == [{"action": "switch.turn_on", "target": {"entity_id": sec.SPEAKER}}]


def test_whoever_is_downstairs_when_the_alarm_arms_is_expected():
    body = BY_ID["security_expected_at_arming"]
    assert body["triggers"] == [{"trigger": "state", "entity_id": sec.ALARM, "to": sec.ARMED}]
    assert sec.home_mode() in body["conditions"]
    assert body["actions"] == [sec.expect_for_a_while()]


def test_the_bedroom_button_once_stops_the_speaker_twice_arms_for_the_night():
    single = BY_ID["security_bedroom_button_stops_speaker"]
    double = BY_ID["security_bedroom_button_night_arm"]
    for body, gesture in ((single, "single"), (double, "double")):
        assert body["triggers"][0]["entity_id"] == sec.BUTTON
        assert {"condition": "state", "entity_id": sec.BUTTON, "attribute": "event_type",
                "state": gesture} in body["conditions"]
    # Stops the speaker (if still sounding) and answers the intrusion alert (A2).
    assert single["actions"] == sec.acknowledge(stop_speaker=True)
    assert "switch.turn_off" in json.dumps(single["actions"])
    arm = double["actions"][0]
    assert arm["action"] == "automation.trigger" and arm["data"] == {"skip_condition": True}
    assert sec.NIGHT_ARM_RULE_ID in arm["target"]["entity_id"]


def test_the_old_light_rules_on_the_button_are_the_ones_removed():
    assert sec.OLD_BUTTON_RULES == ["npu_bedroom_button_single_on", "npu_bedroom_button_double_off"]


def test_templates_use_the_subscript_form_and_balance():
    text = json.dumps(sec.automations())
    assert "states.binary_sensor.0x" not in text
    def strings(node):
        if isinstance(node, dict):
            for value in node.values():
                yield from strings(value)
        elif isinstance(node, list):
            for value in node:
                yield from strings(value)
        elif isinstance(node, str):
            yield node

    for value in strings(sec.automations()):
        assert value.count("{{") == value.count("}}") and value.count("{%") == value.count("%}")


def test_the_script_writes_nothing_without_apply(capsys):
    assert sec.main([]) == 0
    assert "Nothing was written" in capsys.readouterr().out


# ── The intrusion alert (2026-09-25, action list A2) ─────────────────────────

import jinja2  # noqa: E402

TELEGRAM = ["notify.house_bot_jack"]
SCRIPT_BODY = sec.intrusion_script(TELEGRAM)


def _render(template: str, states: dict, **variables) -> str:
    env = jinja2.Environment()
    return env.from_string(template).render(
        states=lambda e: states.get(e, "unknown"), is_state=lambda e, v: states.get(e) == v, **variables).strip()


def test_the_speaker_starting_starts_the_alert_whatever_started_it():
    body = BY_ID["security_intrusion_alert"]
    assert body["triggers"] == [{"trigger": "state", "entity_id": sec.SPEAKER, "from": "off", "to": "on"}]
    assert body["actions"] == [{"action": "script.turn_on", "target": {"entity_id": sec.INTRUSION_SCRIPT}}]


def test_the_first_message_is_critical_names_the_cause_and_has_both_buttons():
    push = SCRIPT_BODY["sequence"][2]
    assert push["action"] == sec.PHONE
    data = push["data"]["data"]
    assert data["push"]["sound"]["critical"] == 1
    assert [a["action"] for a in data["actions"]] == [sec.STOP_ACTION, sec.ACK_ACTION]
    why = _render(sec.WHY, {sec.REASON: "Motion sensor and TH Living room Occupancy · 02:14"})
    assert why == "Motion sensor and TH Living room Occupancy · 02:14"
    assert _render(sec.WHY, {sec.REASON: "unknown"}) == "The alarm speaker was turned on"
    telegram = SCRIPT_BODY["sequence"][3]
    assert telegram["target"]["entity_id"] == TELEGRAM and telegram["data"]["message"].startswith("🚨")


def test_it_repeats_every_two_minutes_until_answered_even_after_the_speaker_stops():
    loop = SCRIPT_BODY["sequence"][4]["repeat"]
    assert {"condition": "state", "entity_id": sec.INTRUSION, "state": "on"} in loop["while"]
    assert "repeat.index <= 15" in loop["while"][1]["value_template"]
    wait = loop["sequence"][0]
    assert wait["wait_for_trigger"] == [{"trigger": "state", "entity_id": sec.INTRUSION, "to": "off"}]
    assert wait["timeout"] == {"minutes": 2}
    reminder = loop["sequence"][1]
    # Only the flag gates a reminder - not the speaker, which stops by itself after 5 minutes.
    assert reminder["if"] == [{"condition": "state", "entity_id": sec.INTRUSION, "state": "on"}]
    text = reminder["then"][0]["data"]["message"]

    class Repeat:
        index = 3
    assert _render(text, {sec.SPEAKER: "off"}, repeat=Repeat, why="Office camera") == \
        "Still no answer - 6 min. Office camera. The speaker is silent now."


def test_stop_silences_and_answers_i_know_only_answers():
    stop = BY_ID["security_intrusion_push_stop"]
    ack = BY_ID["security_intrusion_push_ack"]
    assert stop["triggers"][0]["event_data"] == {"action": sec.STOP_ACTION}
    assert ack["triggers"][0]["event_data"] == {"action": sec.ACK_ACTION}
    flag_off = {"action": "input_boolean.turn_off", "target": {"entity_id": sec.INTRUSION}}
    assert flag_off in stop["actions"] and flag_off in ack["actions"]
    assert "switch.turn_off" in json.dumps(stop["actions"])
    assert "switch.turn_off" not in json.dumps(ack["actions"])


def test_the_bedroom_button_answers_even_after_the_speaker_stopped_by_itself():
    body = BY_ID["security_bedroom_button_stops_speaker"]
    either = next(c for c in body["conditions"] if c.get("condition") == "or")
    assert {"condition": "state", "entity_id": sec.INTRUSION, "state": "on"} in either["conditions"]
    assert {"condition": "state", "entity_id": sec.SPEAKER, "state": "on"} in either["conditions"]
    assert {"action": "input_boolean.turn_off", "target": {"entity_id": sec.INTRUSION}} in body["actions"]


def test_the_alert_flag_is_created():
    assert dict(sec.HELPERS)[sec.INTRUSION]["type"] == "input_boolean/create"
