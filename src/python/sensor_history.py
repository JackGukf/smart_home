"""Hourly history of groups of Home Assistant sensors, for the Temperatures card.

The card decides which sensors are indoor and which are outdoor, and which the
person has hidden; this module only answers "what did the average of these
sensors do over the last day", one value per hour. Home Assistant's recorder
already holds the readings, so nothing new is stored on the board.

Readings are irregular - a Zigbee sensor reports when its value changes, some
only every few hours - so each sensor is sampled every few minutes, carrying its
last reading forward, the group is averaged at each sample, and the samples are
averaged per hour. A sensor with no reading yet in the window simply does not
count until its first one, rather than dragging the average towards zero.

Entity ids come from the browser, so they are checked against a strict pattern
and capped in number before they go anywhere near a URL.
"""

from __future__ import annotations

import json
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from urllib.parse import quote
from urllib.request import Request, urlopen

GROUPS = ("indoor_temperature", "outdoor_temperature", "indoor_humidity", "outdoor_humidity", "co2")
ENTITY_ID = re.compile(r"^sensor\.[a-z0-9_]{1,120}$")
MAX_ENTITIES_PER_GROUP = 40
MAX_HOURS = 48
SAMPLE_MINUTES = 10
CACHE_SECONDS = 300
FETCH_TIMEOUT_S = 20


class HistoryRequestError(ValueError):
    """The request names something this module will not ask Home Assistant for."""


def validate_groups(groups: dict[str, list[str]]) -> dict[str, list[str]]:
    clean: dict[str, list[str]] = {}
    for name, ids in groups.items():
        if name not in GROUPS:
            raise HistoryRequestError(f"unknown group {name!r}")
        unique = list(dict.fromkeys(ids))
        if len(unique) > MAX_ENTITIES_PER_GROUP:
            raise HistoryRequestError(f"{name}: more than {MAX_ENTITIES_PER_GROUP} sensors")
        for entity_id in unique:
            if not ENTITY_ID.match(entity_id):
                raise HistoryRequestError(f"not a sensor entity id: {entity_id!r}")
        clean[name] = unique
    return clean


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _readings(history: list[list[dict[str, Any]]]) -> dict[str, list[tuple[datetime, float]]]:
    """entity_id -> [(when, value)], oldest first, numeric states only."""
    out: dict[str, list[tuple[datetime, float]]] = {}
    for states in history:
        if not states:
            continue
        entity_id = states[0].get("entity_id")
        points: list[tuple[datetime, float]] = []
        for state in states:
            entity_id = state.get("entity_id", entity_id)
            try:
                value = float(state["state"])
                when = _parse_time(state.get("last_changed") or state["last_updated"])
            except (KeyError, TypeError, ValueError):
                # "unavailable" and friends end the previous reading rather than
                # extending it, so a sensor that dropped out stops counting.
                if points and state.get("last_changed"):
                    try:
                        points.append((_parse_time(state["last_changed"]), float("nan")))
                    except ValueError:
                        pass
                continue
            points.append((when, value))
        if entity_id:
            out[entity_id] = sorted(points, key=lambda p: p[0])
    return out


def hourly_series(
    readings: dict[str, list[tuple[datetime, float]]],
    entity_ids: list[str],
    start: datetime,
    hours: int,
) -> list[float | None]:
    """One value per hour: the group's average, sampled every SAMPLE_MINUTES."""
    step = timedelta(minutes=SAMPLE_MINUTES)
    per_hour = 60 // SAMPLE_MINUTES
    cursors = {entity_id: 0 for entity_id in entity_ids}
    current: dict[str, float] = {}
    series: list[float | None] = []
    for hour in range(hours):
        samples: list[float] = []
        for k in range(per_hour):
            at = start + timedelta(hours=hour) + step * k + step / 2
            values: list[float] = []
            for entity_id in entity_ids:
                points = readings.get(entity_id) or []
                i = cursors[entity_id]
                while i < len(points) and points[i][0] <= at:
                    current[entity_id] = points[i][1]
                    i += 1
                cursors[entity_id] = i
                value = current.get(entity_id)
                if value is not None and value == value:  # not NaN
                    values.append(value)
            if values:
                samples.append(sum(values) / len(values))
        series.append(round(sum(samples) / len(samples), 2) if samples else None)
    return series


class SensorHistory:
    def __init__(
        self,
        base_url: str,
        token_provider: Callable[[], str | None],
        fetch: Callable[[str, dict[str, str]], Any] | None = None,
        clock: Callable[[], float] = time.time,
    ):
        self._base_url = base_url.rstrip("/")
        self._token = token_provider
        self._fetch = fetch or self._http_json
        self._clock = clock
        self._lock = threading.Lock()
        self._cache: dict[tuple, tuple[float, dict[str, Any]]] = {}

    @staticmethod
    def _http_json(url: str, headers: dict[str, str]) -> Any:
        with urlopen(Request(url, headers=headers), timeout=FETCH_TIMEOUT_S) as response:  # noqa: S310 - HA on the board
            return json.loads(response.read())

    def hourly(self, groups: dict[str, list[str]], hours: int = 24) -> dict[str, Any]:
        groups = validate_groups(groups)
        if not 1 <= hours <= MAX_HOURS:
            raise HistoryRequestError(f"hours must be between 1 and {MAX_HOURS}")
        key = (hours, tuple(sorted((name, tuple(sorted(ids))) for name, ids in groups.items())))
        now = self._clock()
        with self._lock:
            hit = self._cache.get(key)
        if hit and now - hit[0] < CACHE_SECONDS:
            return hit[1]

        token = self._token()
        if not token:
            return {"status": "needs_auth", "hours": [], "series": {}}

        end = datetime.fromtimestamp(now, tz=timezone.utc).replace(second=0, microsecond=0)
        start = end - timedelta(hours=hours)
        entity_ids = sorted({entity_id for ids in groups.values() for entity_id in ids})
        readings: dict[str, list[tuple[datetime, float]]] = {}
        if entity_ids:
            url = (
                f"{self._base_url}/api/history/period/{quote(start.strftime('%Y-%m-%dT%H:%M:%SZ'))}"
                f"?end_time={quote(end.strftime('%Y-%m-%dT%H:%M:%SZ'))}"
                f"&filter_entity_id={','.join(entity_ids)}&minimal_response&no_attributes"
            )
            readings = _readings(self._fetch(url, {"Authorization": f"Bearer {token}"}))

        result = {
            "status": "ok",
            "start": start.isoformat(),
            "hours": [(start + timedelta(hours=h)).isoformat() for h in range(hours)],
            "series": {name: hourly_series(readings, ids, start, hours) for name, ids in groups.items()},
        }
        with self._lock:
            self._cache[key] = (now, result)
        return result
