import pandas as pd
import pytest

from app.forecasting.baselines import drift, naive_last, seasonal_naive
from app.forecasting.metrics import backtest_split, mape, rmse
from app.forecasting.series import to_series


def test_to_series_parses_daily_monthly_quarterly_annual():
    daily = to_series([("2024-01-01", 1.0), ("2024-01-02", 2.0)])
    assert daily.index[0] == pd.Timestamp("2024-01-01")

    monthly = to_series([("2024-01", 1.0), ("2024-02", 2.0)])
    assert monthly.index[1] == pd.Timestamp("2024-02-01")

    quarterly = to_series([("2023-Q4", 1.0), ("2024-Q1", 2.0)])
    assert quarterly.index[1] == pd.Timestamp("2024-01-01")

    annual = to_series([("2022", 1.0), ("2023", 2.0)])
    assert annual.index[0] == pd.Timestamp("2022-01-01")


def test_to_series_drops_missing_and_sorts():
    s = to_series([("2024-03", 3.0), ("2024-01", 1.0), ("2024-02", None)])
    assert list(s.values) == [1.0, 3.0]
    assert s.index.is_monotonic_increasing


def test_rmse_and_mape_known_values():
    actual = [100.0, 200.0]
    predicted = [110.0, 190.0]
    assert rmse(actual, predicted) == pytest.approx(10.0)
    assert mape(actual, predicted) == pytest.approx(7.5)  # (10% + 5%) / 2


def test_backtest_split_holds_out_tail():
    s = to_series([(f"20{y:02d}", float(y)) for y in range(10, 20)])
    train, test = backtest_split(s, holdout=3)
    assert len(train) == 7
    assert len(test) == 3
    assert list(test.values) == [17.0, 18.0, 19.0]


def test_naive_last_repeats_final_value():
    s = to_series([("2024-01", 1.0), ("2024-02", 5.0)])
    assert naive_last(s, horizon=3) == [5.0, 5.0, 5.0]


def test_drift_extrapolates_linear_trend():
    s = to_series([("2024-01", 1.0), ("2024-02", 2.0), ("2024-03", 3.0)])
    assert drift(s, horizon=2) == pytest.approx([4.0, 5.0])


def test_seasonal_naive_repeats_last_season():
    values = [(f"2023-{m:02d}", float(m)) for m in range(1, 13)]
    s = to_series(values)
    forecast = seasonal_naive(s, horizon=3, season=12)
    assert forecast == [1.0, 2.0, 3.0]
