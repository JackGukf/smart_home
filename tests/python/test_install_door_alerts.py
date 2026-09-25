"""The front door left open: when it fires, where it goes, and what stops it."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "install-door-alerts.py"
spec = importlib.util.spec_from_file_location("door_alerts", SCRIPT)
doors = importlib.util.module_from_spec(spec)
spec.loader.exec_module(doors)
TELEGRAM = ["notify.house_bot_jack"]
BY_ID = {body["id"]: body for body in doors.automations(TELEGRAM)}


def _strings(node):
    if isinstance(node, dict):
        for value in node.values():
            yield from _strings(value)
    elif isinstance(node, list):
        for value in node:
            yield from _strings(value)
    elif isinstance(node, str):
        yield node


def test_a_fires_when_the_last_person_leaves_with_the_door_open():
    body = BY_ID["front_door_open_when_everyone_left"]
    assert body["triggers"][0]["entity_id"] == doors.PEOPLE_HOME and body["triggers"][0]["below"] == 1
    assert body["conditions"] == [{"condition": "state", "entity_id": doors.DOOR, "state": "on"}]
    assert body["actions"][0]["target"]["entity_id"] == doors.SCRIPT


def test_a_also_fires_for_a_door_opened_just_after_leaving_not_hours_later():
    body = BY_ID["front_door_opened_just_after_leaving"]
    assert body["triggers"][0]["to"] == "on" and body["triggers"][0]["for"] == {"minutes": 2}
    template = next(c["value_template"] for c in body["conditions"] if c["condition"] == "template")
    assert "zone.home" in template and str(doors.JUST_LEFT_S) in template


def test_b_needs_no_phone_only_an_open_door_and_a_still_house():
    body = BY_ID["front_door_open_house_still"]
    assert doors.PEOPLE_HOME not in json.dumps(body["conditions"])
    still = next(c for c in body["conditions"] if c.get("entity_id") == doors.INDOOR)
    assert still["for"] == {"minutes": 10} and "off" in still["state"]
    assert {"condition": "state", "entity_id": doors.DOOR, "state": "on", "for": {"minutes": 10}} in body["conditions"]


def test_the_message_is_sent_once_then_reminded_three_times_at_most_while_open():
    body = doors.script(TELEGRAM)
    assert body["mode"] == "single" and body["max_exceeded"] == "silent"   # A and B together: one message
    loop = body["sequence"][1]["repeat"]
    conditions = json.dumps(loop["while"])
    assert doors.DOOR in conditions and doors.ALERT in conditions and "repeat.index <= 4" in conditions
    wait = loop["sequence"][-1]
    assert wait["timeout"] == {"minutes": 15} and wait["continue_on_timeout"] is True
    assert {t["entity_id"] for t in wait["wait_for_trigger"]} == {doors.DOOR, doors.ALERT}


def test_it_goes_to_the_iphone_time_sensitive_and_to_telegram():
    sequence = doors.script(TELEGRAM)["sequence"][1]["repeat"]["sequence"]
    push = next(a for a in sequence if a.get("action") == doors.PHONE)
    assert push["data"]["data"]["push"]["interruption-level"] == "time-sensitive"
    assert push["data"]["data"]["tag"] == doors.TAG
    assert {a["action"] for a in push["data"]["data"]["actions"]} == {"URI", doors.ACK_ACTION}
    telegram = next(a for a in sequence if a.get("action") == "notify.send_message")
    assert telegram["target"]["entity_id"] == TELEGRAM


def test_without_telegram_nothing_is_sent_there():
    text = json.dumps({"s": doors.script([]), "a": doors.automations([])})
    assert "notify.send_message" not in text


def test_closing_the_door_or_i_know_stops_it_and_clears_the_dashboard():
    closed = BY_ID["front_door_closed_after_alert"]
    assert closed["actions"][0] == {"action": "input_boolean.turn_off", "target": {"entity_id": doors.ALERT}}
    closed_push = next(a for a in closed["actions"] if a.get("action") == doors.PHONE)
    assert closed_push["data"]["data"]["tag"] == doors.TAG               # replaces the alert on the lock screen
    ack = BY_ID["front_door_alert_acknowledged"]
    assert ack["triggers"][0]["event_data"] == {"action": doors.ACK_ACTION}
    assert ack["actions"] == [{"action": "input_boolean.turn_off", "target": {"entity_id": doors.ALERT}}]


def test_templates_balance_and_ids_are_fixed():
    for value in _strings({"s": doors.script(TELEGRAM), "a": doors.automations(TELEGRAM)}):
        assert value.count("{{") == value.count("}}") and value.count("{%") == value.count("%}")
    ids = [b["id"] for b in doors.automations(TELEGRAM)]
    assert len(ids) == len(set(ids)) and all(i.startswith("front_door_") for i in ids)


def test_the_script_writes_nothing_without_apply(capsys):
    assert doors.main([]) == 0
    assert "Nothing was written" in capsys.readouterr().out
