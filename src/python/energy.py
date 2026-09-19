"""Electricity and natural gas for the dashboard's Energy card and view.

Electricity is live once the BC Hydro PowerLync is paired (`LiveEnergy`,
below): the PowerLync reads the smart meter over Zigbee and Home Assistant reads
the PowerLync over HomeKit, locally - scripts/setup-ha-powerlync.py does both.
Until then every figure is *sample data* (`snapshot()`): a plausible day for
this house, generated from the clock so it moves like a real reading and is the
same for every screen at the same moment. Each section says which it is
("sample": true), and the dashboard shows it. Gas stays sample data: the
FortisBC meter cannot be read from the house (docs/energy-monitoring.md).
The payload's shape is the contract the page reads, live or not.

Electricity is in kW (now) and kWh (energy); natural gas is in GJ, the unit
FortisBC bills in, and only daily - a gas meter is not read in real time.
The prices are illustrative, not a tariff: BC Hydro's Step 1 rate and a
FortisBC all-in price per GJ, round figures for the order of magnitude.
"""
from __future__ import annotations

import asyncio
import json
import math
import random
import statistics
import threading
import time
from datetime import date, datetime, timedelta
from typing import Any, Callable
from urllib.parse import quote
from urllib.request import Request, urlopen

ELECTRIC_RATE = 0.1143   # $/kWh, BC Hydro Step 1 - illustrative
GAS_RATE = 15.20         # $/GJ, FortisBC all-in - illustrative

# A usual day for this house, kW averaged over each hour: about 0.4 kW of base
# load overnight (fridge, network, the Orange Pi), a breakfast bump and an
# evening peak with the oven and the dryer. Sums to about 21 kWh.
USUAL_HOURLY_KW = [0.45, 0.41, 0.40, 0.40, 0.41, 0.46, 0.80, 1.30, 1.05, 0.70, 0.66, 0.68,
                   0.80, 0.70, 0.66, 0.74, 1.10, 1.85, 2.60, 2.20, 1.60, 1.25, 0.90, 0.60]


def _rng(*seed: Any) -> random.Random:
    return random.Random("|".join(map(str, seed)))


def _hour_kw(day: date, hour: int) -> float:
    """One hour's average, near the usual day, varied by date."""
    return round(USUAL_HOURLY_KW[hour] * _rng("h", day, hour).uniform(0.82, 1.2), 3)


