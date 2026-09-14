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


def test_sentences_are_written_only_with_apply(tmp_path) -> None:
    assert voice.ensure_custom_sentences(tmp_path, apply=False)
    assert not (tmp_path / "custom_sentences").exists()
    voice.ensure_custom_sentences(tmp_path, apply=True)
    assert (tmp_path / "custom_sentences" / "en" / SENTENCES_FILE.name).is_file()
    assert voice.ensure_custom_sentences(tmp_path, apply=True) == []
