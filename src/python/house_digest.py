"""A morning digest of the house, written by the local model from computed facts.

This is the shape a slow local model is actually good at: a batch job at 4am
with no latency budget, where twenty seconds of thinking costs nothing and
nobody is waiting.

The division of labour is the point, and it is the opposite of the usual one:

    Python computes every number. The model only writes the sentences.

So the model is never asked "how many times did the front door open" - it is
handed "front_door: 11 opens, 14-day average 4.2" and asked to say that in
English. It cannot be wrong about a figure it did not calculate, which turns
its unreliability from a correctness problem into a style problem. The facts
are kept alongside the prose in the digest file for exactly this reason: if a
sentence looks wrong, the numbers it came from are right there.

If Ollama is down or slow the digest is still produced, with the facts and no
prose. A digest that says less is far better than no digest, and this way the
morning report does not depend on the least reliable component in it.
"""

from __future__ import annotations

import json
import re
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

# A day, and the fortnight before it to compare against. The motion log keeps
# 14 days, so the baseline is everything it has that is not today.
WINDOW_HOURS = 24
BASELINE_DAYS = 13

# Below this, a battery is worth mentioning before it dies rather than after.
BATTERY_WARN_PERCENT = 50

# States that mean "this entity is not telling us anything".
DEAD_STATES = frozenset({"unavailable", "unknown"})


def is_camera_sighting(entity_id: str) -> bool:
    """Did this come from the NPU camera detector rather than a PIR sensor?

    They arrive on the same feed and share a device_class, but they are not the
    same evidence: a PIR says something warm moved, a camera says it recognised
    a person. Worth keeping apart in a briefing.
    """
    return "_npu_" in str(entity_id or "").lower()


def camera_name(name: str) -> str:
    """"Office Camera (NPU) Person" -> "the office camera"."""
    cleaned = str(name or "").replace("(NPU)", "").replace("Person", "").strip()
    cleaned = " ".join(cleaned.split()).lower()
    if not cleaned:
        return "a camera"
    return f"the {cleaned}"

class EmptySummary(RuntimeError):
    """The model answered, with nothing in it."""


DEFAULT_MODEL = "qwen3:4b-house"
DEFAULT_ENDPOINT = "http://127.0.0.1:11434/api/chat"

# Kept short and role-only. With the schema below, a long list of rules in the
# system turn is something the model will happily paraphrase back into the
# `summary` field instead of using the data - which is exactly what it did on
# the first attempt.
SYSTEM_PROMPT = (
    "You write the morning briefing for the person who lives in this house. "
    "You are given figures that have already been computed: report them, never "
    "recalculate them, and never mention a device or a number that is not in "
    "the input."
)

# The instruction rides with the data in the user turn, so the model is always
# answering about the figures rather than about the task.
USER_TEMPLATE = (
    "Notes from last night:\n{facts}\n\n"
    "Rewrite these notes as {sentences} short sentences of plain prose for the "
    "householder. Use every note, add nothing, and do not copy the wording."
)


@dataclass
class Facts:
    """Everything the digest knows, all of it computed here rather than by the model."""

    generated_at: float
    window_hours: int = WINDOW_HOURS
    motion: list[dict] = field(default_factory=list)
    batteries: list[dict] = field(default_factory=list)
    unavailable: dict = field(default_factory=dict)
    board: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)


def read_motion_events(path: Path, since: float) -> list[dict]:
    """Motion transitions at or after `since`. A malformed line is skipped, not fatal."""
    path = Path(path)
    if not path.is_file():
        return []
    events = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and float(event.get("ts", 0)) >= since:
            events.append(event)
    return events


