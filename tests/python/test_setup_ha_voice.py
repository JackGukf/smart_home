"""The satellite's voice pipeline, and the wake word said twice.

Both come from measured runs on 2026-09-13. Speech the matcher could not parse
waited 17 s and 57 s on Qwen, in silence, before an answer to noise - so the
voice pipeline must carry no model. And the satellite gives no sign it woke, so
the wake word got said again and transcribed as the command, verbatim
" Okay, Naboo." - so that transcript must be answered with nothing.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT_ROOT / "scripts" / "setup-ha-voice.py"

_spec = importlib.util.spec_from_file_location("setup_ha_voice", SCRIPT)
voice = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(voice)


def _normalise(text: str) -> str:
    """Roughly what Home Assistant's matcher does: case and punctuation go."""
    return " ".join(re.sub(r"[^\w\s]", " ", text.lower()).split())


def test_the_voice_pipeline_has_no_model_in_it() -> None:
    fields = voice.voice_pipeline_fields("stt.faster_whisper", "en", "tts.piper", "en_US")
    assert fields["conversation_engine"] == "conversation.home_assistant"
    assert "qwen" not in str(fields).lower()


def test_the_voice_pipeline_keeps_the_negotiated_languages() -> None:
    """Piper takes en_US and not en; the pipeline must carry what was negotiated."""
    fields = voice.voice_pipeline_fields("stt.faster_whisper", "en", "tts.piper", "en_US")
    assert (fields["stt_language"], fields["tts_language"]) == ("en", "en_US")


def test_the_voice_pipeline_is_not_the_default_one() -> None:
    """Typed Assist keeps its Qwen fallback; only the satellite changes."""
    assert voice.VOICE_PIPELINE_NAME != "Home Assistant"


def test_the_transcript_whisper_actually_produced_is_ignored() -> None:
    phrases = {_normalise(p) for p in voice.WAKE_ECHO_PHRASES}
    assert _normalise(" Okay, Naboo.") in phrases


def test_the_repeated_wake_word_gets_an_empty_answer() -> None:
    body = voice.wake_echo_automation()
    assert body["triggers"] == [{"trigger": "conversation",
                                 "command": voice.WAKE_ECHO_PHRASES}]
    assert body["actions"] == [{"set_conversation_response": ""}]


def test_no_ignored_phrase_is_a_real_command() -> None:
    """Every phrase is only the wake word; nothing a person means as a request."""
    for phrase in voice.WAKE_ECHO_PHRASES:
        words = set(_normalise(phrase).split())
        assert words <= {"okay", "ok", "nabu", "naboo"}, phrase


def test_the_automation_id_is_fixed_so_re_running_replaces_rather_than_duplicates() -> None:
    assert voice.WAKE_ECHO_AUTOMATION_ID == "voice_ignore_repeated_wake_word"


# --- custom sentences -------------------------------------------------------

SENTENCES_FILE = voice.CUSTOM_SENTENCES / "voice_time_date.yaml"


def _expand(template: str) -> set[str]:
    """Expand hassil's [optional] and (a|b) syntax into every plain sentence."""
    match = re.search(r"\[([^\[\]]*)\]|\(([^()]*)\)", template)
    if not match:
        return {" ".join(template.split())}
    if match.group(1) is not None:
        options = [""] + match.group(1).split("|")
    else:
        options = match.group(2).split("|")
    out: set[str] = set()
    for option in options:
        out |= _expand(template[:match.start()] + option + template[match.end():])
    return out


def _sentences() -> dict[str, set[str]]:
    import yaml
    data = yaml.safe_load(SENTENCES_FILE.read_text(encoding="utf-8"))
    return {intent: {s for block in body["data"] for t in block["sentences"] for s in _expand(t)}
            for intent, body in data["intents"].items()}


def test_sentences_only_extend_home_assistants_own_time_and_date_intents() -> None:
    assert set(_sentences()) == {"HassGetCurrentTime", "HassGetCurrentDate"}


def test_the_phrasings_that_failed_on_the_panel_are_covered() -> None:
    """Verbatim Whisper transcripts that got "Sorry, I couldn't understand that"."""
    sentences = _sentences()
    assert _normalise("What time is now?") in sentences["HassGetCurrentTime"]
    for heard in ["What day is today?", "What day is it?", "What day is it today?",
                  "What's today?", "Today's date"]:
        assert _normalise(heard.replace("'", "")) in {_normalise(s.replace("'", ""))
                                                      for s in sentences["HassGetCurrentDate"]}, heard


