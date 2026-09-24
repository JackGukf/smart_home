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
    heat, base_nights = _heat_and_nights(lambda t: _hour_kw(t.date(), t.hour), now)
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
            "heat": heat,
            "base_nights": base_nights,
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
    """(power entity, energy entity) for the house's meter, or None if it is not
    paired or the meter has never reported.

    A PowerLync paired with Home Assistant but not joined to the meter - BC
    Hydro's side, and undone by a factory reset - still makes every sensor and
    reads 0 in all of them. A real register is never 0 kWh, so until it is
    above zero this is not a meter, and the page keeps its sample data rather
    than showing a live 0 W. Seen on the board 2026-09-23."""
    found = powerlync_sensors(states)
    if not found:
        return None
    by_id = {str(s.get("entity_id", "")): s for s in states}
    register = _number(by_id[found[1]].get("state"))
    return found if register and register > 0 else None


def powerlync_sensors(states: list[dict[str, Any]]) -> tuple[str, str] | None:
    """(power entity, energy entity) if the PowerLync is paired, reporting or not."""
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
    heat, base_nights = _heat_and_nights(lambda t: by_hour.get(t), now)

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
        "heat": heat,
        "base_nights": base_nights,
        "days": days,
        "rate": ELECTRIC_RATE,
        "provider": "BC Hydro",
    }


HEAT_DAYS = 14          # the heat map's rows, oldest first, today last
NIGHT_HOURS = range(0, 6)  # "always on" is the quietest hour between midnight and 6