def motion_summary(events: list[dict], now: float, window_hours: int = WINDOW_HOURS,
                   baseline_days: int = BASELINE_DAYS) -> list[dict]:
    """Per sensor: activity in the window, against its own average day before it.

    Each sensor is compared with itself rather than with the other sensors,
    because a hallway and a spare room have nothing to say about each other.
    """
    window_start = now - window_hours * 3600
    baseline_start = window_start - baseline_days * 86400

    recent: dict[str, int] = defaultdict(int)
    recent_seconds: dict[str, float] = defaultdict(float)
    baseline: dict[str, int] = defaultdict(int)
    names: dict[str, str] = {}

    for event in events:
        entity_id = event.get("entity_id")
        if not entity_id:
            continue
        names[entity_id] = event.get("name") or entity_id
        timestamp = float(event.get("ts", 0))
        if event.get("state") == "on":
            if timestamp >= window_start:
                recent[entity_id] += 1
            elif timestamp >= baseline_start:
                baseline[entity_id] += 1
        elif timestamp >= window_start:
            recent_seconds[entity_id] += float(event.get("duration_s") or 0)

    # How much history there actually is before the window. The motion log was
    # only added recently, so for a while there is no "normal" to compare with
    # - and reporting an average of 0.0/day would be a fabricated baseline
    # that makes a busy night look like an anomaly and a quiet one look fine.
    earliest = min((float(e.get("ts", 0)) for e in events if e.get("ts")), default=window_start)
    baseline_span_days = max(0.0, (window_start - earliest) / 86400)
    has_baseline = baseline_span_days >= 1

    summary = []
    for entity_id, name in sorted(names.items(), key=lambda item: item[1]):
        average = (round(baseline[entity_id] / baseline_span_days, 1)
                   if has_baseline else None)
        summary.append({
            "entity_id": entity_id,
            "name": name,
            "events": recent[entity_id],
            "active_minutes": round(recent_seconds[entity_id] / 60, 1),
            "daily_average": average,
            "baseline_days": round(baseline_span_days, 1),
            "camera": is_camera_sighting(entity_id),
            # Only claimed when there is a baseline to claim it against: a
            # sensor logged since yesterday has no normal yet.
            "unusual": bool(average is not None and average >= 1
                            and (recent[entity_id] >= average * 2
                                 or recent[entity_id] <= average / 3)),
        })
    return summary


def battery_report(states: list[dict], threshold: int = BATTERY_WARN_PERCENT) -> list[dict]:
    """Batteries below the threshold, worst first."""
    low = []
    for state in states:
        attributes = state.get("attributes", {})
        if attributes.get("device_class") != "battery":
            continue
        if not state.get("entity_id", "").startswith("sensor."):
            continue
        try:
            percent = float(state.get("state"))
        except (TypeError, ValueError):
            continue
        if percent <= threshold:
            low.append({
                "name": attributes.get("friendly_name") or state["entity_id"],
                "entity_id": state["entity_id"],
                "percent": round(percent),
            })
    low.sort(key=lambda item: item["percent"])
    return low


def unavailable_report(states: list[dict], ignore: frozenset[str] = frozenset()) -> dict:
    """What is not reporting, grouped rather than listed.

    Forty-nine dead entity ids is not a fact anybody can act on; "3 devices,
    one of them the doorbell" is. So this counts them and names the devices.
    """
    by_device: dict[str, list[str]] = defaultdict(list)
    for state in states:
        entity_id = state.get("entity_id", "")
        if entity_id in ignore or state.get("state") not in DEAD_STATES:
            continue
        name = state.get("attributes", {}).get("friendly_name") or entity_id
        # Entities of one device share a name prefix, and the device is the
        # useful unit here rather than its fifteen diagnostic sensors. Two
        # words, not one: this house has "Motion sensor and TH bedroom" next to
        # "Motion sensor and illumination", and one word collapses every
        # unrelated sensor in the house into a single bogus "Motion" device.
        by_device[" ".join(name.split()[:2]) or name].append(entity_id)

    devices = sorted(by_device.items(), key=lambda item: (-len(item[1]), item[0]))
    return {
        "entities": sum(len(ids) for _, ids in devices),
        "devices": len(devices),
        "worst": [{"device": device, "entities": len(ids)} for device, ids in devices[:5]],
    }


