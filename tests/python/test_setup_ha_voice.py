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
