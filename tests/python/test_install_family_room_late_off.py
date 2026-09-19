"""The family room's late-night lights-off automation: what it switches, and when."""
from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "install-family-room-late-off.py"
spec = importlib.util.spec_from_file_location("late_off", SCRIPT)
late_off = importlib.util.module_from_spec(spec)
spec.loader.exec_module(late_off)

FOUR = {"light.family_room_led", "light.0x286847fffe5eb711", "light.0x64028ffffe64de32",
        "switch.family_room_cabinet_led"}


def test_it_turns_off_all_four_and_never_turns_anything_on():
    body = late_off.automation()
    switched = {e for a in body["actions"] for e in a["target"]["entity_id"]}
    assert switched == FOUR
    assert all(a["action"].endswith("turn_off") for a in body["actions"])


def test_only_overnight_and_only_when_nobody_has_moved_for_ten_minutes():
    conditions = late_off.automation()["conditions"]
    time = next(c for c in conditions if c["condition"] == "time")
    # The start is the dashboard's time helper; the end is fixed.
    assert (time["after"], time["before"]) == ("input_datetime.family_room_lights_off_after", "06:00:00")
    occupancy = next(c for c in conditions if c.get("entity_id") == late_off.OCCUPANCY)
    assert occupancy["state"] == "off" and occupancy["for"] == {"minutes": 10}
    anything_on = next(c for c in conditions if c.get("match") == "any")
    assert set(anything_on["entity_id"]) == FOUR and anything_on["state"] == "on"


def test_an_empty_room_at_the_start_time_is_still_caught():
    """The sensor went quiet at 11:00: no state change after 11:30 would fire."""
    triggers = late_off.automation()["triggers"]
    assert {"trigger": "time", "at": "input_datetime.family_room_lights_off_after"} in triggers
    assert any(t.get("entity_id") == late_off.OCCUPANCY and t.get("to") == "off" for t in triggers)
    assert any(set(t.get("entity_id") or []) == FOUR and t.get("to") == "on" for t in triggers)


def test_no_template_can_trip_on_the_digit_leading_entity_ids():
    assert "states." not in str(late_off.automation())


def test_dry_run_writes_nothing(monkeypatch, capsys):
    def refuse(*_a, **_k):
        raise AssertionError("a dry run must not call Home Assistant")

    monkeypatch.setattr(late_off, "install", refuse)
    assert late_off.main([]) == 0
    assert "Nothing was written" in capsys.readouterr().out


# ── Its start time, from the dashboard (Settings -> Night lights) ────────────

def _client(tmp_path, monkeypatch, calls):
    import yaml
    from fastapi.testclient import TestClient
    from src.python import web_app

    cfg = tmp_path / "devices.local.yaml"
    cfg.write_text(yaml.dump({"home_assistant": {"base_url": "http://127.0.0.1:8123"}}), encoding="utf-8")
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN", "token")
    monkeypatch.setattr(web_app, "_home_assistant_get", lambda c, t, path: {"state": "23:30:00"})
    monkeypatch.setattr(web_app, "_home_assistant_post", lambda c, t, path, body: calls.append((path, body)))
    return TestClient(web_app.create_app(config_path=cfg, check_camera_ports=False))


def test_the_dashboard_reads_the_same_helper_the_automation_does(tmp_path, monkeypatch):
    from src.python import web_app

    assert web_app.NIGHT_LIGHTS_AFTER_ENTITY == late_off.AFTER
    doc = _client(tmp_path, monkeypatch, []).get("/api/night-lights").json()
    assert doc == {"after": "23:30", "until": "06:00", "entity": late_off.AFTER}


def test_the_dashboard_moves_the_start_time(tmp_path, monkeypatch):
    calls: list = []
    response = _client(tmp_path, monkeypatch, calls).put("/api/night-lights", json={"after": "22:45"})

    assert response.status_code == 200
    assert calls == [("/api/services/input_datetime/set_datetime", {"entity_id": late_off.AFTER, "time": "22:45:00"})]


def test_only_a_time_of_day_is_taken(tmp_path, monkeypatch):
    calls: list = []
    client = _client(tmp_path, monkeypatch, calls)
    for bad in ("24:00", "7:5", "23:30:00", "noon", "23:30; rm"):
        assert client.put("/api/night-lights", json={"after": bad}).status_code == 422
    assert calls == []



# ── On with motion, in the dark ─────────────────────────────────────────────

def test_motion_turns_on_only_the_ones_that_are_off():
    """turn_on to a light already on makes the IKEA drivers flash: each light
    is checked on its own and switched only when it is off."""
    body = late_off.motion_on_automation()
    switched = set()
    for step in body["actions"]:
        [check] = step["if"]
        [action] = step["then"]
        assert check == {"condition": "state", "entity_id": check["entity_id"], "state": "off"}
        assert action["target"]["entity_id"] == check["entity_id"]
        assert action["action"] == check["entity_id"].split(".")[0] + ".turn_on"
        switched.add(check["entity_id"])
    assert switched == FOUR
    assert body["triggers"] == [{"trigger": "state", "entity_id": late_off.OCCUPANCY, "from": "off", "to": "on"}]


def test_only_in_the_dark_and_only_if_something_is_off():
    conditions = late_off.motion_on_automation()["conditions"]
    assert {"condition": "state", "entity_id": "sun.sun", "state": "below_horizon"} in conditions
    any_off = next(c for c in conditions if c.get("match") == "any")
    assert set(any_off["entity_id"]) == FOUR and any_off["state"] == "off"


def test_not_for_three_hours_after_movie_mode():
    [template] = [c for c in late_off.motion_on_automation()["conditions"] if c["condition"] == "template"]
    text = template["value_template"]
    assert "state_attr('script.movie_mode', 'last_triggered')" in text
    assert "timedelta(hours=3)" in text and "last is none" in text
    # A template, so the digit-leading Zigbee ids must not be in it.
    assert "0x" not in text


def test_both_automations_are_installed():
    assert [a["id"] for a in late_off.automations()] == ["family_room_lights_off_late", "family_room_lights_on_motion"]



def test_no_automation_here_sends_on_without_checking_first():
    """The owner's rule for every automation that turns a light on."""
    def bare_turn_ons(steps):
        for step in steps:
            if "then" in step:
                continue  # guarded by its own "if it is off"
            if str(step.get("action", "")).endswith("turn_on"):
                yield step
    for automation in late_off.automations():
        assert list(bare_turn_ons(automation["actions"])) == [], automation["id"]
