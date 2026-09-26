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

    Setting("leak_remind_min", "Leak and smoke", "Leak reminder every",
            "While a leak alert stands and nobody said I know.", "min", 10, 2, 60, 1),
    Setting("leak_reminders", "Leak and smoke", "Leak reminders",
            "How many reminders at most after the first message.", "times", 3, 0, 20, 1),
    Setting("smoke_remind_min", "Leak and smoke", "Smoke reminder every",
            "While a smoke alert stands and nobody said I know.", "min", 3, 1, 30, 1),
    Setting("smoke_reminders", "Leak and smoke", "Smoke reminders",
            "How many reminders at most after the first message.", "times", 5, 0, 20, 1),
    Setting("low_battery_pct", "Leak and smoke", "Low battery below",
            "A leak or smoke sensor's battery under this is reported.", "%", 20, 5, 50, 1),
    Setting("sensor_silent_h", "Leak and smoke", "Not reporting after",
            "A leak or smoke sensor unavailable this long is reported. \"Unknown\" does not count: "
            "that is how the Zigbee ones rest.", "h", 6, 1, 48, 1),
    Setting("health_check_at", "Leak and smoke", "Daily sensor check at",
            "Low batteries and silent sensors are listed again every day at this time until fixed.",
            "", "10:00", kind="time"),

    Setting("intrusion_remind_min", "Intrusion", "Reminder every",
            "After the alarm speaker starts, until somebody presses Stop or I know - also after the "
            "speaker stops by itself.", "min", 2, 1, 15, 1),
    Setting("intrusion_reminders", "Intrusion", "Reminders",
            "How many reminders at most.", "times", 15, 0, 60, 1),

    Setting("car_parked_min", "Garage camera", "Car parked at least",
            "A car leaving counts as someone leaving only after it was parked this long - not one "
            "turning round in the driveway.", "min", 10, 1, 60, 1),
    Setting("car_gone_min", "Garage camera", "Driveway empty at least",
            "A car arriving ends Away only after the driveway was empty this long.", "min", 5, 1, 60, 1),
    Setting("left_recently_min", "Garage camera", "\"Someone just left\" lasts",
            "How long the camera's sighting of someone leaving can combine with a still house to "
            "make the house Away.", "min", 30, 5, 120, 5),

    Setting("night_start", "Night recorder", "Night starts", "When clips and Telegram photos begin.",
            "", "22:00", home="board", kind="time"),
    Setting("night_end", "Night recorder", "Night ends", "When they stop.", "", "06:30", home="board", kind="time"),
    Setting("clip_s", "Night recorder", "Clip length", "Each clip's length.", "s", 20, 5, 60, 1, home="board"),
    Setting("photo_every_min", "Night recorder", "One photo per trigger per",
            "A sensor firing every two minutes sends one message, not five; every picture is still kept.",
            "min", 5, 1, 60, 1, home="board"),
    Setting("moving_pct", "Night recorder", "Movement needed",
            "How much of the picture must move for a motion sensor's photo to be sent - a cat is several "
            "times the default, the camera's ticking clock far less.", "%", 0.8, 0.1, 10, 0.1, home="board"),
    Setting("keep_days", "Night recorder", "Keep clips for", "Older clips and photos are deleted.",
            "days", 14, 1, 90, 1, home="board"),
    Setting("max_gb", "Night recorder", "Keep at most", "The oldest go first when this is exceeded.",
            "GB", 20, 1, 200, 1, home="board"),

    Setting("login_max_failures", "Sign-in", "Lock out after",
            "Wrong dashboard passwords - or wrong disarm PINs - from one screen before it is locked out.",
            "tries", 5, 3, 20, 1, home="board"),
    Setting("login_lockout_min", "Sign-in", "Locked out for", "How long that screen is locked out.",
            "min", 15, 1, 120, 1, home="board"),

    Setting("backup_alert_h", "Backup and watchdog", "Alert when no backup for",
            "The heartbeat fails its ping when the nightly off-site backup has not succeeded this long.",
            "h", 36, 24, 168, 1, home="board"),
    Setting("backup_keep_daily", "Backup and watchdog", "Daily backups kept", "", "", 14, 1, 60, 1, home="board"),
    Setting("backup_keep_weekly", "Backup and watchdog", "Weekly backups kept", "", "", 8, 0, 52, 1, home="board"),
    Setting("backup_keep_monthly", "Backup and watchdog", "Monthly backups kept", "", "", 12, 0, 60, 1, home="board"),
    Setting("camera_outage_min", "Backup and watchdog", "Camera down before it counts",
            "A camera's detection unavailable this long is reported; shorter Wi-Fi blips are not.",
            "min", 10, 4, 60, 2, home="board"),
)

GROUP_ORDER = ("Freeze and furnace", "Leak and smoke", "Intrusion", "Garage camera", "Night recorder",
               "Sign-in", "Backup and watchdog")
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