def test_no_sentence_is_shared_between_time_and_date() -> None:
    sentences = _sentences()
    assert not sentences["HassGetCurrentTime"] & sentences["HassGetCurrentDate"]


def test_the_date_answer_names_the_weekday() -> None:
    """Rendered with real Jinja against the slot Home Assistant passes: a date."""
    import datetime

    import jinja2
    import yaml
    data = yaml.safe_load(SENTENCES_FILE.read_text(encoding="utf-8"))
    template = data["responses"]["intents"]["HassGetCurrentDate"]["default"]
    render = jinja2.Environment().from_string(template).render
    assert render(slots={"date": datetime.date(2026, 9, 13)}).strip() == "Sunday, September 13th, 2026"
    assert render(slots={"date": datetime.date(2026, 10, 1)}).strip() == "Thursday, October 1st, 2026"
    assert render(slots={"date": datetime.date(2026, 11, 12)}).strip() == "Thursday, November 12th, 2026"
    assert render(slots={"date": datetime.date(2026, 12, 22)}).strip() == "Tuesday, December 22nd, 2026"


# --- what Assist can reach ------------------------------------------------------

def _registry():
    """A small house shaped like the real one: a Kasa switch bridged back in as
    Matter, a bridged device with no native twin, a Matter test light, and
    readings that are and are not worth a voice."""
    devices = [
        {"id": "kasa", "name": "Kitchen light switch", "manufacturer": "TP-Link"},
        {"id": "bridge", "name": "Dashboard Bridge", "manufacturer": "Smart Home AI"},
        {"id": "b-kitchen", "name": "Kitchen light switch", "manufacturer": "Smart Home AI", "via_device_id": "bridge"},
        {"id": "b-stick", "name": "Stick S3", "manufacturer": "Smart Home AI", "via_device_id": "bridge"},
        {"id": "test", "name": "TEST_PRODUCT", "manufacturer": "TEST_VENDOR"},
        {"id": "zb", "name": "Door sensor front door", "manufacturer": "Tuya"},
    ]
    entities = [
        {"entity_id": "light.kitchen_light_switch", "platform": "tplink", "device_id": "kasa"},
        {"entity_id": "light.kitchen_light_switch_2", "platform": "matter", "device_id": "b-kitchen"},
        {"entity_id": "light.stick_s3", "platform": "matter", "device_id": "b-stick"},
        {"entity_id": "light.test_product_2", "platform": "matter", "device_id": "test"},
        {"entity_id": "binary_sensor.front_door_contact", "platform": "mqtt", "device_id": "zb"},
        {"entity_id": "binary_sensor.front_door_battery", "platform": "mqtt", "device_id": "zb"},
        {"entity_id": "binary_sensor.front_door_tamper", "platform": "mqtt", "device_id": "zb",
         "entity_category": "diagnostic"},
        {"entity_id": "binary_sensor.kitchen_water", "platform": "tuya", "device_id": "zb"},
        {"entity_id": "sensor.bedroom_temperature", "platform": "mqtt", "device_id": "zb"},
        {"entity_id": "sensor.old_temperature", "platform": "mqtt", "device_id": "zb", "disabled_by": "user"},
    ]
    states = {
        "light.kitchen_light_switch": {"attributes": {"friendly_name": "Kitchen light switch"}},
        "light.kitchen_light_switch_2": {"attributes": {"friendly_name": "Kitchen light switch"}},
        "light.stick_s3": {"attributes": {"friendly_name": "Stick S3"}},
        "light.test_product_2": {"attributes": {"friendly_name": "TEST_PRODUCT"}},
        "binary_sensor.front_door_contact": {"attributes": {"device_class": "door"}},
        "binary_sensor.front_door_battery": {"attributes": {"device_class": "battery"}},
        "binary_sensor.front_door_tamper": {"attributes": {"device_class": "tamper"}},
        "binary_sensor.kitchen_water": {"attributes": {"device_class": "moisture"}},
        "sensor.bedroom_temperature": {"attributes": {"device_class": "temperature"}},
        "sensor.old_temperature": {"attributes": {"device_class": "temperature"}},
    }
    exposed = {eid: {"conversation": True} for eid in (
        "light.kitchen_light_switch", "light.kitchen_light_switch_2", "light.stick_s3",
        "light.test_product_2", "binary_sensor.front_door_contact", "sensor.bedroom_temperature")}
    return entities, devices, states, exposed


