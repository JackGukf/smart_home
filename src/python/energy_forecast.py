"""Forecasting the house's hourly series, and saying which model to believe.

Three models, and the rule that decides between them is a backtest on this
house's own numbers - not a paper's leaderboard:

  * **seasonal median** - what this hour of this weekday usually is. No
    training, no dependencies, and hard to beat on a house that runs to a
    routine. It is the baseline everything else has to earn its place against.
  * **LightGBM** - gradient boosting on lags and calendar features, trained on
    the board in a second or two. The regular workhorse: it picks up "colder
    days cost more" and "nobody is home on Tuesday afternoons".
  * **Chronos-2** - Amazon's pretrained time-series model (120M parameters),
    used zero-shot: no training at all, it reads the recent history and
    forecasts. Useful in the first weeks, when there is not enough history to
    train anything, and as a check on the other two.

Only the first two are needed for regular operation. LightGBM and Chronos-2
are optional imports, so this module loads and works with neither installed -
`available_models()` says what the machine actually has.

Nothing here drives a device. It writes a forecast for the dashboard to show,
in line with the house's rule: Python computes, rules execute, models never
sit in a trigger path.
"""
from __future__ import annotations

import json
import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Iterable, Sequence

Series = list[tuple[datetime, float]]  # hourly, oldest first

HORIZON = 24          # hours ahead a forecast covers
MIN_TRAIN_HOURS = 72  # less history than this and only the seasonal median runs
CHRONOS_MODEL = "amazon/chronos-2"
CHRONOS_CONTEXT = 24 * 21  # three weeks of context is plenty for an hourly house series


# ── metrics ──

def mae(actual: Sequence[float], predicted: Sequence[float]) -> float:
    return sum(abs(a - p) for a, p in zip(actual, predicted)) / len(actual)


def rmse(actual: Sequence[float], predicted: Sequence[float]) -> float:
    return math.sqrt(sum((a - p) ** 2 for a, p in zip(actual, predicted)) / len(actual))


def smape(actual: Sequence[float], predicted: Sequence[float]) -> float:
    """Symmetric percentage error, in percent. Pairs where both are zero count as zero."""
    total = 0.0
    for a, p in zip(actual, predicted):
        denominator = (abs(a) + abs(p)) / 2
        total += 0.0 if denominator == 0 else abs(a - p) / denominator
    return 100 * total / len(actual)


# ── the hourly grid ──
#
# Home Assistant's statistics skip hours: a sensor that reported nothing, a
# restart, a battery change. Gaps break the models in different ways - Chronos-2
# refuses a series whose frequency it cannot infer, and LightGBM's lag 168 walks
# off the end of a short run - so every series is put on a continuous hourly
# grid before anything sees it.

MAX_GAP_HOURS = 6  # longer than this is not a gap, it is a different stretch of history


