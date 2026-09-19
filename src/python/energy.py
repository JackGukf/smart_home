"""Electricity and natural gas for the dashboard's Energy card and view.

Until the BC Hydro PowerLync (a real-time reader for the smart meter) is
paired, every figure here is *sample data*: a plausible day for this house,
generated from the clock so it moves like a real reading and is the same for
every screen at the same moment. The payload says so ("sample": true), and the
dashboard shows it. When the PowerLync arrives, `snapshot()` is what changes;
the payload's shape is the contract the page reads.

Electricity is in kW (now) and kWh (energy); natural gas is in GJ, the unit
FortisBC bills in, and only daily - a gas meter is not read in real time.
The prices are illustrative, not a tariff: BC Hydro's Step 1 rate and a
FortisBC all-in price per GJ, round figures for the order of magnitude.
"""
from __future__ import annotations

import math
import random
from datetime import date, datetime, timedelta
from typing import Any

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
    gas_days = [{"date": d.isoformat(), "gj": _day_gj(d)} for d in days]
    kw_now = last_hour[-1]
    return {
        "sample": True,
        "source": "Sample data - the PowerLync is not connected yet",
        "at": now.isoformat(timespec="seconds"),
        "electricity": {
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
        "gas": {
            "yesterday_gj": gas_days[-1]["gj"],
            "days": gas_days,
            "rate": GAS_RATE,
            "provider": "FortisBC",
        },
    }