def test_the_bridged_copy_of_a_native_switch_is_hidden_from_assist() -> None:
    """Two exposed entities with one name is exactly "multiple devices called ..."."""
    _, hide = voice.plan_exposure(*_registry())
    assert "light.kitchen_light_switch_2" in hide
    assert "light.kitchen_light_switch" not in hide


def test_a_bridged_device_with_no_native_twin_stays_reachable() -> None:
    _, hide = voice.plan_exposure(*_registry())
    assert "light.stick_s3" not in hide


def test_the_matter_test_light_is_hidden() -> None:
    _, hide = voice.plan_exposure(*_registry())
    assert "light.test_product_2" in hide


def test_room_readings_are_exposed_but_noise_is_not() -> None:
    expose, _ = voice.plan_exposure(*_registry())
    assert expose == ["binary_sensor.kitchen_water"]  # door and temperature already were


def test_nothing_changes_once_the_plan_has_been_applied() -> None:
    entities, devices, states, exposed = _registry()
    expose, hide = voice.plan_exposure(entities, devices, states, exposed)
    for eid in expose:
        exposed[eid] = {"conversation": True}
    for eid in hide:
        exposed[eid] = {"conversation": False}
    assert voice.plan_exposure(entities, devices, states, exposed) == ([], [])


def test_a_switch_hidden_behind_its_light_wrapper_is_not_left_exposed() -> None:
    """switch_as_x hides the original switch; exposed, it duplicates the light's name."""
    entities, devices, states, exposed = _registry()
    devices.append({"id": "wall", "name": "Master bedroom light", "manufacturer": "TP-Link"})
    entities += [
        {"entity_id": "switch.master_bedroom_light", "platform": "tplink", "device_id": "wall",
         "hidden_by": "integration"},
        {"entity_id": "light.master_bedroom_light_3", "platform": "switch_as_x", "device_id": "wall"},
    ]
    for eid in ("switch.master_bedroom_light", "light.master_bedroom_light_3"):
        states[eid] = {"attributes": {"friendly_name": "Master bedroom light"}}
        exposed[eid] = {"conversation": True}
    _, hide = voice.plan_exposure(entities, devices, states, exposed)
    assert "switch.master_bedroom_light" in hide
    assert "light.master_bedroom_light_3" not in hide


def test_a_switch_is_known_to_be_wrapped_by_its_device_not_its_name() -> None:
    """The wrapper is named after the device ("light.bedroom_master_bedroom_light"),
    not the switch, so a name match missed it and a rerun wrapped it again."""
    entities = [
        {"entity_id": "switch.master_bedroom_light", "platform": "tplink", "device_id": "wall-1",
         "hidden_by": "integration"},
        {"entity_id": "light.bedroom_master_bedroom_light", "platform": "switch_as_x", "device_id": "wall-1"},
        {"entity_id": "switch.master_bedroom_light_led", "platform": "tplink", "device_id": "wall-1"},
        {"entity_id": "switch.living_room_switch_2", "platform": "tplink", "device_id": "wall-2"},
        {"entity_id": "switch.office_switch", "platform": "tplink", "device_id": None},
    ]
    wrapped = voice.switches_already_wrapped(entities)
    assert "switch.master_bedroom_light" in wrapped
    assert "switch.living_room_switch_2" not in wrapped  # not wrapped yet: a rerun must still do it
    assert "switch.office_switch" not in wrapped          # no device must never count as wrapped


def test_only_wall_switches_become_lights_never_plugs() -> None:
    assert set(voice.WALL_SWITCHES_AS_LIGHTS) == {"switch.master_bedroom_light", "switch.living_room_switch_2"}
    assert not any("plug" in eid or "night_light" in eid or "office" in eid
                   for eid in voice.WALL_SWITCHES_AS_LIGHTS)


def test_the_plug_that_powers_the_wall_panel_is_never_reachable_by_voice() -> None:
    """Home Assistant exposes a newly added switch by default; this takes it back."""
    entities, devices, states, exposed = _registry()
    devices.append({"id": "pi-plug", "name": "Raspberry PI", "manufacturer": "TP-Link"})
    entities.append({"entity_id": "switch.raspberry_pi", "platform": "tplink", "device_id": "pi-plug"})
    states["switch.raspberry_pi"] = {"attributes": {"friendly_name": "Raspberry PI"}}
    exposed["switch.raspberry_pi"] = {"conversation": True}
    _, hide = voice.plan_exposure(entities, devices, states, exposed)
    assert "switch.raspberry_pi" in hide