def _kw_at(moment: datetime) -> float:
    """Instantaneous kW: the hour's average, eased into the next, with a short
    appliance cycle now and then (a kettle, the fridge compressor)."""
    hour = moment.hour
    frac = moment.minute / 60
    here = _hour_kw(moment.date(), hour)
    nxt = _hour_kw((moment + timedelta(hours=1)).date(), (hour + 1) % 24)
    base = here + (nxt - here) * frac
    ripple = 0.05 * math.sin(moment.minute / 4.0)
    burst = 1.4 if _rng("b", moment.date(), hour, moment.minute // 12).random() < 0.12 else 0.0
    return round(max(0.25, base + ripple + burst), 2)


def _day_kwh(day: date) -> float:
    return round(sum(_hour_kw(day, h) for h in range(24)), 1)


def _day_gj(day: date) -> float:
    """Gas: the water heater all year, the furnace as it cools. Colder months more."""
    season = 0.5 + 0.5 * math.cos((day.timetuple().tm_yday - 15) / 365 * 2 * math.pi)  # 1 in January
    return round(0.14 + 0.55 * season + _rng("g", day).uniform(-0.03, 0.04), 2)


def snapshot(now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now()
    today = now.date()
    last_hour = [_kw_at(now - timedelta(minutes=59 - i)) for i in range(60)]
    hours_done = [_hour_kw(today, h) for h in range(now.hour)]
    this_hour = _hour_kw(today, now.hour) * now.minute / 60
    today_kwh = round(sum(hours_done) + this_hour, 1)
    # The last 24 whole hours, oldest first: complete periods read the same at
    # 00:30 as at 18:00, where "today" would be nearly empty just after midnight.
    hours_back = [now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=h) for h in range(24, 0, -1)]
    last_24h_hourly = [_hour_kw(t.date(), t.hour) for t in hours_back]
    last_24h_kwh = round(sum(last_24h_hourly), 1)
    # Whole days too, ending yesterday - for gas as well, which FortisBC reads daily at best.
    days = [today - timedelta(days=30 - i) for i in range(30)]
    electric_days = [{"date": d.isoformat(), "kwh": _day_kwh(d)} for d in days]
    kw_now = last_hour[-1]
    return {
        "sample": True,
        "source": "Sample data - the PowerLync is not connected yet",
        "at": now.isoformat(timespec="seconds"),
        "electricity": {
            "sample": True,
            "kw_now": kw_now,
            "state": "high" if kw_now >= 3 else "busy" if kw_now >= 1.2 else "base",
            "base_kw": round(min(USUAL_HOURLY_KW) * 0.95, 2),
            "last_hour_kw": last_hour,
            "today_kwh": today_kwh,
            "last_24h_kwh": last_24h_kwh,
            "today_hourly_kwh": [round(v, 2) for v in hours_done] + [round(this_hour, 2)],
            "last_24h_hourly_kwh": [round(v, 2) for v in last_24h_hourly],
            "last_24h_start_hour": hours_back[0].hour,
            "usual_hourly_kwh": USUAL_HOURLY_KW,
            "usual_24h_hourly_kwh": [USUAL_HOURLY_KW[t.hour] for t in hours_back],
            "days": electric_days,
            "rate": ELECTRIC_RATE,
            "provider": "BC Hydro",
        },
        "gas": _sample_gas(days),
    }


def _sample_gas(days: list[date]) -> dict[str, Any]:
    gas_days = [{"date": d.isoformat(), "gj": _day_gj(d)} for d in days]
    return {
        "sample": True,
        "yesterday_gj": gas_days[-1]["gj"],
        "days": gas_days,
        "rate": GAS_RATE,
        "provider": "FortisBC",
    }


# ── Live electricity, from the PowerLync through Home Assistant ──
#
# The community integration (Bolshem/powerlync-hub-homeassistant) names its
# sensors "Grid ..." for the house's meter and "Plug ..." for the smart outlet
# built into the PowerLync itself. Only the grid pair is the house; the plug
# pair measures whatever is plugged into the PowerLync, usually nothing.

POWER_SUFFIX = "instantaneous_demand"      # W, the meter's demand, ~every 30 s
ENERGY_SUFFIX = "total_energy_consumed"    # kWh, the meter's register, total_increasing
NOT_THE_HOUSE = ("plug", "local")

DISCOVERY_SECONDS = 60          # how often to look for the sensors while they are missing
POWER_CACHE_SECONDS = 10        # the page polls every 15 s; one query serves every screen
STATISTICS_CACHE_SECONDS = 300  # hourly statistics change once an hour
USUAL_DAYS = 14                 # "a usual day" is the median of this many
USUAL_MIN_DAYS = 3              # fewer whole days than this and there is no usual day yet
FETCH_TIMEOUT_S = 15


def find_powerlync_entities(states: list[dict[str, Any]]) -> tuple[str, str] | None:
    """(power entity, energy entity) for the house's meter, or None if not paired."""
    ids = [str(s.get("entity_id", "")) for s in states]

    def pick(suffix: str) -> str | None:
        found = sorted(i for i in ids if i.startswith("sensor.powerlync") and i.endswith(suffix)
                       and not any(word in i for word in NOT_THE_HOUSE))
        return found[0] if found else None

    power, energy = pick(POWER_SUFFIX), pick(ENERGY_SUFFIX)
    return (power, energy) if power and energy else None


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _local(value: Any) -> datetime:
    """A Home Assistant time - ISO text or epoch milliseconds - as naive local time."""
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone().replace(tzinfo=None)


def minute_series(history: list[dict[str, Any]], end: datetime, minutes: int = 60) -> list[float | None]:
    """kW at each minute up to `end`, carrying the last reading forward.

    The meter reports every 30 s or so, and only changes are recorded, so a
    flat stretch is one reading. "unavailable" ends a reading rather than
    extending it."""
    points = sorted(((_local(s.get("last_changed") or s.get("last_updated")), _number(s.get("state")))
                     for s in history if s.get("last_changed") or s.get("last_updated")),
                    key=lambda p: p[0])
    series: list[float | None] = []
    current: float | None = None
    i = 0
    for m in range(minutes):
        at = end - timedelta(minutes=minutes - 1 - m)
        while i < len(points) and points[i][0] <= at:
            current = points[i][1]
            i += 1
        series.append(None if current is None else round(current / 1000, 2))
    return series


def _state_of(kw: float | None) -> str:
    if kw is None:
        return "unknown"
    return "high" if kw >= 3 else "busy" if kw >= 1.2 else "base"


def build_live_electricity(
    now: datetime,
    power_state: dict[str, Any] | None,
    power_history: list[dict[str, Any]],
    hourly: list[dict[str, Any]],
    daily: list[dict[str, Any]],
) -> dict[str, Any]:
    """The electricity section from Home Assistant's own records.

    `hourly` and `daily` are recorder statistics ("change" of the kWh register
    per period), so they survive the recorder's 10-day purge and cover every
    day since pairing. Before that there is nothing, and the lists are short
    or hold None - the page draws what there is rather than inventing the rest."""
    kw_now = None
    if power_state is not None:
        watts = _number(power_state.get("state"))
        kw_now = None if watts is None else round(watts / 1000, 2)

    by_hour: dict[datetime, float] = {}
    for row in hourly:
        change = _number(row.get("change"))
        if change is not None and change >= 0:
            by_hour[_local(row["start"])] = change
    top = now.replace(minute=0, second=0, microsecond=0)
    hours_back = [top - timedelta(hours=h) for h in range(24, 0, -1)]
    last_24h = [by_hour.get(t) for t in hours_back]
    midnight = top.replace(hour=0)
    today = [by_hour.get(midnight + timedelta(hours=h)) for h in range(now.hour)]

    # A usual day: per clock hour, the median over the whole days before today.
    first_day = midnight - timedelta(days=USUAL_DAYS)
    per_hour: list[list[float]] = [[] for _ in range(24)]
    for t, kwh in by_hour.items():
        if first_day <= t < midnight:
            per_hour[t.hour].append(kwh)
    usual = None
    if all(len(values) >= USUAL_MIN_DAYS for values in per_hour):
        usual = [round(statistics.median(values), 2) for values in per_hour]
    recent = [kwh for t, kwh in by_hour.items() if t >= midnight - timedelta(days=7)]

    days = []
    for row in daily:
        change = _number(row.get("change"))
        day = _local(row["start"]).date()
        if change is not None and change >= 0 and day < now.date():
            days.append({"date": day.isoformat(), "kwh": round(change, 1)})
    days = sorted(days, key=lambda d: d["date"])[-30:]

    return {
        "sample": False,
        "kw_now": kw_now,
        "state": _state_of(kw_now),
        "base_kw": round(min(recent), 2) if recent else None,
        "last_hour_kw": minute_series(power_history, now),
        "today_kwh": round(sum(v for v in today if v is not None), 1),
        "last_24h_kwh": round(sum(v for v in last_24h if v is not None), 1),
        "today_hourly_kwh": [None if v is None else round(v, 2) for v in today],
        "last_24h_hourly_kwh": [None if v is None else round(v, 2) for v in last_24h],
        "last_24h_start_hour": hours_back[0].hour,
        "usual_hourly_kwh": usual,
        "usual_24h_hourly_kwh": [usual[t.hour] for t in hours_back] if usual else None,
        "days": days,
        "rate": ELECTRIC_RATE,
        "provider": "BC Hydro",
    }


class LiveEnergy:
    """`/api/energy`: live electricity once the PowerLync is in Home Assistant,
    sample data until then. Gas is sample data either way.

    Missing sensors are not an error - that is every day before the device
    arrives. Once they have been seen, a Home Assistant failure is raised
    rather than covered with sample figures: the page keeps its last reading,
    which is honest, where invented numbers labelled "live" would not be."""

    def __init__(
        self,
        base_url: str,
        token_provider: Callable[[], str | None],
        get_json: Callable[[str], Any] | None = None,
        get_statistics: Callable[[str, datetime, datetime, str], list[dict[str, Any]]] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._base_url = base_url.rstrip("/")
        self._token = token_provider
        self._get_json = get_json or self._http_json
        self._get_statistics = get_statistics or self._ws_statistics
        self._clock = clock
        self._lock = threading.Lock()
        self._entities: tuple[str, str] | None = None
        self._looked_at: float | None = None
        self._cache: dict[str, tuple[float, Any]] = {}

    # Home Assistant, over REST and (for statistics, which REST does not serve) WebSocket.
    def _http_json(self, path: str) -> Any:
        request = Request(f"{self._base_url}{path}", headers={"Authorization": f"Bearer {self._token()}"})
        with urlopen(request, timeout=FETCH_TIMEOUT_S) as response:  # noqa: S310 - HA on the board
            return json.loads(response.read())

    def _ws_statistics(self, statistic_id: str, start: datetime, end: datetime, period: str) -> list[dict[str, Any]]:
        return asyncio.run(self._ws_statistics_async(statistic_id, start, end, period))

    async def _ws_statistics_async(self, statistic_id: str, start: datetime, end: datetime,
                                   period: str) -> list[dict[str, Any]]:
        import aiohttp

        url = self._base_url.replace("https://", "wss://").replace("http://", "ws://") + "/api/websocket"
        timeout = aiohttp.ClientTimeout(total=FETCH_TIMEOUT_S)
        async with aiohttp.ClientSession(timeout=timeout) as session, session.ws_connect(url) as ws:
            await ws.receive_json()  # auth_required
            await ws.send_json({"type": "auth", "access_token": self._token()})
            if (await ws.receive_json()).get("type") != "auth_ok":
                raise OSError("Home Assistant refused the token")
            await ws.send_json({
                "id": 1, "type": "recorder/statistics_during_period",
                "start_time": start.astimezone().isoformat(), "end_time": end.astimezone().isoformat(),
                "statistic_ids": [statistic_id], "period": period,
                "types": ["change"], "units": {"energy": "kWh"},
            })
            reply = await ws.receive_json()
            if not reply.get("success"):
                raise OSError(f"statistics query failed: {reply.get('error')}")
            return list((reply.get("result") or {}).get(statistic_id) or [])

    def _cached(self, key: str, max_age: float, fetch: Callable[[], Any]) -> Any:
        now = self._clock()
        with self._lock:
            hit = self._cache.get(key)
        if hit and now - hit[0] < max_age:
            return hit[1]
        value = fetch()
        with self._lock:
            self._cache[key] = (now, value)
        return value

    def _find(self) -> tuple[str, str] | None:
        if self._entities:
            return self._entities
        now = self._clock()
        if self._looked_at is not None and now - self._looked_at < DISCOVERY_SECONDS:
            return None
        self._looked_at = now
        try:
            self._entities = find_powerlync_entities(self._get_json("/api/states"))
        except OSError:
            return None  # Home Assistant down, and nothing was ever paired: still sample data
        return self._entities

    def snapshot(self, now: datetime | None = None) -> dict[str, Any]:
        now = now or datetime.now()
        entities = self._find() if self._token() else None
        if not entities:
            return snapshot(now)
        power, energy = entities
        start = now - timedelta(minutes=61)
        history_path = (f"/api/history/period/{quote(start.astimezone().isoformat())}"
                        f"?end_time={quote(now.astimezone().isoformat())}"
                        f"&filter_entity_id={power}&minimal_response&no_attributes")

        def power_now() -> tuple[Any, Any]:
            history = self._get_json(history_path)
            return self._get_json(f"/api/states/{power}"), (history[0] if history else [])

        state, history = self._cached("power", POWER_CACHE_SECONDS, power_now)
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        hourly = self._cached("hourly", STATISTICS_CACHE_SECONDS, lambda: self._get_statistics(
            energy, midnight - timedelta(days=USUAL_DAYS), now, "hour"))
        daily = self._cached("daily", STATISTICS_CACHE_SECONDS, lambda: self._get_statistics(
            energy, midnight - timedelta(days=30), midnight, "day"))
        days = [midnight.date() - timedelta(days=30 - i) for i in range(30)]
        return {
            "sample": True,  # the gas; "electricity.sample" says whether the rest is
            "source": "Electricity live from the PowerLync; gas is sample data",
            "at": now.isoformat(timespec="seconds"),
            "entities": {"power": power, "energy": energy},
            "electricity": build_live_electricity(now, state, history, hourly, daily),
            "gas": _sample_gas(days),
        }
