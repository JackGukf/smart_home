"""The house's tunable numbers, in one place: what each is, its range, its default,
and where it lives - edited on the dashboard (Settings -> House rules).

Asked for 2026-09-26: the thresholds, delays and counts written that week were
constants in installers and services. Each is now a Setting:

  * home="ha"    a Home Assistant number helper, input_number.house_<key> (or an
                 input_datetime for a time of day). The rules read it with
                 ha_value() in their templates, so a change applies at once,
                 without reinstalling anything. scripts/install-house-settings.py
                 creates the helpers.
  * home="board" a key in house_settings.json beside the project, read by the
                 board's own services (the night watch, the heartbeat, the backup)
                 with value() each time they need it.

Standard library only: the heartbeat runs on the system python3, the night watch
in the NPU environment.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BOARD_FILE = Path(os.getenv("HOUSE_SETTINGS_FILE", str(PROJECT_ROOT / "house_settings.json")))


@dataclass(frozen=True)
class Setting:
    key: str
    group: str
    label: str
    help: str
    unit: str
    default: float | str
    minimum: float = 0
    maximum: float = 0
    step: float = 1
    home: str = "ha"            # "ha" or "board"
    kind: str = "number"        # "number" or "time" (HH:MM)

    @property
    def entity(self) -> str:
        domain = "input_datetime" if self.kind == "time" else "input_number"
        return f"{domain}.house_{self.key}"


SETTINGS: tuple[Setting, ...] = (
    Setting("freeze_below_c", "Freeze and furnace", "Too cold below",
            "Alert when the thermostat reads below this for 10 minutes: pipes freeze well "
            "below it, and the furnace should never let the house get here.",
            "°C", 12, 5, 20, 0.5),
    Setting("furnace_fail_min", "Freeze and furnace", "Furnace failing after",
            "Alert when heat has been called for this long and the house has not warmed "
            "by at least 0.3 °C.", "min", 60, 20, 240, 5),
)

GROUP_ORDER = ("Freeze and furnace",)
BY_KEY = {s.key: s for s in SETTINGS}


def validate(key: str, raw: Any) -> float | str:
    """The value to store, or ValueError saying why not."""
    setting = BY_KEY.get(key)
    if setting is None:
        raise ValueError(f"unknown setting: {key}")
    if setting.kind == "time":
        text = str(raw).strip()[:5]
        hours, _, minutes = text.partition(":")
        if not (hours.isdigit() and minutes.isdigit() and int(hours) < 24 and int(minutes) < 60 and len(text) == 5):
            raise ValueError(f"{setting.label}: a time like 22:00")
        return text
    try:
        number = float(raw)
    except (TypeError, ValueError):
        raise ValueError(f"{setting.label}: a number") from None
    if not setting.minimum <= number <= setting.maximum:
        raise ValueError(f"{setting.label}: between {setting.minimum:g} and {setting.maximum:g} {setting.unit}")
    steps = round((number - setting.minimum) / setting.step)
    return round(setting.minimum + steps * setting.step, 6)


def board_values(path: Path | None = None) -> dict[str, Any]:
    """Every board setting: the stored value where there is a valid one, else the default."""
    try:
        stored = json.loads((path or BOARD_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        stored = {}
    out: dict[str, Any] = {}
    for setting in SETTINGS:
        if setting.home != "board":
            continue
        try:
            out[setting.key] = validate(setting.key, stored[setting.key])
        except (KeyError, ValueError):
            out[setting.key] = setting.default
    return out


def value(key: str, path: Path | None = None) -> Any:
    """A board setting, as a service reads it (a bad or missing value is the default)."""
    return board_values(path)[key]


def save_board(key: str, raw: Any, path: Path | None = None) -> Any:
    setting = BY_KEY[key]
    if setting.home != "board":
        raise ValueError(f"{key} lives in Home Assistant")
    clean = validate(key, raw)
    target = path or BOARD_FILE
    try:
        stored = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        stored = {}
    stored[key] = clean
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(stored, indent=1, sort_keys=True), encoding="utf-8")
    tmp.replace(target)
    return clean


def ha_value(key: str) -> str:
    """A Jinja expression for a rule: the helper's value, or the default when the
    helper is missing or unavailable - a rule must never stop for want of a setting."""
    setting = BY_KEY[key]
    if setting.kind == "time":
        return f"(states('{setting.entity}')[:5] if states('{setting.entity}') not in ['unknown', 'unavailable'] else '{setting.default}')"
    return f"(states('{setting.entity}') | float({setting.default}))"


def ha_helper_messages() -> list[tuple[str, dict]]:
    """Websocket create messages for the Home Assistant helpers. Named so that the
    entity id comes out as input_number.house_<key>; no `initial`, which would
    reset the value on every Home Assistant restart."""
    out = []
    for setting in SETTINGS:
        if setting.home != "ha":
            continue
        name = "House " + setting.key.replace("_", " ")
        if setting.kind == "time":
            out.append((setting.entity, {"type": "input_datetime/create", "name": name,
                                         "has_date": False, "has_time": True, "icon": "mdi:clock-outline"}))
        else:
            out.append((setting.entity, {"type": "input_number/create", "name": name,
                                         "min": setting.minimum, "max": setting.maximum, "step": setting.step,
                                         "mode": "box", "unit_of_measurement": setting.unit,
                                         "icon": "mdi:tune-variant"}))
    return out


def describe(ha_states: dict[str, Any]) -> list[dict[str, Any]]:
    """The dashboard's page: groups in order, each setting with its current value.
    `ha_states` maps entity id -> state string."""
    board = board_values()
    groups: dict[str, list[dict[str, Any]]] = {}
    for setting in SETTINGS:
        if setting.home == "board":
            current, available = board[setting.key], True
        else:
            raw = ha_states.get(setting.entity)
            try:
                current, available = validate(setting.key, raw), True
            except ValueError:
                current, available = setting.default, False
        groups.setdefault(setting.group, []).append({
            "key": setting.key, "label": setting.label, "help": setting.help, "unit": setting.unit,
            "value": current, "default": setting.default, "min": setting.minimum, "max": setting.maximum,
            "step": setting.step, "kind": setting.kind, "home": setting.home, "available": available,
        })
    order = list(GROUP_ORDER) + [g for g in groups if g not in GROUP_ORDER]
    return [{"name": g, "settings": groups[g]} for g in order if g in groups]