def test_the_protected_plug_is_matched_by_device_even_if_the_entity_is_renamed() -> None:
    entities, devices, states, exposed = _registry()
    devices.append({"id": "pi-plug", "name": "Raspberry PI", "manufacturer": "TP-Link"})
    entities.append({"entity_id": "switch.panel_power", "platform": "tplink", "device_id": "pi-plug"})
    states["switch.panel_power"] = {"attributes": {"friendly_name": "Panel power"}}
    exposed["switch.panel_power"] = {"conversation": True}
    _, hide = voice.plan_exposure(entities, devices, states, exposed)
    assert "switch.panel_power" in hide


STATUS_FILE = voice.CUSTOM_SENTENCES / "voice_device_status.yaml"


def _status():
    import yaml
    return yaml.safe_load(STATUS_FILE.read_text(encoding="utf-8"))


def _sentences_with(template_fill: dict[str, str]) -> set[str]:
    out: set[str] = set()
    for body in _status()["intents"].values():
        for block in body["data"]:
            for template in block["sentences"]:
                filled = template
                for slot, value in template_fill.items():
                    filled = filled.replace(slot, value)
                if "{" not in filled:
                    out |= {_normalise(s) for s in _expand(filled)}
    return out


def test_status_sentences_only_use_home_assistants_own_intents() -> None:
    assert set(_status()["intents"]) == {"HassGetState", "HassClimateGetTemperature"}


def test_the_status_questions_that_failed_on_the_panel_are_covered() -> None:
    fill = {"{area}": "kitchen", "{on_off_states:state}": "on",
            "{bs_door_states:state}": "open"}
    assert _normalise("is the kitchen light on") in _sentences_with(fill)
    assert _normalise("is there water in the kitchen") in _sentences_with(fill)
    fill["{area}"] = "front door"
    assert _normalise("is the front door open") in _sentences_with(fill)
    fill["{area}"] = "family room"
    assert _normalise("what is the temperature in the family room") in _sentences_with(fill)
    fill["{area}"] = "bedroom"
    assert _normalise("whats the humidity in the bedroom") in {s.replace("what s", "whats")
                                                              for s in _sentences_with(fill)}
    assert _normalise("what is the thermostat set to") in _sentences_with(fill)


def _render(template: str, **context) -> str:
    import jinja2
    env = jinja2.Environment()

    def is_number(value) -> bool:
        try:
            float(value)
            return True
        except (TypeError, ValueError):
            return False

    env.filters["is_number"] = is_number
    env.globals["state_attr"] = context.pop("state_attr", lambda *_: None)
    return " ".join(env.from_string(template).render(**context).split())


class _State:
    def __init__(self, state: str, unit: str = "°C") -> None:
        self.state = state
        self.attributes = {"unit_of_measurement": unit}


def test_a_room_reading_is_the_average_of_its_sensors_in_words() -> None:
    template = _status()["responses"]["intents"]["HassGetState"]["room_reading"]
    query = {"matched": [_State("21.2"), _State("22.1"), _State("unavailable"), _State("22.4")]}
    assert _render(template, query=query) == "21.9 degrees, across 3 sensors"
    assert _render(template, query={"matched": [_State("57", "%")]}) == "57.0 percent"
    assert _render(template, query={"matched": [_State("unavailable")]}) == \
        "I don't have a reading for that right now"


def test_the_thermostat_answer_is_its_target_not_the_room_temperature() -> None:
    template = _status()["responses"]["intents"]["HassClimateGetTemperature"]["target"]

    class Climate:
        entity_id = "climate.my_ecobee"

    attrs = {"temperature": 17.0}
    assert _render(template, state=Climate(), state_attr=lambda _e, key: attrs.get(key)) == \
        "The thermostat is set to 17.0 degrees"
    attrs = {"temperature": None, "target_temp_low": 18, "target_temp_high": 24}
    assert _render(template, state=Climate(), state_attr=lambda _e, key: attrs.get(key)) == \
        "The thermostat is set between 18 and 24 degrees"


def test_sentences_are_written_only_with_apply(tmp_path) -> None:
    assert voice.ensure_custom_sentences(tmp_path, apply=False)
    assert not (tmp_path / "custom_sentences").exists()
    voice.ensure_custom_sentences(tmp_path, apply=True)
    assert (tmp_path / "custom_sentences" / "en" / SENTENCES_FILE.name).is_file()
    assert voice.ensure_custom_sentences(tmp_path, apply=True) == []
