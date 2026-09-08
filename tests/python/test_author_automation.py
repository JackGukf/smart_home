"""The automation author's checks.

The model is the unreliable part of this tool and cannot be tested; the checks
around it are the part that makes its unreliability visible, so they are what
these tests cover. Each case here is a mistake Qwen3-4B actually made against
the real house, not a hypothetical.
"""

from __future__ import annotations

from src.python import automation_author as author

ENTITIES = {"binary_sensor.hall_motion", "light.family_room", "switch.office_switch",
            "sensor.bedroom_humidity"}
SERVICES = {"light.turn_on", "light.turn_off", "switch.turn_off", "notify.mobile_app_iphone_15"}


def check(automation):
    return author.validate(automation, ENTITIES, SERVICES)


def test_invented_entity_is_rejected() -> None:
    """The failure that looks most like success: it loads, and never fires.

    The model produced switch.family_room_switch, which is plausible and does
    not exist -- the real ones are switch.family_room_switch_led and
    light.family_room_switch.
    """
    problems = check({
        "alias": "x",
        "triggers": [{"trigger": "state", "entity_id": "binary_sensor.hall_motion", "to": "on"}],
        "actions": [{"action": "light.turn_on", "entity_id": "switch.family_room_switch"}],
    })
    assert any("does not exist" in p for p in problems)


def test_delay_is_a_step_not_a_service() -> None:
    """Asked for "for five minutes", the model emitted `action: delay`.

    Home Assistant has no delay service; such an automation loads and silently
    skips the wait.
    """
    assert any("delay" in p and "does not exist" in p for p in check({
        "alias": "x",
        "triggers": [{"trigger": "state", "entity_id": "binary_sensor.hall_motion", "to": "on"}],
        "actions": [{"action": "delay", "data": {"message": "5 minutes"}}],
    }))

    # The correct form passes.
    assert check({
        "alias": "x",
        "triggers": [{"trigger": "state", "entity_id": "binary_sensor.hall_motion", "to": "on"}],
        "actions": [{"action": "light.turn_on", "entity_id": "light.family_room"},
                    {"delay": "00:05:00"},
                    {"action": "light.turn_off", "entity_id": "light.family_room"}],
    }) == []


def test_state_trigger_that_can_never_fire_is_rejected() -> None:
    """from == to. Reached for when a numeric threshold was meant."""
    assert any("never fire" in p for p in check({
        "alias": "x",
        "triggers": [{"trigger": "state", "entity_id": "sensor.bedroom_humidity",
                      "from": "70", "to": "70"}],
        "actions": [{"action": "notify.mobile_app_iphone_15"}],
    }))


def test_time_trigger_cannot_take_sunset() -> None:
    """"after sunset" produced a time trigger at sunset -- wrong construct and
    invalid value. It is a condition; as a trigger the automation also fires at
    sunset regardless of what was supposed to trigger it."""
    problems = check({
        "alias": "x",
        "triggers": [{"trigger": "time", "at": "sunset"}],
        "actions": [{"action": "switch.turn_off", "entity_id": "switch.office_switch"}],
    })
    assert any("at=HH:MM:SS" in p for p in problems)
    assert any("sun trigger" in p or "condition" in p for p in problems)


def test_a_step_is_a_service_call_or_a_wait_never_both() -> None:
    assert any("one or the other" in p for p in check({
        "alias": "x",
        "triggers": [{"trigger": "state", "entity_id": "binary_sensor.hall_motion", "to": "on"}],
        "actions": [{"action": "light.turn_on", "entity_id": "light.family_room", "delay": "00:01:00"}],
    }))
    assert any("must not carry 'data'" in p for p in check({
        "alias": "x",
        "triggers": [{"trigger": "state", "entity_id": "binary_sensor.hall_motion", "to": "on"}],
        "actions": [{"delay": "00:01:00", "data": {"message": "hi"}}],
    }))


def test_hints_catch_what_validation_cannot() -> None:
    """Structurally valid, and not what was asked.

    Every one of these came back from a single request: five seconds instead of
    five minutes, the delay before the thing it was meant to delay, no sunset
    condition, and nothing ever turned off again.
    """
    hints = author.review_hints(
        "when the hallway motion sensor detects movement after sunset, "
        "turn on the family room switch for 5 minutes",
        {"alias": "x",
         "triggers": [{"trigger": "state", "entity_id": "binary_sensor.hall_motion", "to": "on"}],
         "actions": [{"delay": "00:00:05"},
                     {"action": "light.turn_on", "entity_id": "light.family_room"}]},
    )
    joined = " | ".join(hints)
    assert "00:05:00" in joined, "did not notice 5 minutes became 5 seconds"
    assert "turn_off" in joined, "did not notice nothing is ever turned off"
    assert "no condition" in joined, "did not notice the sunset restriction vanished"
    assert "first action is a delay" in joined


def test_time_hint_does_not_fire_when_the_trigger_is_already_a_time() -> None:
    """Regression: "every night at 11pm" is fully handled by a time trigger.

    Warning about it trained the reader to ignore hints, which is worse than
    having none.
    """
    hints = author.review_hints(
        "turn off the office switch every night at 11pm",
        {"alias": "x",
         "triggers": [{"trigger": "time", "at": "23:00:00"}],
         "actions": [{"action": "switch.turn_off", "entity_id": "switch.office_switch"}]},
    )
    assert hints == [], f"false positive: {hints}"


def test_threshold_without_a_numeric_state_trigger_is_flagged() -> None:
    """The one the model would not fix even after two repair attempts."""
    hints = author.review_hints(
        "notify my iphone when the bedroom humidity goes above 70 percent",
        {"alias": "x",
         "triggers": [{"trigger": "state", "entity_id": "sensor.bedroom_humidity",
                       "from": "0", "to": "70.00000000000001"}],
         "actions": [{"action": "notify.mobile_app_iphone_15"}]},
    )
    assert any("numeric_state" in h for h in hints)

    # And the correct form is not flagged.
    assert author.review_hints(
        "notify my iphone when the bedroom humidity goes above 70 percent",
        {"alias": "x",
         "triggers": [{"trigger": "numeric_state", "entity_id": "sensor.bedroom_humidity",
                       "above": 70}],
         "actions": [{"action": "notify.mobile_app_iphone_15"}]},
    ) == []


def test_entity_selection_drops_dead_entities_and_prefers_actionable_ones() -> None:
    """52 of the 218 entities are unavailable; none can be automated against,
    and they crowd a 4096-token context."""
    states = [
        {"entity_id": "light.family_room", "state": "on", "attributes": {"friendly_name": "Family room"}},
        {"entity_id": "light.dead_one", "state": "unavailable", "attributes": {"friendly_name": "Family room spare"}},
        {"entity_id": "sensor.unrelated", "state": "5", "attributes": {"friendly_name": "Pressure"}},
    ]
    chosen = [s["entity_id"] for s in author.select_entities(states, "turn on the family room light", 10)]
    assert "light.family_room" in chosen
    assert "light.dead_one" not in chosen
