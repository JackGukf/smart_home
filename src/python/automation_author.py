"""Draft a Home Assistant automation from a sentence, using the local LLM.

This is the shape the model is actually good for: **the LLM authors, rules
execute.**  Qwen drafts the automation once, where taking twenty seconds does
not matter and a human reads the result before it does anything.  Home
Assistant then runs it deterministically forever after.  The model is never in
the trigger path -- it is slower and less reliable than the rule it would
replace.

Three things keep this honest:

* **Drafting never installs anything.**  `draft_automation` returns a proposal;
  putting it in the house is a separate, explicit act.
* **The entity list comes from Home Assistant**, not from the model's
  imagination.  Entity ids are the thing an LLM invents most readily, so the
  relevant ones are put in the prompt and everything it emits is checked back
  against the real list.
* **The output is grammar-constrained** to a JSON schema by Ollama's `format`,
  so it cannot ramble.  Qwen3 reasons before answering, and on a free-form call
  that reasoning lands in the answer; a schema leaves no room for it.

This module holds the drafting itself so that both callers can share it:
`scripts/author_automation.py` at the command line, and the dashboard's
/api/automations endpoints.  It talks to Home Assistant and Ollama over
loopback, so it only works on the board.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Defaults shared by both callers - the CLI and the dashboard - so a change
# here does not have to be made twice.
DEFAULT_MODEL = "qwen3:4b-house"
DEFAULT_ENDPOINT = "http://127.0.0.1:11434/api/chat"
DEFAULT_ENTITIES = 25       # more crowds the context and buries the relevant ones
DEFAULT_RETRIES = 2
DEFAULT_TIMEOUT = 180.0


class AuthorError(Exception):
    """Anything that stops a draft being produced."""


class NoCandidateEntities(AuthorError):
    """Nothing in the house matched the request, so there is nothing to draft with."""

    def __init__(self, request: str) -> None:
        super().__init__(f"no entities matched {request!r}")
        self.request = request


class EmptyModelResponse(AuthorError):
    """The model returned no content. The two causes need different fixes."""


# Domains worth acting on. Used to bias entity selection towards things an
# automation can actually do something with, rather than 75 diagnostic sensors.
ACTIONABLE = ("light", "switch", "climate", "fan", "cover", "media_player", "scene", "script")

STEP_DATA = {
    "type": "object",
    "properties": {
        "brightness_pct": {"type": "integer"},
        "temperature": {"type": "number"},
        "hvac_mode": {"type": "string"},
        "color_temp_kelvin": {"type": "integer"},
        "message": {"type": "string"},
        "title": {"type": "string"},
    },
}

AUTOMATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["alias", "triggers", "actions"],
    "properties": {
        "alias": {"type": "string"},
        "description": {"type": "string"},
        "mode": {"type": "string", "enum": ["single", "restart", "queued", "parallel"]},
        "triggers": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["trigger"],
                "properties": {
                    "trigger": {"type": "string",
                                "enum": ["state", "numeric_state", "time", "sun", "homeassistant"]},
                    "entity_id": {"type": "string"},
                    "from": {"type": "string"},
                    "to": {"type": "string"},
                    "above": {"type": "number"},
                    "below": {"type": "number"},
                    "for": {"type": "string"},
                    "at": {"type": "string"},
                    "event": {"type": "string", "enum": ["sunrise", "sunset"]},
                    "offset": {"type": "string"},
                },
            },
        },
        "conditions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["condition"],
                "properties": {
                    "condition": {"type": "string",
                                  "enum": ["state", "numeric_state", "time", "sun"]},
                    "entity_id": {"type": "string"},
                    "state": {"type": "string"},
                    "above": {"type": "number"},
                    "below": {"type": "number"},
                    "after": {"type": "string"},
                    "before": {"type": "string"},
                },
            },
        },
        "actions": {
            "type": "array",
            "items": {
                # A step is either a service call or a wait. `delay` is a step
                # key in Home Assistant, not a service -- asking for "for five
                # minutes" makes the model reach for `action: delay`, which
                # loads and then silently does nothing. Neither key is required
                # by the schema; exactly one is required by validate().
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "entity_id": {"type": "string"},
                    "data": STEP_DATA,
                    "delay": {"type": "string"},
                },
            },
        },
    },
}


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def ha_get(base_url: str, token: str, path: str, timeout: float = 15.0) -> Any:
    request = Request(f"{base_url.rstrip('/')}{path}",
                      headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def words(text: str) -> set[str]:
    return {w for w in re.split(r"[^a-z0-9]+", text.lower()) if len(w) > 2}


def select_entities(states: list[dict], request: str, limit: int) -> list[dict]:
    """Put the entities the request is plausibly about in front of the model.

    All 211 of them would crowd a 4096-token context and bury the relevant ones.
    Lexical overlap is crude but works here, because home entities are named
    after the rooms and things people say.
    """
    wanted = words(request)
    scored = []
    for state in states:
        entity_id = state["entity_id"]
        domain = entity_id.split(".")[0]
        name = state.get("attributes", {}).get("friendly_name") or ""
        haystack = words(entity_id) | words(name)
        # 'unavailable' means the thing is not there -- no automation can act on
        # it, and offering it only invites the model to pick it. Excluded
        # outright rather than penalised, because a close name match will
        # out-score any penalty. 'unknown' is different: the entity exists and
        # simply has not reported yet, so it stays, ranked lower.
        if state.get("state") == "unavailable":
            continue
        score = len(wanted & haystack) * 3
        if domain in ACTIONABLE:
            score += 1
        if state.get("state") == "unknown":
            score -= 2
        if score > 0:
            scored.append((score, entity_id, state))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [state for _, _, state in scored[:limit]]


def describe(state: dict) -> str:
    attrs = state.get("attributes", {})
    name = attrs.get("friendly_name") or state["entity_id"]
    device_class = attrs.get("device_class")
    unit = attrs.get("unit_of_measurement")
    bits = [f"{state['entity_id']}", f'"{name}"', f"= {state.get('state')}"]
    if device_class:
        bits.append(f"class={device_class}")
    if unit:
        bits.append(f"unit={unit}")
    return "  " + " ".join(bits)


def allowed_services(services: list[dict], entities: list[dict]) -> list[str]:
    domains = {e["entity_id"].split(".")[0] for e in entities} | {"notify"}
    out = []
    for entry in services:
        if entry["domain"] in domains:
            out += [f"{entry['domain']}.{name}" for name in entry["services"]]
    return sorted(out)


def call_ollama(endpoint: str, model: str, messages: list[dict], timeout: float) -> dict:
    payload = {
        "model": model,
        "stream": False,
        "format": AUTOMATION_SCHEMA,
        # Qwen3 reasons before answering and the reasoning is charged to the same
        # token budget, so a schema this size returns an EMPTY answer without
        # this: the budget is spent thinking before any JSON is emitted. Safe to
        # disable here precisely because `format` grammar-constrains the output --
        # on a free-form call, think:false instead dumps the reasoning into the
        # answer. See docs/local-ai.md.
        "think": False,
        # Deterministic: the same sentence should give the same automation.
        "options": {"temperature": 0, "num_predict": 1500},
        "messages": messages,
    }
    request = Request(endpoint, data=json.dumps(payload).encode("utf-8"),
                      headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        body = json.loads(response.read().decode("utf-8"))
    content = (body.get("message") or {}).get("content") or ""
    if not content.strip():
        # Say which of the two causes it was, rather than making the next person guess.
        raise EmptyModelResponse(
            f"the model returned empty content "
            f"(done_reason={body.get('done_reason')}, generated={body.get('eval_count')} tokens, "
            f"prompt={body.get('prompt_eval_count')} tokens).\n"
            f"  done_reason=length means the budget ran out: raise num_predict.\n"
            f"  Otherwise the prompt is probably too big for the context window; "
            f"lower --entities."
        )
    return json.loads(content)


def collect_entity_ids(automation: dict) -> list[tuple[str, str]]:
    found = []
    for section in ("triggers", "conditions", "actions"):
        for index, step in enumerate(automation.get(section) or []):
            value = step.get("entity_id")
            for one in ([value] if isinstance(value, str) else (value or [])):
                found.append((f"{section}[{index}]", one))
    return found


def validate(automation: dict, valid_entities: set[str], valid_services: set[str]) -> list[str]:
    """Check the draft against what this Home Assistant actually has.

    An invented entity_id is the failure that looks most like success: the
    automation loads, and simply never fires.
    """
    problems = []
    if not (automation.get("triggers") or []):
        problems.append("no triggers - the automation would never fire")
    if not (automation.get("actions") or []):
        problems.append("no actions - the automation would do nothing")

    # Trigger shape. The model reaches for a time trigger to express "after
    # sunset", which is both the wrong construct -- that is a condition, or the
    # automation fires at sunset regardless of the real trigger -- and an invalid
    # one, since a time trigger takes a clock time.
    for index, step in enumerate(automation.get("triggers") or []):
        kind = step.get("trigger")
        if kind == "time":
            at = step.get("at")
            if not at or not re.fullmatch(r"\d{1,2}:\d{2}(:\d{2})?", at):
                problems.append(
                    f"triggers[{index}]: time trigger needs at=HH:MM:SS, got {at!r}"
                    + (" -- for sunset use a sun trigger, or a sun condition if it is a"
                       " restriction rather than the thing that fires it" if at in ("sunset", "sunrise") else "")
                )
        elif kind == "sun" and step.get("event") not in ("sunrise", "sunset"):
            problems.append(f"triggers[{index}]: sun trigger needs event=sunrise or sunset")
        if kind == "state" and step.get("from") is not None and step.get("from") == step.get("to"):
            # Reached for when a numeric threshold was meant. It loads happily
            # and never fires, which is the worst way for this to be wrong.
            problems.append(
                f"triggers[{index}]: state trigger has from == to ({step.get('from')!r}), so it can "
                f"never fire -- for a numeric threshold use a numeric_state trigger with above/below")
        elif kind in ("state", "numeric_state") and not step.get("entity_id"):
            problems.append(f"triggers[{index}]: {kind} trigger needs an entity_id")
        if kind == "numeric_state" and step.get("above") is None and step.get("below") is None:
            problems.append(f"triggers[{index}]: numeric_state trigger needs above or below")
        for key in ("for", "offset"):
            value = step.get(key)
            if value and not re.fullmatch(r"-?\d{1,2}:\d{2}(:\d{2})?", value):
                problems.append(f"triggers[{index}]: {key}={value!r} is not HH:MM:SS")

    for where, entity_id in collect_entity_ids(automation):
        if entity_id not in valid_entities:
            problems.append(f"{where}: entity_id '{entity_id}' does not exist in Home Assistant")

    for index, step in enumerate(automation.get("actions") or []):
        service, delay = step.get("action"), step.get("delay")
        if service and delay:
            problems.append(f"actions[{index}]: has both 'action' and 'delay'; a step is one or the other")
        elif not service and not delay:
            problems.append(f"actions[{index}]: neither 'action' nor 'delay'")
        elif service and service not in valid_services:
            problems.append(f"actions[{index}]: service '{service}' does not exist")
        elif delay and not re.fullmatch(r"\d{1,2}:\d{2}(:\d{2})?", delay):
            problems.append(f"actions[{index}]: delay '{delay}' is not HH:MM:SS")
        # data belongs to a service call; on a delay step it is meaningless and
        # the model fills it with whatever the schema offered.
        if delay and step.get("data"):
            problems.append(f"actions[{index}]: a delay step must not carry 'data'")
    return problems


def review_hints(request: str, automation: dict) -> list[str]:
    """Flag likely omissions -- things the request asked for that the draft lacks.

    Validation proves the automation is well formed and refers to real things.
    It cannot prove the automation means what you asked, and a 4B model reliably
    drops parts of a compound request: the sunset restriction, the turn-off, or
    the difference between five minutes and five seconds. These are warnings for
    a human, never failures, because judging intent is exactly the part that is
    not mechanical.
    """
    hints: list[str] = []
    lowered = request.lower()
    blob = json.dumps(automation).lower()

    triggers = automation.get("triggers") or []
    has_time_trigger = any(t.get("trigger") in ("time", "sun") for t in triggers)
    if any(w in lowered for w in ("sunset", "sunrise", "night", "evening", "dark", "morning")):
        # Only a concern when the time is a *restriction* on some other trigger.
        # If the automation already fires on time or sun, it is handled.
        if '"condition"' not in blob and not has_time_trigger:
            hints.append("the request mentions a time of day, but the draft has no condition - "
                         "check it is not firing around the clock")

    match = re.search(r"(\d+)\s*(second|minute|hour)", lowered)
    if match:
        count, unit = int(match.group(1)), match.group(2)
        expected = {"second": f"00:00:{count:02d}", "minute": f"00:{count:02d}:00",
                    "hour": f"{count:02d}:00:00"}[unit]
        if expected not in blob:
            hints.append(f"the request says {count} {unit}(s) (= {expected}), which does not "
                         f"appear in the draft - check any delay or 'for' duration")

    threshold = re.search(r"(above|below|over|under|more than|less than|greater than)\s+(\d+)", lowered)
    if threshold and not any(
        t.get("trigger") == "numeric_state" and (t.get("above") is not None or t.get("below") is not None)
        for t in triggers
    ):
        hints.append(f"the request sets a threshold ({threshold.group(0)}) but the draft has no "
                     f"numeric_state trigger with above/below - it may never fire")

    wants_off = any(w in lowered for w in ("for ", "then off", "turn off", "switch off"))
    if wants_off and "turn_off" not in blob:
        hints.append("the request implies turning something off again, but no turn_off action "
                     "is present")

    if len(automation.get("actions") or []) > 1:
        first = (automation.get("actions") or [])[0]
        if first.get("delay"):
            hints.append("the first action is a delay, so nothing happens until it elapses - "
                         "check the ordering is what you meant")
    return hints


@dataclass
class Draft:
    """One drafting run, whatever the outcome.

    `problems` are mechanical: an entity or service that does not exist, or an
    automation that cannot fire. A draft with any is not fit to install.
    `hints` are heuristics about intent -- warnings, never blockers, because a
    false positive must not be able to veto a correct automation.
    """

    request: str
    automation: dict
    yaml_text: str
    problems: list[str]
    hints: list[str]
    attempts: int
    elapsed: float
    entities_shown: int

    @property
    def ok(self) -> bool:
        return not self.problems

    def as_dict(self) -> dict:
        return {
            "request": self.request,
            "automation": self.automation,
            "yaml": self.yaml_text,
            "problems": self.problems,
            "hints": self.hints,
            "attempts": self.attempts,
            "elapsed": round(self.elapsed, 1),
            "entities_shown": self.entities_shown,
            "ok": self.ok,
            "slug": self.slug(),
        }

    def slug(self) -> str:
        alias = (self.automation.get("alias") or "automation").lower()
        return re.sub(r"[^a-z0-9]+", "-", alias).strip("-")[:60] or "automation"


def build_system_prompt(candidates: list[dict], service_names: list[str]) -> str:
    """The rules here are the mistakes this model actually made, one line each."""
    return (
        "You write Home Assistant automations. Use ONLY the entity_ids listed "
        "below, exactly as written -- never invent one, and never guess at a "
        "name that is not listed. Use ONLY the listed services.\n"
        "Rules:\n"
        "- A threshold on a measured value (above/below a number) is a "
        "numeric_state trigger with above or below. Never express it as a state "
        "trigger with from and to -- that can never fire.\n"
        "- Use state triggers for binary sensors and switches, with from/to being "
        "different values such as 'off' and 'on'.\n"
        "- To wait, emit an action step with only {\"delay\": \"00:05:00\"} in "
        "HH:MM:SS. There is no 'delay' service, and a delay step takes no data.\n"
        "- A trigger is what makes the automation fire. A restriction like "
        "\"after sunset\", \"at night\" or \"only on weekdays\" is a CONDITION, "
        "never a trigger -- adding it as a trigger makes the automation also fire "
        "at that time on its own. Use {\"condition\": \"sun\", \"after\": "
        "\"sunset\"} or a time condition.\n"
        "- A time trigger takes a clock time as at=HH:MM:SS. It cannot take "
        "\"sunset\".\n"
        "- Only put data on a service call, and only fields that service accepts.\n"
        "- Give the automation a short descriptive alias.\n\n"
        "Entities:\n" + "\n".join(describe(s) for s in candidates) +
        "\n\nServices:\n  " + ", ".join(service_names)
    )


def draft_automation(
    request: str,
    states: list[dict],
    services: list[dict],
    *,
    model: str = DEFAULT_MODEL,
    endpoint: str = DEFAULT_ENDPOINT,
    entities: int = DEFAULT_ENTITIES,
    retries: int = DEFAULT_RETRIES,
    timeout: float = DEFAULT_TIMEOUT,
    progress: Callable[[str], None] | None = None,
) -> Draft:
    """Draft one automation. Raises NoCandidateEntities if nothing matches.

    Network errors from Ollama or Home Assistant propagate to the caller, which
    knows how it wants to report them.
    """
    say = progress or (lambda _message: None)

    candidates = select_entities(states, request, entities)
    if not candidates:
        raise NoCandidateEntities(request)
    service_names = allowed_services(services, candidates)

    system = build_system_prompt(candidates, service_names)
    valid_entities = {s["entity_id"] for s in states}
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": request}]

    # The validator produces exact, mechanical errors -- "that entity does not
    # exist", "a time trigger cannot take sunset" -- which is precisely the kind
    # of feedback a small model can act on. Handing them back is far more
    # effective than trying to prevent every mistake in the prompt, and it keeps
    # the deterministic checker as the arbiter rather than the model.
    started = time.time()
    automation: dict = {}
    problems: list[str] = []
    hints: list[str] = []
    attempts = 0

    for attempt in range(1 + retries):
        attempts = attempt + 1
        say(f"asking {model}..." if attempt == 0
            else f"asking again with {len(problems)} validation error(s) "
                 f"(attempt {attempts})")
        automation = call_ollama(endpoint, model, messages, timeout)
        problems = validate(automation, valid_entities, set(service_names))
        hints = review_hints(request, automation)
        if not problems and not hints:
            break
        if attempt == retries:
            break
        messages += [
            {"role": "assistant", "content": json.dumps(automation)},
            {"role": "user", "content":
                "That automation has problems:\n- " + "\n- ".join(problems + hints) +
                "\nReturn a corrected automation. Use only the entity_ids listed in the "
                "system message, copied exactly. Keep the original intent: " + request},
        ]

    import yaml

    yaml_text = yaml.safe_dump([automation], sort_keys=False, allow_unicode=True,
                               default_flow_style=False)
    return Draft(
        request=request,
        automation=automation,
        yaml_text=yaml_text,
        problems=problems,
        hints=hints,
        attempts=attempts,
        elapsed=time.time() - started,
        entities_shown=len(candidates),
    )


def render_proposal(draft: Draft, model: str = DEFAULT_MODEL) -> str:
    """The proposal file body: the YAML, and everything a reviewer needs above it."""
    return (
        f"# Drafted by the local LLM on {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"# Model: {model}\n"
        f"# Request: {draft.request}\n"
        f"# Every entity_id and service below was checked against this Home Assistant.\n"
        + "".join(f"# REVIEW HINT: {h}\n" for h in draft.hints) +
        f"# REVIEW IT, then install it. Nothing here is active until you do.\n\n"
        + draft.yaml_text
    )