def _heat_and_nights(kwh_at: Callable[[datetime], float | None], now: datetime
                     ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """The heat map (kWh per hour, a row per day) and each night's always-on load.

    An hour's kWh is its average kW, so the quietest night hour *is* the load
    that never switches off - the fridge, the network, the Orange Pi. Hours not
    yet over, or not recorded, are None: the page leaves them blank."""
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    heat, nights = [], []
    for back in range(HEAT_DAYS - 1, -1, -1):
        day = midnight - timedelta(days=back)
        hours = []
        for h in range(24):
            t = day + timedelta(hours=h)
            value = kwh_at(t) if t + timedelta(hours=1) <= now else None
            hours.append(None if value is None else round(value, 2))
        heat.append({"date": day.date().isoformat(), "hours": hours})
        night = [hours[h] for h in NIGHT_HOURS if hours[h] is not None]
        if night:
            nights.append({"date": day.date().isoformat(), "kw": round(min(night), 3)})
    return heat, nights


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
        self.waiting_for_meter = False   # paired with Home Assistant, but the meter has not reported
        self._looked_at: float | None = None
        self._cache: dict[str, tuple[float, Any]] = {}

    # Home Assistant, over REST and (for statistics, which REST does not serve) WebSocket.
    def _http_json(self, path: str) -> Any:
        request = Request(f"{self._base_url}{path}", headers={"Authorization": f"Bearer {self._token()}"})
        with urlopen(request, timeout=FETCH_TIMEOUT_S) as response:  # noqa: S310 - HA on the board
            return json.loads(response.read())

    def _ws_statistics(self, statistic_id: str, start: datetime, end: datetime, period: str) -> list[dict[str, Any]]:
        return fetch_statistics(self._base_url, self._token() or "", statistic_id, start, end, period)

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
            states = self._get_json("/api/states")
            self._entities = find_powerlync_entities(states)
            self.waiting_for_meter = self._entities is None and powerlync_sensors(states) is not None
        except OSError:
            return None  # Home Assistant down, and nothing was ever paired: still sample data
        return self._entities

    def snapshot(self, now: datetime | None = None) -> dict[str, Any]:
        now = now or datetime.now()
        entities = self._find() if self._token() else None
        if not entities:
            doc = snapshot(now)
            if self.waiting_for_meter:
                doc["meter"] = "waiting"
            return doc
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


def fetch_statistics(base_url: str, token: str, statistic_id: str, start: datetime, end: datetime,
                     period: str = "hour", types: tuple[str, ...] = ("change",)) -> list[dict[str, Any]]:
    """Home Assistant's long-term statistics, which REST does not serve.

    They survive the recorder's purge, so this is the only way to ask about
    anything older than ten days - the Energy view's 30 days, and the history
    the forecast models train on (src/python/energy_forecast.py)."""
    return asyncio.run(fetch_statistics_async(base_url, token, statistic_id, start, end, period, types))


async def fetch_statistics_async(base_url: str, token: str, statistic_id: str, start: datetime,
                                 end: datetime, period: str = "hour",
                                 types: tuple[str, ...] = ("change",)) -> list[dict[str, Any]]:
    import aiohttp

    url = base_url.rstrip("/").replace("https://", "wss://").replace("http://", "ws://") + "/api/websocket"
    timeout = aiohttp.ClientTimeout(total=FETCH_TIMEOUT_S)
    async with aiohttp.ClientSession(timeout=timeout) as session, session.ws_connect(url) as ws:
        await ws.receive_json()  # auth_required
        await ws.send_json({"type": "auth", "access_token": token})
        if (await ws.receive_json()).get("type") != "auth_ok":
            raise OSError("Home Assistant refused the token")
        await ws.send_json({
            "id": 1, "type": "recorder/statistics_during_period",
            "start_time": start.astimezone().isoformat(), "end_time": end.astimezone().isoformat(),
            "statistic_ids": [statistic_id], "period": period,
            "types": list(types), "units": {"energy": "kWh"},
        })
        reply = await ws.receive_json()
        if not reply.get("success"):
            raise OSError(f"statistics query failed: {reply.get('error')}")
        return list((reply.get("result") or {}).get(statistic_id) or [])


FORECAST_MAX_AGE_HOURS = 36  # a nightly file older than this is stale, so say nothing


def read_forecast(path, now: datetime | None = None) -> dict[str, Any] | None:
    """Last night's forecast (src/python/energy_forecast.py), if it is recent.

    The forecast job runs in its own venv on its own timer and may not have run
    at all - no file, or a file from before the PowerLync was paired, is simply
    nothing to show."""
    from pathlib import Path as _Path

    try:
        doc = json.loads(_Path(path).read_text(encoding="utf-8"))
        at = datetime.fromisoformat(str(doc["at"]))
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if (now or datetime.now()) - at > timedelta(hours=FORECAST_MAX_AGE_HOURS):
        return None
    return doc


# ── Gas, from the bills the owner uploaded ──
#
# The FortisBC meter cannot be read from the house, so there are no daily gas
# figures to show and inventing them would be worse than showing none. What the
# house does have is real: two years of billing periods, and a model fitted on
# them (src/python/gas_model.py). So the gas column shows **billing periods** -
# each one a measured amount over a measured stretch - and says what the model
# made of them.

GAS_PERIODS_SHOWN = 24


def gas_from_records(db_path, now: datetime | None = None) -> dict[str, Any] | None:
    """The gas section from the owner's own bills, or None if there are none yet."""
    from src.python import ai_data, gas_model

    now = now or datetime.now()
    try:
        db = ai_data.connect(db_path)
    except Exception:  # noqa: BLE001 - no database yet is not an error
        return None
    try:
        rows = [dict(r) for r in db.execute(
            "SELECT id, period_start, period_end, gj, cost, avg_temp_c FROM bills ORDER BY period_start")]
        if not rows:
            return None
        model = gas_model.fit(db, now)
        # A bill whose period another bill already covers is the same gas twice.
        # Its money is still real, so it counts towards the price per GJ below,
        # but it must not become a bar of its own.
        duplicates = {clash["other"]["id"] for clash in ai_data.overlapping_bills(db)}
        costed_rows = rows
        rows = [r for r in rows if r["id"] not in duplicates]
        periods = [{
            "start": r["period_start"], "end": r["period_end"],
            "date": r["period_end"],           # the chart labels by the day a period ended
            "gj": round(float(r["gj"]), 2),
            "days": (date.fromisoformat(r["period_end"]) - date.fromisoformat(r["period_start"])).days,
            "avg_temp_c": r["avg_temp_c"],
            "cost": r["cost"],
        } for r in rows][-GAS_PERIODS_SHOWN:]
        costed = [(r["cost"], r["gj"]) for r in costed_rows if r["cost"] and r["gj"]]
        rate = round(sum(c for c, _ in costed) / sum(g for _, g in costed), 2) if costed else GAS_RATE
        last = periods[-1]
        return {
            "sample": False,
            "source": "your FortisBC bills",
            "provider": "FortisBC",
            "periods": periods,
            "last_period": last,
            "last_period_gj": last["gj"],
            "gj_per_day": round(last["gj"] / last["days"], 3) if last["days"] else None,
            "same_period_last_year": _same_period_last_year(periods, last),
            "rate": rate,
            "rate_measured": bool(costed),
            "duplicates_ignored": len(duplicates),
            "model": model.as_dict(),
            # Daily figures only where the model's own input is known for the day.
            "days": [d for d in gas_model.daily_estimates(db, model, 30, now.date()) if d["gj"] is not None],
        }
    finally:
        db.close()


def _same_period_last_year(periods: list[dict[str, Any]], last: dict[str, Any]) -> dict[str, Any] | None:
    """The bill from a year ago, for the one comparison a person actually makes."""
    target = date.fromisoformat(last["end"]) - timedelta(days=365)
    nearest = min((p for p in periods if p is not last),
                  key=lambda p: abs((date.fromisoformat(p["end"]) - target).days), default=None)
    if nearest is None or abs((date.fromisoformat(nearest["end"]) - target).days) > 20:
        return None
    change = None
    if nearest["gj"]:
        change = round(100 * (last["gj"] - nearest["gj"]) / nearest["gj"])
    return {**nearest, "change_percent": change}


# ── Electricity, from BC Hydro's exports, until the PowerLync is paired ──
#
# Two years of bills say what the house used and what it cost; they cannot say
# what it is using now. So this is a third state, between the sample data and
# the live meter: real history, honestly labelled, with the live half missing.

def electricity_from_records(db_path, now: datetime | None = None) -> dict[str, Any] | None:
    """The electricity section from uploaded bills, or None if none are in."""
    from src.python import ai_data

    now = now or datetime.now()
    try:
        db = ai_data.connect(db_path)
    except Exception:  # noqa: BLE001 - no database yet is not an error
        return None
    try:
        rows = [dict(r) for r in db.execute(
            "SELECT period_start, period_end, kwh, cost, tier1_price, tier2_price,"
            " tier2_threshold_kwh, basic_per_day, source FROM power_periods ORDER BY period_start")]
        if not rows:
            return None
        bills = [r for r in rows if r["source"] == "bill"]
        months = [r for r in rows if r["source"] == "usage"]
        # Calendar months make the better chart - twice as many points - but the
        # bills are where the money is, so both are kept and each is used for
        # what it knows.
        series = months or bills
        periods = [{"start": r["period_start"], "end": r["period_end"], "date": r["period_end"],
                    "kwh": round(r["kwh"], 1), "cost": r["cost"],
                    "days": (date.fromisoformat(r["period_end"]) - date.fromisoformat(r["period_start"])).days}
                   for r in series][-GAS_PERIODS_SHOWN:]
        last = periods[-1]
        costed = [(r["cost"], r["kwh"]) for r in bills if r["cost"] and r["kwh"]]
        rate = round(sum(c for c, _ in costed) / sum(k for _, k in costed), 4) if costed else ELECTRIC_RATE
        newest_priced = next((r for r in reversed(bills) if r["tier1_price"]), None)
        last_bill = bills[-1] if bills else None
        return {
            "sample": False,
            "mode": "records",
            "source": "your BC Hydro bills",
            "provider": "BC Hydro",
            "period_kind": "month" if months else "bill",
            "periods": periods,
            "last_period": last,
            "last_period_kwh": last["kwh"],
            "kwh_per_day": round(last["kwh"] / last["days"], 1) if last["days"] else None,
            "same_period_last_year": _same_period_last_year_kwh(periods, last),
            "last_bill": ({"start": last_bill["period_start"], "end": last_bill["period_end"],
                           "kwh": round(last_bill["kwh"], 1), "cost": last_bill["cost"]}
                          if last_bill else None),
            "rate": rate,
            "rate_measured": bool(costed),
            "tier1_price": newest_priced["tier1_price"] if newest_priced else None,
            "tier2_price": newest_priced["tier2_price"] if newest_priced else None,
            "tier2_threshold_kwh": newest_priced["tier2_threshold_kwh"] if newest_priced else None,
            "basic_per_day": newest_priced["basic_per_day"] if newest_priced else None,
            "tier_bill_days": ((date.fromisoformat(newest_priced["period_end"])
                                - date.fromisoformat(newest_priced["period_start"])).days
                               if newest_priced else None),
            "year_kwh": round(sum(p["kwh"] for p in periods[-12:]), 1),
            "year_cost": round(sum(r["cost"] for r in bills[-6:] if r["cost"]), 2) if costed else None,
        }
    finally:
        db.close()


def _same_period_last_year_kwh(periods: list[dict[str, Any]], last: dict[str, Any]) -> dict[str, Any] | None:
    target = date.fromisoformat(last["end"]) - timedelta(days=365)
    nearest = min((p for p in periods if p is not last),
                  key=lambda p: abs((date.fromisoformat(p["end"]) - target).days), default=None)
    if nearest is None or abs((date.fromisoformat(nearest["end"]) - target).days) > 20:
        return None
    change = round(100 * (last["kwh"] - nearest["kwh"]) / nearest["kwh"]) if nearest["kwh"] else None
    return {**nearest, "change_percent": change}


# ── The power flow and the bill in progress ──
#
# Nothing in the house meters its own draw, so the flow is split only where
# something real says so: the meter, the always-on load (the quietest night
# hour), the furnace's state from the ecobee, and the gas model. The page
# labels the last two as estimates.

def furnace_state(attrs: dict[str, Any] | None) -> str | None:
    """"heating", "fan" or "idle" from an ecobee climate entity, or None if unknown.

    `equipment_running` (the cloud integration) tells a fan running on its own
    from burning gas; `hvac_action` (HomeKit) is the fallback."""
    from src.python.ai_data import HEATING_EQUIPMENT

    if not attrs:
        return None
    equipment = attrs.get("equipment_running")
    if equipment is not None:
        names = str(equipment).lower()
        if any(word in names for word in HEATING_EQUIPMENT):
            return "heating"
        return "fan" if "fan" in names else "idle"
    action = attrs.get("hvac_action")
    if action is None:
        return None
    return {"heating": "heating", "fan": "fan"}.get(str(action), "idle")


def bill_progress(records: dict[str, Any] | None, electricity: dict[str, Any],
                  now: datetime | None = None) -> dict[str, Any] | None:
    """Where this BC Hydro bill stands against the Step 1 threshold.

    BC Hydro bills on a fixed cycle, so the current period is the last uploaded
    bill rolled forward by its own length. The threshold and prices are the
    newest priced bill's, and the threshold is per bill, so it is scaled by the
    day to this period's length. Usage is the meter's days since the period
    began plus today; days before the first reading are not guessed - the
    period is "counted from" the first one, and the projection uses only the
    days that were counted."""
    if not records or not records.get("tier2_threshold_kwh") or not records.get("tier1_price"):
        return None
    last = records.get("last_bill") or {}
    try:
        start = date.fromisoformat(last["start"])
        end = date.fromisoformat(last["end"])
    except (KeyError, TypeError, ValueError):
        return None
    length = (end - start).days
    if length <= 0:
        return None
    now = now or datetime.now()
    today = now.date()
    start = end
    while start + timedelta(days=length) <= today:
        start += timedelta(days=length)
    end = start + timedelta(days=length)

    counted = [d for d in electricity.get("days") or [] if date.fromisoformat(d["date"]) >= start]
    used = sum(d["kwh"] for d in counted) + float(electricity.get("today_kwh") or 0)
    counted_from = min([date.fromisoformat(d["date"]) for d in counted] + [today])
    elapsed = (now - datetime.combine(counted_from, datetime.min.time())).total_seconds() / 86400
    per_day = used / elapsed if elapsed > 0.25 else None
    remaining = (datetime.combine(end, datetime.min.time()) - now).total_seconds() / 86400
    projected = None if per_day is None else used + per_day * max(0.0, remaining)

    tier_days = records.get("tier_bill_days") or length
    threshold = records["tier2_threshold_kwh"] * length / tier_days
    t1, t2 = records["tier1_price"], records.get("tier2_price") or records["tier1_price"]
    basic = records.get("basic_per_day") or 0.0

    def cost(kwh: float, days: float) -> float:
        return min(kwh, threshold) * t1 + max(0.0, kwh - threshold) * t2 + basic * days

    day_index = (today - start).days + 1
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "days": length,
        "day": day_index,
        "counted_from": counted_from.isoformat(),
        "partial": counted_from > start,
        "kwh": round(used, 1),
        "threshold_kwh": round(threshold),
        "projected_kwh": None if projected is None else round(projected),
        "tier1_price": t1,
        "tier2_price": t2,
        "cost_so_far": round(cost(used, day_index), 2),
        "projected_cost": None if projected is None else round(cost(projected, length), 2),
        "room_kwh_per_day": (None if projected is None
                             else round((threshold - used) / max(1, (end - today).days), 1)),
    }
