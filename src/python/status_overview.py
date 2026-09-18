"""What the Status view draws: the last day of the house, and of the board.

Four logs, four shapes:

  * **activity** - every binary sensor that says something happened (motion,
    occupancy, a camera's person detector, doors, leaks, smoke), counted per
    hour from Home Assistant's recorder;
  * **board** - memory, temperature and load, from the resource logger's own
    file, which samples every 30 seconds and holds weeks;
  * **services** - the units and containers the house runs on, checked by name
    from a fixed list, never from anything a request supplies;
  * **batteries** - what needs a new cell soon.

Everything here is read-only and cached, because the view is a glance: several
screens polling it must cost the board one pass, not one per screen.
"""

from __future__ import annotations

import json
import re
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.request import Request, urlopen

HOURS = 24
CACHE_SECONDS = 120
FETCH_TIMEOUT_S = 30
# The logger writes ~2,880 lines a day; a fortnight of history is ~1.2 MB. Only
# the tail is ever read, so the file can grow without slowing this down.
RESOURCE_TAIL_BYTES = 3_000_000
DEFAULT_RESOURCE_LOG = Path.home() / "resource-history.log"

ACTIVITY_CLASSES = frozenset({
    "motion", "occupancy", "door", "window", "garage_door", "opening",
    "vibration", "smoke", "moisture", "gas", "carbon_monoxide",
})

# What the house runs on. A fixed list: the view asks about these and nothing
# else, so no request can turn this into "run systemctl on anything".
SERVICE_UNITS: tuple[tuple[str, str, str], ...] = (
    ("smart-home-dashboard.service", "user", "Dashboard"),
    ("go2rtc.service", "user", "go2rtc"),
    ("npu-detector.service", "user", "NPU detector"),
    ("matter-bridge.service", "user", "Matter bridge"),
    ("panel-camera.service", "user", "Panel camera"),
    ("resource-logger.service", "user", "Resource logger"),
    ("zigbee-adapter-watch.service", "user", "Zigbee watchdog"),
    ("ollama.service", "system", "Ollama"),
    ("matter-server.service", "system", "Matter server"),
)
SERVICE_CONTAINERS: tuple[tuple[str, str], ...] = (
    ("homeassistant", "Home Assistant"),
    ("zigbee2mqtt", "Zigbee2MQTT"),
    ("mosquitto", "MQTT broker"),
    ("wyoming-whisper", "Whisper"),
    ("wyoming-piper", "Piper"),
)

PHONE_ENTITY = re.compile(r"iphone|ipad|android|pixel|galaxy|_watch", re.I)

RESOURCE_LINE = re.compile(
    r"^(?P<when>\S+) mem_used=(?P<mem>\d+)M avail=(?P<avail>\d+)M "
    r"load=(?P<load>[\d.]+)/[\d.]+ temp=(?P<temp>\d+)C"
)


@dataclass
class Bucket:
    values: list[float]

    def mean(self) -> float | None:
        return round(sum(self.values) / len(self.values), 2) if self.values else None


