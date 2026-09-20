"""Forecasting the house's hourly series: the baseline, LightGBM, Chronos-2, and
the backtest that decides which of them the nightly job actually uses.

The heavy models are optional, so these tests run with none of them installed -
what is always testable is the machinery: the features, the walk-forward
backtest, and the rule that keeps the baseline unless something beats it.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta

import pytest

from src.python import energy_forecast as ef

START = datetime(2026, 8, 1, 0, 0)


def house_series(hours: int = 24 * 30, noise: float = 0.03) -> ef.Series:
    """A plausible house: a daily shape, a weekend lift, and a little noise.
    Deterministic, so a failure is a real failure."""
    import random

    rng = random.Random("house")
    series: ef.Series = []
    for h in range(hours):
        when = START + timedelta(hours=h)
        shape = ef.MODELS and (0.4 + 1.6 * math.sin(math.pi * max(0, when.hour - 6) / 18) ** 2)
        weekend = 1.15 if when.weekday() >= 5 else 1.0
        series.append((when, round(shape * weekend * rng.uniform(1 - noise, 1 + noise), 3)))
    return series


def test_metrics():
    assert ef.mae([1, 2, 3], [1, 2, 3]) == 0
    assert ef.mae([1, 2], [2, 4]) == pytest.approx(1.5)
    assert ef.rmse([0, 0], [3, 4]) == pytest.approx(3.5355, abs=1e-3)
    assert ef.smape([0], [0]) == 0          # a zero hour predicted zero is not 100% wrong
    assert ef.smape([1], [3]) == pytest.approx(100.0)


def test_the_baseline_learns_the_daily_shape():
    series = house_series()
    model = ef.SeasonalMedian().fit(series[:-24])
    predicted = model.predict(series[:-24], 24)
    actual = [v for _, v in series[-24:]]
    flat = [sum(v for _, v in series[:-24]) / len(series[:-24])] * 24
    assert ef.mae(actual, predicted) < ef.mae(actual, flat) / 2   # much better than "the average hour"
    assert len(predicted) == 24


def test_features_are_lags_rolling_means_and_calendar():
    values = [float(i) for i in range(200)]
    row = ef._features(values, datetime(2026, 8, 8, 13))          # a Saturday
    assert row[:3] == [199.0, 198.0, 197.0]                       # lag 1, 2, 3
    assert row[len(ef.LAGS)] == pytest.approx(sum(values[-3:]) / 3)
    assert row[-1] == 1.0                                          # weekend flag
    short = ef._features([1.0], datetime(2026, 8, 3, 9))           # a Monday, no history
    assert math.isnan(short[4]) and short[-1] == 0.0


def test_backtest_walks_forward_and_scores_each_fold():
    score = ef.backtest(house_series(), ef.SeasonalMedian, horizon=24, folds=5)
    assert score.model == "seasonal median" and score.folds == 5 and score.error is None
    assert 0 < score.mae < 1 and score.rmse >= score.mae
    assert score.as_dict()["folds"] == 5


def test_a_short_history_is_reported_not_crashed():
    score = ef.backtest(house_series(hours=40), ef.LightGBM, horizon=24, folds=3)
    assert score.folds == 0 and "needs" in score.error
    # And a model whose package is missing says so rather than failing the run.
    broken = type("Missing", (), {"name": "broken", "needs_hours": 24,
                                  "fit": lambda self, s: (_ for _ in ()).throw(ImportError("no package")),
                                  "__init__": lambda self: None})
    assert "ImportError" in ef.backtest(house_series(), broken, folds=2).error


def test_evaluate_scores_skill_against_the_baseline_and_ranks():
    scores = ef.evaluate(house_series(), ["seasonal median"], folds=3)
    assert [s.model for s in scores] == ["seasonal median"]
    assert scores[0].skill == 0.0                                  # the baseline against itself


def test_pick_keeps_the_baseline_unless_clearly_beaten():
    base = ef.Score("seasonal median", 0.10, 0.2, 10, 5, 0.1)
    tiny = ef.Score("lightgbm", 0.099, 0.2, 10, 5, 2.0, skill=0.01)
    clear = ef.Score("lightgbm", 0.08, 0.15, 8, 5, 2.0, skill=0.20)
    broken = ef.Score("chronos-2", float("nan"), float("nan"), float("nan"), 0, 0.0, error="ImportError")
    assert ef.pick([base, tiny]) == "seasonal median"              # 1% better is not worth it
    assert ef.pick([base, clear]) == "lightgbm"
    assert ef.pick([broken]) == "seasonal median"


def test_forecast_document_shape():
    doc = ef.forecast(house_series(), "sensor.x", "kWh", horizon=24, folds=3,
                      models=["seasonal median"]).as_dict()
    assert doc["model"] == "seasonal median" and doc["unit"] == "kWh"
    assert len(doc["hourly"]) == 24 and doc["history_hours"] == 24 * 30
    assert doc["next_24h_total"] == pytest.approx(sum(p["value"] for p in doc["hourly"]), abs=0.02)
    first = datetime.fromisoformat(doc["hourly"][0]["at"])
    assert first == START + timedelta(hours=24 * 30)               # the hour after the last reading
    assert doc["scores"][0]["model"] == "seasonal median"


def test_available_models_never_lies_about_the_baseline():
    have = ef.available_models()
    assert have["seasonal median"] is True and set(have) == set(ef.MODELS)


@pytest.mark.skipif(not ef.available_models()["lightgbm"], reason="lightgbm not installed here")
def test_lightgbm_beats_a_flat_line_when_it_is_installed():
    series = house_series()
    predicted = ef.LightGBM().fit(series[:-24]).predict(series[:-24], 24)
    actual = [v for _, v in series[-24:]]
    flat = [series[-25][1]] * 24
    assert ef.mae(actual, predicted) < ef.mae(actual, flat)


def test_gaps_are_filled_and_long_ones_cut_the_history():
    """Home Assistant's statistics skip hours. Chronos-2 refuses a series whose
    frequency it cannot infer and LightGBM's 168-hour lag falls off the end, so
    a gappy series is regularised before any model sees it."""
    base = datetime(2026, 9, 1, 0)
    series = [(base + timedelta(hours=h), float(h)) for h in range(10)]
    holed = series[:4] + series[6:]                       # two hours missing
    filled = ef.regularize(holed)
    assert [w for w, _ in filled] == [w for w, _ in series]
    assert filled[4][1] == pytest.approx(4.0) and filled[5][1] == pytest.approx(5.0)  # interpolated

    # A gap of more than six hours is not bridged: only the newer run is kept.
    split = series[:3] + [(base + timedelta(hours=20 + h), 100.0 + h) for h in range(5)]
    kept = ef.regularize(split)
    assert len(kept) == 5 and kept[0][0] == base + timedelta(hours=20)
    assert ef.regularize([]) == []


def test_a_gappy_series_still_gets_scored():
    series = house_series()
    gappy = [p for i, p in enumerate(series) if i % 37]     # drop an hour here and there
    scores = ef.evaluate(gappy, ["seasonal median"], folds=3)
    assert scores[0].error is None and scores[0].folds == 3


@pytest.mark.skipif(not ef.available_models()["lightgbm"], reason="lightgbm not installed here")
def test_lightgbm_trains_on_less_than_a_week():
    """Its longest lag is a week, but a lag past the start of history is NaN and
    LightGBM handles that - otherwise it could never train in the first week."""
    short = house_series(hours=100)
    predicted = ef.LightGBM().fit(short).predict(short, 24)
    assert len(predicted) == 24 and all(math.isfinite(v) for v in predicted)