def regularize(series: Series, max_gap: int = MAX_GAP_HOURS) -> Series:
    """One point per hour, oldest first: short gaps interpolated, and anything
    before a long gap dropped rather than bridged with invention."""
    if not series:
        return []
    points = sorted(series, key=lambda p: p[0])
    start = points[0][0]
    for (before, _), (after, _) in zip(points, points[1:]):
        if (after - before).total_seconds() > max_gap * 3600:
            start = after            # keep only the run after the last long gap
    run = [(when, value) for when, value in points if when >= start]
    out: Series = [run[0]]
    for when, value in run[1:]:
        previous_when, previous_value = out[-1]
        missing = int((when - previous_when).total_seconds() // 3600) - 1
        for step in range(1, missing + 1):
            share = step / (missing + 1)
            out.append((previous_when + timedelta(hours=step),
                        previous_value + (value - previous_value) * share))
        out.append((when, value))
    return out


# ── models ──
#
# A model is fit on a series and asked for the next `horizon` values. Keeping
# that interface tiny is what lets the backtest treat all three the same.

class SeasonalMedian:
    """The median of this hour of this weekday, then of this hour, then of everything."""

    name = "seasonal median"
    needs_hours = 24

    def __init__(self) -> None:
        self._by_slot: dict[tuple[int, int], list[float]] = {}
        self._by_hour: dict[int, list[float]] = {}
        self._all: list[float] = []

    def fit(self, series: Series) -> "SeasonalMedian":
        for when, value in series:
            self._by_slot.setdefault((when.weekday(), when.hour), []).append(value)
            self._by_hour.setdefault(when.hour, []).append(value)
            self._all.append(value)
        return self

    def _one(self, when: datetime) -> float:
        slot = self._by_slot.get((when.weekday(), when.hour))
        if slot and len(slot) >= 2:
            return statistics.median(slot)
        hour = self._by_hour.get(when.hour)
        if hour:
            return statistics.median(hour)
        return statistics.median(self._all) if self._all else 0.0

    def predict(self, series: Series, horizon: int = HORIZON) -> list[float]:
        last = series[-1][0]
        return [self._one(last + timedelta(hours=h)) for h in range(1, horizon + 1)]


LAGS = (1, 2, 3, 4, 24, 25, 48, 168)


def _features(history: list[float], when: datetime) -> list[float]:
    """Lags and calendar, for the point at `when` given everything before it."""
    row: list[float] = []
    for lag in LAGS:
        row.append(history[-lag] if len(history) >= lag else float("nan"))
    for window in (3, 24):
        row.append(sum(history[-window:]) / min(window, len(history)) if history else float("nan"))
    row += [
        math.sin(2 * math.pi * when.hour / 24), math.cos(2 * math.pi * when.hour / 24),
        math.sin(2 * math.pi * when.weekday() / 7), math.cos(2 * math.pi * when.weekday() / 7),
        float(when.weekday() >= 5),
    ]
    return row


class LightGBM:
    """Gradient boosting on lags and calendar, forecasting one hour at a time.

    Recursive rather than one model per horizon: a house has one series and a
    few weeks of it, so 24 models would each see less data and take 24 times
    as long to train, for no gain that showed in the backtest.
    """

    name = "lightgbm"
    needs_hours = MIN_TRAIN_HOURS

    def __init__(self, **params: Any) -> None:
        self.params = {
            "objective": "l1",          # absolute error: a spiky hour should not drag the rest
            "num_leaves": 15,
            "learning_rate": 0.06,
            "n_estimators": 250,
            "min_child_samples": 10,
            "verbose": -1,
            "n_jobs": 4,                # four A720s; the board has other work
            **params,
        }
        self._model: Any = None

    def fit(self, series: Series) -> "LightGBM":
        import lightgbm as lgb

        values = [v for _, v in series]
        rows, targets = [], []
        # From the first day, not the first week: a lag that reaches past the
        # start of the history is NaN, and LightGBM handles missing values
        # natively. Waiting for lag 168 to be real would refuse to train on
        # anything younger than a week - which is exactly the first week.
        for i in range(min(max(LAGS), 24), len(series)):
            rows.append(_features(values[:i], series[i][0]))
            targets.append(values[i])
        if not rows:
            raise ValueError("not enough history to train")
        self._model = lgb.LGBMRegressor(**self.params).fit(rows, targets)
        return self

    def predict(self, series: Series, horizon: int = HORIZON) -> list[float]:
        values = [v for _, v in series]
        when = series[-1][0]
        out: list[float] = []
        for _ in range(horizon):
            when += timedelta(hours=1)
            predicted = float(self._model.predict([_features(values, when)])[0])
            out.append(predicted)
            values.append(predicted)  # recursive: its own forecast becomes the next lag
        return out


class Chronos2:
    """Amazon's pretrained Chronos-2, zero-shot: no training on this house at all.

    Loaded once and kept, because loading costs far more than a forecast does.
    """

    name = "chronos-2"
    needs_hours = 48

    _pipelines: dict[str, Any] = {}

    def __init__(self, model: str = CHRONOS_MODEL, context: int = CHRONOS_CONTEXT) -> None:
        self.model = model
        self.context = context
        self._series: Series = []

    @classmethod
    def pipeline(cls, model: str = CHRONOS_MODEL) -> Any:
        if model not in cls._pipelines:
            import torch
            from chronos import Chronos2Pipeline

            torch.set_num_threads(4)
            cls._pipelines[model] = Chronos2Pipeline.from_pretrained(model, device_map="cpu")
        return cls._pipelines[model]

    def fit(self, series: Series) -> "Chronos2":
        self._series = series[-self.context:]  # "fitting" is just keeping the context
        return self

    def predict(self, series: Series, horizon: int = HORIZON) -> list[float]:
        import pandas as pd

        context = (series or self._series)[-self.context:]
        frame = pd.DataFrame({
            "id": ["house"] * len(context),
            "timestamp": pd.to_datetime([when for when, _ in context]),
            "target": [value for _, value in context],
        })
        answer = self.pipeline(self.model).predict_df(
            frame, prediction_length=horizon, quantile_levels=[0.5],
            id_column="id", timestamp_column="timestamp", target="target",
        )
        column = "0.5" if "0.5" in answer.columns else "predictions"
        return [float(v) for v in answer[column].tolist()[:horizon]]


ModelFactory = Callable[[], Any]
MODELS: dict[str, ModelFactory] = {
    "seasonal median": SeasonalMedian,
    "lightgbm": LightGBM,
    "chronos-2": Chronos2,
}


def available_models() -> dict[str, bool]:
    """Which models this machine can actually run. The baseline always can."""
    have = {"seasonal median": True}
    for name, module in (("lightgbm", "lightgbm"), ("chronos-2", "chronos")):
        try:
            __import__(module)
            have[name] = True
        except ImportError:
            have[name] = False
    return have


# ── backtesting ──

@dataclass
class Score:
    model: str
    mae: float
    rmse: float
    smape: float
    folds: int
    seconds: float
    skill: float = 0.0  # how much better than the baseline, as a fraction of its MAE
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"model": self.model, "mae": round(self.mae, 4), "rmse": round(self.rmse, 4),
                "smape": round(self.smape, 2), "folds": self.folds,
                "seconds": round(self.seconds, 1), "skill": round(self.skill, 3),
                **({"error": self.error} if self.error else {})}