_RESOURCE_LINE = re.compile(
    r"^(?P<stamp>\S+)\s+mem_used=(?P<used>\d+)M\s+avail=(?P<avail>\d+)M\s+"
    r"load=(?P<load>[\d.]+)/[\d.]+\s+temp=(?P<temp>\d+)C")


def board_report(path: Path, since: float) -> dict:
    """Memory low-water mark, peak temperature and load, and any reboots.

    The resource logger writes a BOOT marker on start, so a reboot the house
    did not notice still shows up in the morning.
    """
    path = Path(path)
    if not path.is_file():
        return {}

    min_avail: int | None = None
    max_temp: int | None = None
    max_load: float | None = None
    boots = 0
    samples = 0

    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "BOOT" in line:
            stamp = line.split(" ", 1)[0]
            if _timestamp(stamp) >= since:
                boots += 1
            continue
        match = _RESOURCE_LINE.match(line)
        if not match or _timestamp(match.group("stamp")) < since:
            continue
        samples += 1
        avail = int(match.group("avail"))
        temp = int(match.group("temp"))
        load = float(match.group("load"))
        min_avail = avail if min_avail is None else min(min_avail, avail)
        max_temp = temp if max_temp is None else max(max_temp, temp)
        max_load = load if max_load is None else max(max_load, load)

    if not samples:
        return {}
    return {"samples": samples, "min_available_mb": min_avail,
            "max_temp_c": max_temp, "peak_load": max_load, "reboots": boots}


def _timestamp(stamp: str) -> float:
    """Parse the logger's ISO stamp. An unparseable line is treated as ancient."""
    try:
        from datetime import datetime
        return datetime.fromisoformat(stamp).timestamp()
    except (ValueError, TypeError):
        return 0.0


def facts_to_prompt(facts: Facts) -> str:
    """Render the facts as the flat, unambiguous text the model is asked to retell."""
    lines = [f"Window: the last {facts.window_hours} hours."]

    active = [entry for entry in facts.motion
              if (entry["events"] or entry["daily_average"]) and not entry["camera"]]
    cameras = [entry for entry in facts.motion if entry["camera"]]
    no_baseline = active and all(entry["daily_average"] is None for entry in active)
    if active:
        lines.append("\nMotion (times triggered, then this sensor's own daily average):")
        for entry in active:
            flag = "  <- unusual" if entry["unusual"] else ""
            average = (f"average {entry['daily_average']}/day"
                       if entry["daily_average"] is not None
                       else "no baseline yet")
            lines.append(f"  {entry['name']}: {entry['events']} times, "
                         f"{entry['active_minutes']} minutes active, "
                         f"{average}{flag}")
        if no_baseline:
            # Said plainly so the model does not imply a comparison it was
            # never given.
            lines.append("  (the motion log is too new to say what is normal, "
                         "so do not call any of this unusual)")
    else:
        lines.append("\nMotion: no sensors reported.")

    if cameras:
        lines.append("\nCameras (the NPU detector recognising a person, not a PIR trip):")
        for entry in cameras:
            lines.append(f"  {camera_name(entry['name'])}: {entry['events']} sightings, "
                         f"{entry['active_minutes']} minutes in view")

    if facts.batteries:
        lines.append("\nBatteries running low:")
        for entry in facts.batteries:
            lines.append(f"  {entry['name']}: {entry['percent']}%")
    else:
        lines.append("\nBatteries: none below the warning level.")

    dead = facts.unavailable
    if dead.get("entities"):
        worst = ", ".join(f"{item['device']} ({item['entities']})" for item in dead["worst"])
        lines.append(f"\nNot reporting: {dead['entities']} entities across "
                     f"{dead['devices']} devices. Most affected: {worst}.")

    board = facts.board
    if board:
        lines.append(f"\nBoard: lowest free memory {board['min_available_mb']} MB, "
                     f"peak temperature {board['max_temp_c']}C, "
                     f"peak load {board['peak_load']}, "
                     f"reboots {board['reboots']}.")
    return "\n".join(lines)