def _hour_index(when: datetime, start: datetime) -> int | None:
    index = int((when - start).total_seconds() // 3600)
    return index if 0 <= index < HOURS else None


# ── the board's own log ───────────────────────────────────────────────────────

def read_resource_history(path: Path, start: datetime, now: datetime) -> dict[str, Any]:
    """Hourly memory, load and temperature, plus when the board last booted."""
    series = {name: [Bucket([]) for _ in range(HOURS)] for name in ("mem", "avail", "load", "temp")}
    boot: str | None = None
    try:
        with path.open("rb") as handle:
            handle.seek(0, 2)
            size = handle.tell()
            handle.seek(max(0, size - RESOURCE_TAIL_BYTES))
            text = handle.read().decode("utf-8", "replace")
    except OSError:
        return {"status": "missing", "hours": [], "mem": [], "avail": [], "load": [], "temp": [], "boot": None}

    for line in text.splitlines():
        if " BOOT " in line:
            boot = line.split(" ", 1)[0]
            continue
        match = RESOURCE_LINE.match(line)
        if not match:
            continue
        try:
            when = datetime.fromisoformat(match.group("when"))
        except ValueError:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        index = _hour_index(when, start)
        if index is None:
            continue
        series["mem"][index].values.append(float(match.group("mem")))
        series["avail"][index].values.append(float(match.group("avail")))
        series["load"][index].values.append(float(match.group("load")))
        series["temp"][index].values.append(float(match.group("temp")))

    return {
        "status": "ok",
        "hours": [(start + timedelta(hours=h)).isoformat() for h in range(HOURS)],
        "mem": [b.mean() for b in series["mem"]],
        "avail": [b.mean() for b in series["avail"]],
        "load": [b.mean() for b in series["load"]],
        "temp": [b.mean() for b in series["temp"]],
        "boot": boot,
    }


# ── what happened in the house ────────────────────────────────────────────────

def _friendly(state: dict[str, Any]) -> str:
    return str((state.get("attributes") or {}).get("friendly_name") or state.get("entity_id") or "")


def activity_sensors(states: Iterable[dict[str, Any]]) -> list[dict[str, str]]:
    """Every binary sensor whose job is to say something happened."""
    picked = []
    for state in states:
        entity_id = str(state.get("entity_id") or "")
        if not entity_id.startswith("binary_sensor."):
            continue
        device_class = str((state.get("attributes") or {}).get("device_class") or "")
        is_camera = entity_id.endswith("_npu_person")
        if not is_camera and device_class not in ACTIVITY_CLASSES:
            continue
        kind = "camera" if is_camera else "motion" if device_class in {"motion", "occupancy"} \
            else "safety" if device_class in {"smoke", "moisture", "gas", "carbon_monoxide"} else "door"
        picked.append({"entity_id": entity_id, "name": _friendly(state), "kind": kind})
    return picked


def hourly_activity(history: list[list[dict[str, Any]]], start: datetime, now: datetime,
                    meta: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    """Per sensor: how many times it went on each hour, and for how long.

    The count is the rise, not the state: a sensor that stays on for an hour is
    one event, which is what "how often did this trip" means.
    """
    out: list[dict[str, Any]] = []
    for states in history:
        if not states:
            continue
        entity_id = str(states[0].get("entity_id") or "")
        info = meta.get(entity_id)
        if not info:
            continue
        counts = [0] * HOURS
        minutes = [0.0] * HOURS
        previous_state: str | None = None
        previous_at: datetime | None = None
        for point in states:
            raw = point.get("last_changed") or point.get("last_updated")
            if not isinstance(raw, str):
                continue
            try:
                at = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                continue
            if previous_state == "on" and previous_at is not None:
                _add_span(minutes, previous_at, at, start)
            # A rise from "off" only: the opening point, and a sensor coming back from
            # "unavailable" after a restart, are not something happening.
            if point.get("state") == "on" and previous_state == "off":
                index = _hour_index(at, start)
                if index is not None:
                    counts[index] += 1
            previous_state, previous_at = point.get("state"), at
        if previous_state == "on" and previous_at is not None:
            _add_span(minutes, previous_at, now, start)
        out.append({
            "entity_id": entity_id,
            "name": info["name"],
            "kind": info["kind"],
            "counts": counts,
            "minutes": [round(m, 1) for m in minutes],
            "total": sum(counts),
        })
    out.sort(key=lambda item: -item["total"])
    return out


def _add_span(minutes: list[float], begin: datetime, end: datetime, start: datetime) -> None:
    """Spread an on-period across the hours it covers."""
    cursor = max(begin, start)
    while cursor < end:
        index = _hour_index(cursor, start)
        if index is None:
            break
        boundary = min(end, start + timedelta(hours=index + 1))
        minutes[index] += (boundary - cursor).total_seconds() / 60
        cursor = boundary


def batteries(states: Iterable[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    found = []
    for state in states:
        attributes = state.get("attributes") or {}
        if attributes.get("device_class") != "battery":
            continue
        # A phone's battery is the companion app reporting, not a sensor in
        # the house that needs a new cell.
        if PHONE_ENTITY.search(str(state.get("entity_id") or "")):
            continue
        try:
            level = float(state.get("state"))
        except (TypeError, ValueError):
            continue
        found.append({"name": _friendly(state).replace(" Battery", ""), "percent": round(level)})
    found.sort(key=lambda item: item["percent"])
    return found[:limit]


# ── what the house runs on ────────────────────────────────────────────────────

def _run(command: list[str], timeout: float = 4.0) -> str:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def service_states(runner: Callable[[list[str]], str] = _run) -> list[dict[str, Any]]:
    """Each unit and container by name, with whether it is running.

    `systemctl --user is-active` answers "not-found" for a *system* unit and
    vice versa, which reads like "not installed" rather than "look in the other
    place" - so each one is asked in the scope it actually lives in.
    """
    out: list[dict[str, Any]] = []
    for unit, scope, label in SERVICE_UNITS:
        command = ["systemctl", "--user", "is-active", unit] if scope == "user" else ["systemctl", "is-active", unit]
        state = runner(command) or "unknown"
        out.append({"name": label, "unit": unit, "scope": scope, "state": state, "ok": state == "active"})

    running = {line.strip() for line in runner(["docker", "ps", "--format", "{{.Names}}"]).splitlines() if line.strip()}
    known = {line.strip() for line in runner(["docker", "ps", "-a", "--format", "{{.Names}}"]).splitlines() if line.strip()}
    for container, label in SERVICE_CONTAINERS:
        if container in running:
            state = "active"
        elif container in known:
            state = "stopped"
        else:
            state = "unknown"
        out.append({"name": label, "unit": container, "scope": "container", "state": state, "ok": state == "active"})
    return out


# ── the service ───────────────────────────────────────────────────────────────

class StatusOverview:
    def __init__(
        self,
        base_url: str,
        token_provider: Callable[[], str | None],
        resource_log: Path | None = None,
        fetch: Callable[[str, dict[str, str]], Any] | None = None,
        runner: Callable[[list[str]], str] = _run,
        clock: Callable[[], float] = time.time,
    ):
        self._base_url = base_url.rstrip("/")
        self._token = token_provider
        self._resource_log = resource_log or DEFAULT_RESOURCE_LOG
        self._fetch = fetch or self._http_json
        self._runner = runner
        self._clock = clock
        self._lock = threading.Lock()
        self._cache: tuple[float, dict[str, Any]] | None = None

    @staticmethod
    def _http_json(url: str, headers: dict[str, str]) -> Any:
        with urlopen(Request(url, headers=headers), timeout=FETCH_TIMEOUT_S) as response:  # noqa: S310 - HA on the board
            return json.loads(response.read())

    def overview(self) -> dict[str, Any]:
        now_ts = self._clock()
        with self._lock:
            hit = self._cache
        if hit and now_ts - hit[0] < CACHE_SECONDS:
            return hit[1]

        now = datetime.fromtimestamp(now_ts, tz=timezone.utc).replace(minute=0, second=0, microsecond=0) \
            + timedelta(hours=1)
        start = now - timedelta(hours=HOURS)

        board = read_resource_history(self._resource_log, start, now)
        services = service_states(self._runner)

        token = self._token()
        activity: list[dict[str, Any]] = []
        power: list[dict[str, Any]] = []
        status = "ok"
        if token:
            headers = {"Authorization": f"Bearer {token}"}
            try:
                states = self._fetch(f"{self._base_url}/api/states", headers)
                sensors = activity_sensors(states)
                power = batteries(states)
                if sensors:
                    ids = ",".join(sensor["entity_id"] for sensor in sensors)
                    url = (
                        f"{self._base_url}/api/history/period/{start.strftime('%Y-%m-%dT%H:%M:%SZ')}"
                        f"?end_time={now.strftime('%Y-%m-%dT%H:%M:%SZ')}&filter_entity_id={ids}"
                        "&minimal_response&no_attributes"
                    )
                    history = self._fetch(url, headers)
                    activity = hourly_activity(history, start, now, {s["entity_id"]: s for s in sensors})
            except OSError:
                status = "home_assistant_unavailable"
        else:
            status = "needs_auth"

        result = {
            "status": status,
            "start": start.isoformat(),
            "hours": [(start + timedelta(hours=h)).isoformat() for h in range(HOURS)],
            "activity": activity,
            "events_total": sum(item["total"] for item in activity),
            "board": board,
            "services": services,
            "batteries": power,
        }
        with self._lock:
            self._cache = (now_ts, result)
        return result