def backtest(series: Series, factory: ModelFactory, horizon: int = HORIZON,
             folds: int = 5, step: int = 24, clock: Callable[[], float] | None = None) -> Score:
    """Walk forward: train on the past, forecast `horizon` hours, score, move on.

    Every fold trains from scratch on everything before its cut, which is what
    the nightly job does, so the score is the score of the job.
    """
    import time

    clock = clock or time.monotonic
    name = getattr(factory, "name", None) or factory().name
    needed = getattr(factory, "needs_hours", MIN_TRAIN_HOURS)
    cuts = [len(series) - horizon - step * i for i in range(folds)]
    cuts = [c for c in cuts if c >= needed]
    if not cuts:
        return Score(name, float("nan"), float("nan"), float("nan"), 0, 0.0,
                     error=f"needs {needed + horizon} hours, has {len(series)}")
    started = clock()
    errors_mae, errors_rmse, errors_smape = [], [], []
    for cut in sorted(cuts):
        train, actual = series[:cut], [v for _, v in series[cut:cut + horizon]]
        try:
            predicted = factory().fit(train).predict(train, horizon)
        except Exception as error:  # noqa: BLE001 - a missing package or a model that will not fit
            return Score(name, float("nan"), float("nan"), float("nan"), 0,
                         clock() - started, error=f"{type(error).__name__}: {error}")
        errors_mae.append(mae(actual, predicted))
        errors_rmse.append(rmse(actual, predicted))
        errors_smape.append(smape(actual, predicted))
    return Score(name, sum(errors_mae) / len(errors_mae), sum(errors_rmse) / len(errors_rmse),
                 sum(errors_smape) / len(errors_smape), len(cuts), clock() - started)


def evaluate(series: Series, models: Iterable[str] | None = None, horizon: int = HORIZON,
             folds: int = 5) -> list[Score]:
    """Backtest each model and score it against the baseline (its "skill")."""
    series = regularize(series)
    have = available_models()
    names = [n for n in (models or MODELS) if have.get(n)]
    if "seasonal median" not in names:
        names.insert(0, "seasonal median")
    scores = [backtest(series, MODELS[name], horizon, folds) for name in names]
    baseline = next((s for s in scores if s.model == "seasonal median" and not s.error), None)
    if baseline and baseline.mae:
        for score in scores:
            if not score.error:
                score.skill = (baseline.mae - score.mae) / baseline.mae
    return sorted(scores, key=lambda s: (s.error is not None, s.mae))


def pick(scores: Sequence[Score], margin: float = 0.03) -> str:
    """The baseline unless something beats it by `margin` - a model that is only
    a hair better is not worth the moving parts."""
    usable = [s for s in scores if not s.error and s.mae == s.mae]
    if not usable:
        return "seasonal median"
    best = min(usable, key=lambda s: s.mae)
    return best.model if best.skill >= margin else "seasonal median"


# ── the forecast the dashboard reads ──

@dataclass
class Forecast:
    statistic_id: str
    unit: str
    model: str
    at: datetime
    hourly: list[dict[str, Any]] = field(default_factory=list)
    scores: list[dict[str, Any]] = field(default_factory=list)
    history_hours: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "statistic_id": self.statistic_id,
            "unit": self.unit,
            "model": self.model,
            "at": self.at.isoformat(timespec="seconds"),
            "history_hours": self.history_hours,
            "next_24h_total": round(sum(p["value"] for p in self.hourly), 2),
            "hourly": self.hourly,
            "scores": self.scores,
        }


def forecast(series: Series, statistic_id: str, unit: str, horizon: int = HORIZON,
             folds: int = 5, models: Iterable[str] | None = None) -> Forecast:
    """Score the models on this house, use the winner, and keep the scorecard."""
    series = regularize(series)
    scores = evaluate(series, models, horizon, folds)
    chosen = pick(scores)
    values = MODELS[chosen]().fit(series).predict(series, horizon)
    last = series[-1][0]
    hourly = [{"at": (last + timedelta(hours=h + 1)).isoformat(timespec="seconds"),
               "value": round(v, 3)} for h, v in enumerate(values)]
    return Forecast(statistic_id, unit, chosen, datetime.now(), hourly,
                    [s.as_dict() for s in scores], len(series))