# Qwen3-4B could not do this job, and it is worth recording exactly how,
# because it refines a claim in docs/local-ai.md. Measured on this board:
#
#   1. free-form + think on   -> 3000 tokens generated, content EMPTY
#                                (done_reason=length: all of it was reasoning)
#   2. schema  + think off    -> it wrote its reasoning into `summary`
#   3. schema  + think on     -> 2500 tokens on a 206-token prompt, EMPTY again
#   4. schema  + think off,
#      with short notes       -> copied the notes back verbatim
#
# Two conclusions. "A schema makes think:false safe" holds only when the
# schema's fields are typed tightly enough to leave no room for prose, as in
# author_automation.py; a single free-text string accepts reasoning just as
# happily as an answer. And when the thing you want *is* prose, there is
# nothing left to constrain - the model reasons without bound about a task
# that needs none.
#
# So prose is off by default. The path below still works if a larger model
# ever runs here, and `headlines()` is the digest in the meantime.
SUMMARY_SCHEMA = {
    "type": "object",
    "required": ["summary"],
    "properties": {"summary": {"type": "string"}},
}



def headlines(facts: Facts) -> list[str]:
    """The few things worth saying, chosen here rather than by the model.

    Handing over the full fact sheet did not work: given ~500 tokens of tables
    and a permissive string schema, Qwen3-4B copied the input back verbatim
    instead of summarising it. With a handful of short notes there is nothing
    to copy and the job is unambiguous, which is the level a 4B model is
    reliable at.
    """
    notes: list[str] = []

    sensors = [e for e in facts.motion if not e["camera"]]
    cameras = [e for e in facts.motion if e["camera"]]

    busiest = sorted((entry for entry in sensors if entry["events"]),
                     key=lambda entry: -entry["events"])[:3]
    if busiest:
        notes += [f"{entry['name']} triggered {entry['events']} times"
                  + (f" (usually {entry['daily_average']} a day)"
                     if entry["daily_average"] is not None else "")
                  for entry in busiest]
    else:
        notes.append("no motion sensor triggered at all")

    # A camera saying it recognised a person is stronger evidence than a PIR
    # saying something warm moved, so it gets its own line rather than being
    # ranked among them.
    seen = sorted((entry for entry in cameras if entry["events"]),
                  key=lambda entry: -entry["events"])
    for entry in seen[:3]:
        notes.append(f"{camera_name(entry['name'])} saw someone {entry['events']} "
                     f"time{'' if entry['events'] == 1 else 's'}"
                     f" ({entry['active_minutes']} minutes in view)")
    if cameras and not seen:
        notes.append(f"no camera saw anyone ({len(cameras)} watching)")

    unusual = [entry["name"] for entry in facts.motion if entry["unusual"]]
    if unusual:
        notes.append("unusually busy: " + ", ".join(unusual[:3]))

    for entry in facts.batteries[:3]:
        notes.append(f"{entry['name']} is down to {entry['percent']} percent")

    dead = facts.unavailable
    if dead.get("entities"):
        worst = dead["worst"][0]["device"] if dead["worst"] else ""
        notes.append(f"{dead['entities']} entities on {dead['devices']} devices are "
                     f"not reporting, mostly {worst}")

    board = facts.board
    if board:
        notes.append(f"the board peaked at {board['max_temp_c']} degrees with "
                     f"{board['min_available_mb']} MB free at its lowest")
        if board.get("reboots"):
            notes.append(f"the board rebooted {board['reboots']} times")
    return notes


