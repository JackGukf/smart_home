"""The voice resolver, pinned against what Whisper really heard on the panel.

Every "heard" string marked REAL is verbatim from Home Assistant's pipeline debug
record on 2026-09-14. When a new miss turns up, add its transcript here with the
device it should have reached; that is the regression set.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESOLVER = PROJECT_ROOT / "configs" / "homeassistant" / "custom_components" / "voice_resolver" / "resolver.py"

_spec = importlib.util.spec_from_file_location("voice_resolver_logic", RESOLVER)
r = importlib.util.module_from_spec(_spec)
# dataclasses look the defining module up in sys.modules; a module loaded by path
# is not there unless registered first.
sys.modules[_spec.name] = r
_spec.loader.exec_module(r)

# The switchable devices exposed to voice in this house, as of 2026-09-14.
HOUSE = [
    r.Candidate("light.kitchen_light_switch", "Kitchen light switch", area="Kitchen"),
    r.Candidate("light.bedroom_master_bedroom_light", "Master bedroom light", area="Bedroom"),
    r.Candidate("light.family_room_switch", "Family room switch", area="Family room"),
    r.Candidate("light.living_room_living_room_switch_2", "Living room switch 2", area="Living Room"),
    r.Candidate("switch.office_switch", "Office switch", area="Office"),
    r.Candidate("switch.north_bedroom_night_light", "North bedroom night light", area="Bedroom"),
    r.Candidate("switch.living_room_cabinet_led", "Living room cabinet LED", area="Living Room"),
    r.Candidate("light.stick_s3", "Stick S3"),
    r.Candidate("light.bedroom_north_bedroom_light_switch", "North Bedroom Light Switch", area="Bedroom"),
    r.Candidate("light.h6076", "Living room ambient light", area="Living Room"),
    r.Candidate("light.family_room_led", "Family room LED"),
]


def _entity(decision) -> str | None:
    return decision.target.entity_id if decision.target else None


@pytest.mark.parametrize("heard, service, entity_id", [
    (" Turn on leaving room switch to", "turn_on", "light.living_room_living_room_switch_2"),   # REAL
    (" Turn on leaving long switch too.", "turn_on", "light.living_room_living_room_switch_2"),  # REAL
    ("turn on living room switch two", "turn_on", "light.living_room_living_room_switch_2"),
    # The prompted Whisper sometimes puts a comma after the verb.
    (" Turn on, Living room switch 2.", "turn_on", "light.living_room_living_room_switch_2"),
    ("Turn off the kitchen light switch.", "turn_off", "light.kitchen_light_switch"),
    ("turn the office switch off", "turn_off", "switch.office_switch"),
    ("switch on the living room cabinet led", "turn_on", "switch.living_room_cabinet_led"),
    ("turn on stick s three", "turn_on", "light.stick_s3"),
    ("turn of the master bedroom light", "turn_off", "light.bedroom_master_bedroom_light"),
])
def test_misheard_names_reach_the_right_device(heard: str, service: str, entity_id: str) -> None:
    decision = r.resolve(heard, HOUSE)
    assert decision.kind == "act", (decision.kind, [c.name for c in decision.options])
    assert (decision.action, _entity(decision)) == (service, entity_id)


def test_a_non_string_alias_placeholder_does_not_crash_resolution() -> None:
    """HA 2026 puts a ComputedNameType object among aliases. On first deploy that
    raised AttributeError and every missed command failed with unknown_error."""
    class ComputedNameType:  # stands in for Home Assistant's placeholder
        pass

    house = [*HOUSE[:3], r.Candidate("light.living_room_living_room_switch_2", "Living room switch 2",
                                     aliases=(ComputedNameType(), "", "main living room light"))]
    decision = r.resolve(" Turn on leaving room switch to", house)
    assert decision.kind == "act" and _entity(decision) == "light.living_room_living_room_switch_2"
    assert _entity(r.resolve("turn on the main living room light", house)) == "light.living_room_living_room_switch_2"


def test_a_name_without_its_number_is_asked_about_not_guessed() -> None:
    decision = r.resolve("turn on the living room switch", HOUSE)
    assert decision.kind == "ask"
    assert "light.living_room_living_room_switch_2" in [c.entity_id for c in decision.options]
    assert r.speech(decision).endswith("?")


def test_a_different_number_is_never_acted_on() -> None:
    assert r.resolve("turn on living room switch 3", HOUSE).kind != "act"


def test_two_similar_devices_are_offered_as_a_choice() -> None:
    decision = r.resolve("turn on the north bedroom light", HOUSE)
    assert decision.kind == "ask"
    assert len(decision.options) == 2
    assert r.speech(decision).startswith("Did you mean ") and " or " in r.speech(decision)


def test_a_device_that_is_not_exposed_is_never_reached() -> None:
    """The Raspberry PI plug is not in the candidate list, so it cannot be acted on."""
    decision = r.resolve("turn off the raspberry pi", HOUSE)
    assert decision.kind != "act"


def test_questions_and_chatter_are_not_commands() -> None:
    for text in ("What time is it?", "Okay, Naboo.", "is the kitchen light on", "I'm going to think about it"):
        assert r.resolve(text, HOUSE).kind == "not_a_command", text


def test_unknown_names_say_what_was_heard() -> None:
    decision = r.resolve("turn on the garage door opener", HOUSE)
    assert decision.kind == "unknown"
    assert "garage door opener" in r.speech(decision)
    assert "can't" not in r.speech(decision).lower() and "couldn't" not in r.speech(decision).lower()


# --- answering "Did you mean ...?" ---------------------------------------------

def _asked(text: str) -> "r.Decision":
    decision = r.resolve(text, HOUSE)
    assert decision.kind == "ask"
    return decision


def test_yes_to_a_single_option_acts() -> None:
    reply = r.resolve_reply("Yes.", _asked("turn on the living room switch"))
    assert reply.kind == "act" and _entity(reply) == "light.living_room_living_room_switch_2"


def test_no_cancels() -> None:
    assert r.resolve_reply("No", _asked("turn on the living room switch")).kind == "cancel"
    assert r.speech(r.resolve_reply("never mind", _asked("turn on the living room switch"))) == "Okay, never mind."


def test_the_second_one_picks_the_second_option() -> None:
    pending = _asked("turn on the north bedroom light")
    reply = r.resolve_reply("the second one", pending)
    assert reply.kind == "act" and reply.target == pending.options[1]


def test_saying_part_of_the_name_picks_it() -> None:
    pending = _asked("turn on the north bedroom light")
    choice = pending.options[0].name.split()[-1]  # e.g. "switch" or "light"
    reply = r.resolve_reply(pending.options[0].name, pending)
    assert reply.kind == "act" and reply.target == pending.options[0], choice


def test_yes_to_two_options_asks_which() -> None:
    reply = r.resolve_reply("yes", _asked("turn on the north bedroom light"))
    assert reply.kind == "ask" and r.speech(reply).startswith("Which one")


def test_a_new_command_instead_of_an_answer_starts_over() -> None:
    reply = r.resolve_reply("turn off the kitchen light switch", _asked("turn on the living room switch"))
    assert reply.kind == "not_a_reply"


def test_the_action_carries_through_the_question() -> None:
    reply = r.resolve_reply("yes", _asked("turn off the living room switch"))
    assert reply.action == "turn_off"
    assert r.speech(reply) == "Turned off Living room switch 2."
