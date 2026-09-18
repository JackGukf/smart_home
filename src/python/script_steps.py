"""What a Home Assistant script does, step by step, and whether each step took.

Quick actions on Home run scripts - Movie mode - and a tap used to give no
sign that anything happened, or of what the button controls. This reads the
script's own configuration into plain steps ("Projector on", "Kitchen light
switch off, if it is on"), and after a run compares each device's state with
what its step asked for.

Pure functions over the config and a state lookup: testable without Home
Assistant, and nothing here sends a command.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Iterable

# A button's state is when it was last pressed; within this long of the run,
# the press is this run's.
PRESS_WINDOW_S = 120


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(v) for v in value if v]


def _entities(step: dict[str, Any]) -> list[str]:
    target = step.get("target") or {}
    data = step.get("data") or {}
    return _as_list(target.get("entity_id")) or _as_list(step.get("entity_id")) or _as_list(data.get("entity_id"))


def _condition_text(conditions: Any) -> str | None:
    """"if it is on" for the one condition these scripts use; a generic phrase
    for anything else, so a condition is never silently dropped."""
    items = conditions if isinstance(conditions, list) else [conditions]
    texts = []
    for condition in items:
        if isinstance(condition, dict) and condition.get("condition") == "state":
            texts.append(f"if it is {condition.get('state')}")
        else:
            texts.append("if a condition holds")
    return " and ".join(texts) if texts else None


def _delay_text(delay: Any) -> str:
    if isinstance(delay, dict):
        parts = [f"{int(delay[k])} {label}" for k, label in (("hours", "h"), ("minutes", "min"), ("seconds", "s"))
                 if delay.get(k)]
        return "Wait " + " ".join(parts) if parts else "Wait"
    return f"Wait {delay}"


def flatten(sequence: Iterable[dict[str, Any]], when: str | None = None) -> list[dict[str, Any]]:
    """A script's sequence as a flat list of steps, nested blocks unrolled."""
    steps: list[dict[str, Any]] = []
    for step in sequence or []:
        if not isinstance(step, dict):
            continue
        action = step.get("action") or step.get("service")
        if action:
            steps.append({"kind": "action", "action": str(action), "entities": _entities(step),
                          "alias": step.get("alias"), "when": when})
        elif "delay" in step:
            steps.append({"kind": "delay", "text": _delay_text(step["delay"]), "alias": step.get("alias")})
        elif "if" in step:
            steps += flatten(step.get("then") or [], _condition_text(step.get("if")))
            if step.get("else"):
                steps += flatten(step["else"], "otherwise")
        elif "choose" in step:
            for option in step.get("choose") or []:
                steps += flatten(option.get("sequence") or [], _condition_text(option.get("conditions")))
            if step.get("default"):
                steps += flatten(step["default"], "otherwise")
        elif "parallel" in step or "sequence" in step:
            children = step.get("parallel") or step.get("sequence") or []
            steps += flatten([c if isinstance(c, dict) else {} for c in children], when)
        else:
            steps.append({"kind": "other", "text": step.get("alias") or next(iter(step), "step"),
                          "alias": step.get("alias")})
    return steps


def expected_state(action: str) -> str | None:
    service = action.split(".", 1)[-1]
    if service == "turn_on":
        return "on"
    if service == "turn_off":
        return "off"
    return None


def _pressed_since(state: str, since: float) -> bool:
    try:
        at = datetime.fromisoformat(str(state).replace("Z", "+00:00"))
    except ValueError:
        return False
    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    return at.timestamp() >= since - 5


def describe(steps: list[dict[str, Any]], state_of: Callable[[str], dict[str, Any] | None],
             ran_at: float | None = None) -> list[dict[str, Any]]:
    """Each step with its devices' names and states. After a run (ran_at),
    each device also says whether it is where its step left it:
    ok True/False, or None where a state cannot say (a condition that did not
    hold, a device that is not there)."""
    out = []
    for step in steps:
        if step["kind"] != "action":
            out.append({**step, "devices": []})
            continue
        devices = []
        want = expected_state(step["action"])
        for entity_id in step["entities"]:
            state = state_of(entity_id)
            # A device that is not there has no name to give: its id, readable.
            fallback = entity_id.split(".", 1)[-1].replace("_", " ").capitalize()
            device: dict[str, Any] = {"entity_id": entity_id,
                                      "name": ((state or {}).get("attributes") or {}).get("friendly_name") or fallback,
                                      "state": (state or {}).get("state")}
            if state is None:
                device["problem"] = "not in Home Assistant"
            if ran_at is not None:
                if state is None or device["state"] in ("unavailable", "unknown"):
                    device["ok"] = False if state is not None else None
                elif want is not None:
                    # A step behind a condition may rightly not have run.
                    device["ok"] = device["state"] == want or (None if step.get("when") else False)
                elif step["action"].startswith("button."):
                    device["ok"] = _pressed_since(device["state"], ran_at)
                else:
                    device["ok"] = None
            devices.append(device)
        out.append({**step, "devices": devices})
    return out


def summary(described: list[dict[str, Any]]) -> dict[str, int]:
    devices = [d for step in described for d in step.get("devices", [])]
    return {
        "devices": len(devices),
        "ok": sum(1 for d in devices if d.get("ok") is True),
        "failed": sum(1 for d in devices if d.get("ok") is False),
        "unknown": sum(1 for d in devices if d.get("ok") is None),
    }