def summarise(facts_text: str, endpoint: str = DEFAULT_ENDPOINT,
              model: str = DEFAULT_MODEL, timeout: float = 300.0,
              sentences: int = 4) -> str:
    """Ask the model for the prose. Raises EmptySummary if it returns none."""
    payload = {
        "model": model,
        "stream": False,
        "format": SUMMARY_SCHEMA,
        "think": True,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_TEMPLATE.format(
                facts=facts_text, sentences=sentences)},
        ],
        # Covers the reasoning as well as the answer. The notes are short, so
        # this is generous rather than a limit that will be reached.
        "options": {"temperature": 0.2, "num_predict": 2500},
    }
    request = Request(endpoint, data=json.dumps(payload).encode("utf-8"),
                      headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        body = json.loads(response.read().decode("utf-8"))

    content = ((body.get("message") or {}).get("content") or "").strip()
    if content:
        # The schema means content is a JSON object, not the sentence itself.
        try:
            content = str(json.loads(content).get("summary") or "").strip()
        except (json.JSONDecodeError, AttributeError):
            content = ""
    if not content:
        # An empty answer is the one failure that looks like success, so say
        # which of the two causes it was instead of writing a blank digest.
        raise EmptySummary(
            f"the model returned no content (done_reason={body.get('done_reason')}, "
            f"generated={body.get('eval_count')} tokens, "
            f"prompt={body.get('prompt_eval_count')} tokens). "
            f"done_reason=length means the budget ran out mid-answer: raise "
            f"num_predict. Anything else usually means the prompt outgrew the "
            f"context window.")
    return content


def gather_facts(states: list[dict], motion_log: Path, resource_log: Path,
                 now: float | None = None, window_hours: int = WINDOW_HOURS,
                 ignore_unavailable: frozenset[str] = frozenset()) -> Facts:
    now = time.time() if now is None else now
    since = now - window_hours * 3600
    events = read_motion_events(motion_log, since - BASELINE_DAYS * 86400)
    return Facts(
        generated_at=now,
        window_hours=window_hours,
        motion=motion_summary(events, now, window_hours),
        batteries=battery_report(states),
        unavailable=unavailable_report(states, ignore_unavailable),
        board=board_report(resource_log, since),
    )


def build_digest(facts: Facts, endpoint: str = DEFAULT_ENDPOINT,
                 model: str = DEFAULT_MODEL, timeout: float = 300.0,
                 with_prose: bool = False) -> dict:
    """The digest: the notes, and the model's prose only if it is asked for.

    `with_prose` defaults to False because on this board it does not currently
    earn its place. Qwen3-4B was given this exact job four ways and failed all
    four - see the note above `summarise`. The notes `headlines` produces are
    already the briefing; the model was only ever going to reword them.
    """
    facts_text = facts_to_prompt(facts)
    notes = headlines(facts)
    prose, error = "", ""
    if with_prose:
        try:
            prose = summarise("\n".join(f"- {note}" for note in notes),
                              endpoint, model, timeout,
                              sentences=min(max(len(notes), 2), 5))
        except Exception as exc:  # noqa: BLE001 - the digest must survive any model failure
            error = f"{type(exc).__name__}: {exc}"
    return {
        "generated_at": facts.generated_at,
        "window_hours": facts.window_hours,
        "summary": prose,
        "notes": notes,
        "facts_text": facts_text,
        "facts": facts.as_dict(),
        "model": model if prose else "",
        "error": error,
    }


def write_digest(digest: dict, latest_path: Path, history_path: Path | None = None) -> None:
    """Write the digest, and append it to the history if one is being kept."""
    latest_path = Path(latest_path)
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    # Written whole then moved, so a reader never sees half a digest.
    temporary = latest_path.with_suffix(latest_path.suffix + ".tmp")
    temporary.write_text(json.dumps(digest, indent=2), encoding="utf-8")
    temporary.replace(latest_path)

    if history_path is not None:
        history_path = Path(history_path)
        with history_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(digest) + "\n")


def read_digest(path: Path) -> dict[str, Any] | None:
    path = Path(path)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