def write_forecast(doc: Forecast, path) -> None:
    from pathlib import Path

    Path(path).write_text(json.dumps(doc.as_dict(), indent=2) + "\n", encoding="utf-8")


# ── the series, from Home Assistant's own records ──

def load_series(base_url: str, token: str, statistic_id: str, days: int = 30,
                kind: str = "change") -> tuple[Series, str]:
    """Hourly history for one statistic, oldest first. `kind` is "change" for a
    meter (kWh in that hour) or "mean" for a reading (degrees, ppm)."""
    from src.python import energy

    end = datetime.now().replace(minute=0, second=0, microsecond=0)
    rows = energy.fetch_statistics(base_url, token, statistic_id, end - timedelta(days=days), end,
                                   "hour", (kind,))
    series: Series = []
    for row in rows:
        value = row.get(kind)
        if value is None:
            continue
        series.append((energy._local(row["start"]), float(value)))
    return regularize(series), kind


def electricity_statistic_id(base_url: str, token: str) -> str | None:
    """The PowerLync's kWh register, if it is paired."""
    from urllib.request import Request, urlopen
    from src.python import energy

    request = Request(f"{base_url.rstrip('/')}/api/states", headers={"Authorization": f"Bearer {token}"})
    with urlopen(request, timeout=30) as response:  # noqa: S310 - HA on the board
        found = energy.find_powerlync_entities(json.loads(response.read()))
    return found[1] if found else None


def main(argv: list[str] | None = None) -> int:
    import argparse
    import os
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[2]
    for line in (project_root / ".env").read_text(encoding="utf-8").splitlines() if (project_root / ".env").is_file() else []:
        key, _, value = line.strip().partition("=")
        if key and not key.startswith("#") and value:
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--statistic-id", help="what to forecast (default: the PowerLync's kWh register)")
    ap.add_argument("--kind", choices=("change", "mean"), default=None,
                    help='"change" for a meter, "mean" for a reading (default: change for energy)')
    ap.add_argument("--days", type=int, default=30, help="how much history to pull")
    ap.add_argument("--horizon", type=int, default=HORIZON)
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--models", help="comma-separated subset, e.g. 'seasonal median,lightgbm'")
    ap.add_argument("--out", default=str(project_root / "energy_forecast.json"),
                    help="where the forecast goes; --evaluate writes nothing")
    ap.add_argument("--evaluate", action="store_true", help="score the models and print a table, changing nothing")
    ap.add_argument("--base-url", default=os.getenv("HOME_ASSISTANT_URL", "http://127.0.0.1:8123"))
    args = ap.parse_args(argv)

    token = os.getenv("HOME_ASSISTANT_TOKEN")
    if not token:
        print("HOME_ASSISTANT_TOKEN is not set (looked in .env)", file=sys.stderr)
        return 1

    statistic_id = args.statistic_id or electricity_statistic_id(args.base_url, token)
    if not statistic_id:
        # Not an error: this is every day until the PowerLync is paired.
        print("no live electricity yet (the PowerLync is not paired) - nothing to forecast")
        return 0
    kind = args.kind or ("mean" if args.statistic_id and not statistic_id.endswith("energy_consumed") else "change")
    series, kind = load_series(args.base_url, token, statistic_id, args.days, kind)
    if len(series) < SeasonalMedian.needs_hours + args.horizon:
        print(f"{statistic_id}: only {len(series)} hours of history - too early to forecast")
        return 0

    models = [m.strip() for m in args.models.split(",")] if args.models else None
    have = available_models()
    print(f"{statistic_id}: {len(series)} hours, {series[0][0]:%Y-%m-%d %H:%M} to {series[-1][0]:%Y-%m-%d %H:%M}")
    print("installed: " + ", ".join(f"{k}={'yes' if v else 'no'}" for k, v in have.items()))

    if args.evaluate:
        scores = evaluate(series, models, args.horizon, args.folds)
        print(f"\n{'model':16} {'MAE':>9} {'RMSE':>9} {'sMAPE%':>8} {'skill':>7} {'folds':>6} {'secs':>7}")
        for s in scores:
            if s.error:
                print(f"{s.model:16} {'-':>9} {'-':>9} {'-':>8} {'-':>7} {'-':>6} {'-':>7}  {s.error}")
            else:
                print(f"{s.model:16} {s.mae:9.4f} {s.rmse:9.4f} {s.smape:8.2f} {s.skill:+7.1%} {s.folds:6} {s.seconds:7.1f}")
        print(f"\nwould use: {pick(scores)}")
        return 0

    doc = forecast(series, statistic_id, "kWh" if kind == "change" else "", args.horizon, args.folds, models)
    write_forecast(doc, args.out)
    print(f"model {doc.model}, next {args.horizon} h totals {doc.as_dict()['next_24h_total']} -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
