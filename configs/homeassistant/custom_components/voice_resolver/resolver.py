"""Deterministic fallback for voice commands Home Assistant's matcher rejected.

Home Assistant's own matcher needs the exact device name. Whisper, on a small
model and a wall panel's microphone, does not hear exact names: on 2026-09-14
"turn on living room switch 2" arrived as "Turn on leaving room switch to" and
"Turn on leaving long switch too." Both got "not aware of any device called ...".

This runs only after the matcher has already failed. It repairs the transcript,
scores it against the devices exposed to voice by spelling, sound and words,
and then either acts (one clear winner), asks (a close call - the house owner
asked for "ask when unsure"), or says what it heard and what is closest.

No model and no Home Assistant imports: every decision is a pure function of
the transcript and the device list, so tests/python/test_voice_resolver.py can
pin it against real transcripts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

# Act only on a clear winner; ask when plausible; below that it is not a match.
ACT_SCORE = 0.84
ACT_MARGIN = 0.10
ASK_SCORE = 0.52
MAX_OPTIONS = 2

# Phrases Whisper actually produced for names in this house, and near kin.
MISHEARINGS = [
    (r"\bleaving long\b", "living room"),
    (r"\bliving long\b", "living room"),
    (r"\bleaving\b", "living"),
    (r"\bleave in\b", "living"),
    (r"\blivin\b", "living"),
    (r"\bbed room\b", "bedroom"),
    (r"\bfamily rooms?\b", "family room"),
    (r"\blite\b", "light"),
    (r"\bled\b", "led"),
]
# Number words that are only ever numbers.
NUMBERS = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
           "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10"}
# Sound-alikes that are numbers only at the end of a device name ("switch to").
TRAILING_NUMBERS = {"to": "2", "too": "2", "won": "1", "for": "4", "fore": "4", "ate": "8", "tree": "3"}
PLURALS = {"lights": "light", "switches": "switch", "lamps": "lamp", "plugs": "plug", "fans": "fan"}
FILLER = {"the", "a", "an", "my", "please", "now", "our"}
GENERIC_WORDS = {"room", "switch", "light", "lamp", "plug", "led", "socket", "outlet", "fan"}

ACTIONS = {"on": "turn_on", "off": "turn_off", "of": "turn_off"}
_COMMAND_PATTERNS = [
    # "turn on the kitchen light", "switch off ...", "put on ..."
    re.compile(r"^(?:(?:can|could|would) you |please )?(?:turn|switch|put) (on|off|of) (.+)$"),
    # "turn the kitchen light on"
    re.compile(r"^(?:(?:can|could|would) you |please )?(?:turn|switch|put) (.+) (on|off|of)$"),
]

YES = {"yes", "yeah", "yep", "yup", "sure", "correct", "right", "ok", "okay", "do it", "please",
       "yes please", "that one", "that s right", "thats right"}
NO = {"no", "nope", "cancel", "never mind", "nevermind", "stop", "forget it", "no thanks"}
ORDINALS = {"first": 0, "the first one": 0, "first one": 0, "one": 0, "1": 0,
            "second": 1, "the second one": 1, "second one": 1, "two": 1, "2": 1,
            "the other one": 1, "other one": 1}


@dataclass(frozen=True)
class Candidate:
    entity_id: str
    name: str
    aliases: tuple[str, ...] = ()
    area: str | None = None

    @property
    def domain(self) -> str:
        return self.entity_id.split(".", 1)[0]


@dataclass
class Decision:
    kind: str                      # act | ask | unknown | cancel | not_a_command | not_a_reply
    action: str | None = None      # turn_on | turn_off
    heard: str = ""
    target: Candidate | None = None
    options: list[Candidate] = field(default_factory=list)


def _clean(text: str) -> str:
    text = text.lower().replace("’", "'")
    text = re.sub(r"'s\b", "", text)
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def normalise_name(text: str) -> str:
    """The form both transcripts and device names are compared in."""
    text = _clean(text)
    for pattern, replacement in MISHEARINGS:
        text = re.sub(pattern, replacement, text)
    words = [PLURALS.get(w, NUMBERS.get(w, w)) for w in text.split()]
    if words and words[-1] in TRAILING_NUMBERS:
        words[-1] = TRAILING_NUMBERS[words[-1]]
    text = " ".join(w for w in words if w not in FILLER)
    # "stick s three" -> "stick s 3" -> "stick s3", the form the name is written in.
    return re.sub(r"\b([a-z]) (\d+)\b", r"\1\2", text)


def parse_command(text: str) -> tuple[str, str] | None:
    """(service, target phrase) for an on/off command, else None."""
    cleaned = _clean(text)
    for pattern in _COMMAND_PATTERNS:
        match = pattern.match(cleaned)
        if not match:
            continue
        if pattern is _COMMAND_PATTERNS[0]:
            state, target = match.group(1), match.group(2)
        else:
            target, state = match.group(1), match.group(2)
        target = normalise_name(target)
        if target:
            return ACTIONS[state], target
    return None


def _skeleton(text: str) -> str:
    """Consonant outline, so "leaving" and "living" look alike."""
    return re.sub(r"(.)\1+", r"\1", re.sub(r"[aeiouy\s]", "", text))


def score(query: str, key: str) -> float:
    if not query or not key:
        return 0.0
    if query == key:
        return 1.0
    chars = SequenceMatcher(None, query, key).ratio()
    sound = SequenceMatcher(None, _skeleton(query), _skeleton(key)).ratio()
    query_words, key_words = set(query.split()), set(key.split())
    words = len(query_words & key_words) / max(len(query_words), len(key_words))
    value = 0.45 * chars + 0.25 * sound + 0.30 * words
    # A word that tells devices apart ("living") missing from the name counts
    # against it; shared generic words ("room switch") must not make "living
    # room switch" look like "family room switch".
    distinctive_missing = {w for w in query_words - key_words if w not in GENERIC_WORDS and not w.isdigit()}
    value -= 0.15 * min(len(distinctive_missing), 2)
    query_numbers = {w for w in query_words if w.isdigit()}
    key_numbers = {w for w in key_words if w.isdigit()}
    if key_numbers and query_numbers and key_numbers != query_numbers:
        value -= 0.40          # "switch 3" is never "switch 2"
    elif key_numbers and not query_numbers:
        value -= 0.12          # probably it, but ask
    elif query_numbers and not key_numbers:
        value -= 0.25
    return max(0.0, min(1.0, value))


def _best_score(query: str, candidate: Candidate) -> float:
    # Home Assistant 2026 keeps a non-string placeholder among aliases; a crash
    # here turned every missed command into "unknown_error" on first deploy.
    keys = [k for k in (candidate.name, *candidate.aliases) if isinstance(k, str) and k.strip()]
    return max((score(query, normalise_name(k)) for k in keys), default=0.0)


def rank(query: str, candidates: list[Candidate]) -> list[tuple[float, Candidate]]:
    scored = [(_best_score(query, c), c) for c in candidates]
    return sorted(scored, key=lambda pair: (-pair[0], pair[1].name))


def resolve(text: str, candidates: list[Candidate]) -> Decision:
    parsed = parse_command(text)
    if parsed is None:
        return Decision("not_a_command", heard=text.strip())
    action, target = parsed
    ranked = rank(target, candidates)
    if not ranked or ranked[0][0] < ASK_SCORE:
        near = [c for s, c in ranked[:MAX_OPTIONS] if s >= 0.35]
        return Decision("unknown", action=action, heard=target, options=near)
    top_score, top = ranked[0]
    runner_up = ranked[1][0] if len(ranked) > 1 else 0.0
    if top_score >= ACT_SCORE and top_score - runner_up >= ACT_MARGIN:
        return Decision("act", action=action, heard=target, target=top)
    options = [c for s, c in ranked[:MAX_OPTIONS] if s >= ASK_SCORE and top_score - s < ACT_MARGIN] or [top]
    return Decision("ask", action=action, heard=target, options=options)


def resolve_reply(text: str, pending: Decision) -> Decision:
    """Interpret the answer to "Did you mean ...?"."""
    reply = _clean(text)
    if parse_command(text) is not None:
        return Decision("not_a_reply", heard=reply)      # a new command: start over
    if reply in NO:
        return Decision("cancel", action=pending.action, heard=reply)
    options = pending.options
    if reply in YES and len(options) == 1:
        return Decision("act", action=pending.action, heard=reply, target=options[0])
    if reply in ORDINALS and ORDINALS[reply] < len(options) and len(options) > 1:
        return Decision("act", action=pending.action, heard=reply, target=options[ORDINALS[reply]])
    if reply in YES:
        return Decision("ask", action=pending.action, heard=reply, options=options)
    ranked = rank(normalise_name(reply), options)
    if ranked and ranked[0][0] >= 0.45:
        return Decision("act", action=pending.action, heard=reply, target=ranked[0][1])
    return Decision("not_a_reply", heard=reply)


def _names(options: list[Candidate]) -> str:
    names = [c.name for c in options]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " or " + names[-1]


def speech(decision: Decision) -> str:
    verb = "on" if decision.action == "turn_on" else "off"
    if decision.kind == "act":
        return f"Turned {verb} {decision.target.name}."
    if decision.kind == "ask":
        if len(decision.options) > 1 and decision.heard in YES:
            return f"Which one: {_names(decision.options)}?"
        return f"Did you mean {_names(decision.options)}?"
    if decision.kind == "cancel":
        return "Okay, never mind."
    if decision.kind == "unknown":
        if decision.options:
            return f"I heard {decision.heard}. Did you mean {_names(decision.options)}?"
        return f"I heard {decision.heard}, but no device has a name like that."
    return ""
