import numpy as np
import pandas as pd
import pytest

from app.forecasting.advanced import (
    ensemble_forecast,
    gbm_forecast,
    montecarlo_forecast,
    theta_forecast,
)
from app.forecasting.registry import MODEL_DESCRIPTIONS, run_model

rng = np.random.default_rng(7)


def make_series(n=72, start=100.0, slope=0.4, noise=0.4, freq="MS"):
    dates = pd.date_range("2018-01-01", periods=n, freq=freq)
    values = start + slope * np.arange(n) + rng.normal(0, noise, n)
    return pd.Series(values, index=dates)


def assert_bands_ordered(result):
    for i in range(len(result.point)):
        assert result.lower_95[i] <= result.lower_80[i] <= result.point[i]
        assert result.point[i] <= result.upper_80[i] <= result.upper_95[i]


def test_theta_forecasts_trend_with_intervals():
    s = make_series()
    result = theta_forecast(s, horizon=6)
    assert len(result.point) == 6
    expected = 100 + 0.4 * (len(s) + 2)
    assert result.point[2] == pytest.approx(expected, abs=4.0)
    assert_bands_ordered(result)
    assert "model_rmse" in result.backtest


def test_gbm_learns_lagged_structure():
    s = make_series(noise=0.2)
    result = gbm_forecast(s, horizon=4)
    assert len(result.point) == 4
    assert result.point[0] > float(s.iloc[-1]) - 3.0
    assert result.metadata["n_lags"] >= 4
    assert_bands_ordered(result)


def test_montecarlo_bands_widen_with_horizon():
    s = make_series(noise=1.0)
    result = montecarlo_forecast(s, horizon=8)
    assert len(result.point) == 8
    assert_bands_ordered(result)
    early = result.upper_95[0] - result.lower_95[0]
    late = result.upper_95[7] - result.lower_95[7]
    assert late > early
    assert result.metadata["n_paths"] >= 500


def test_ensemble_combines_members():
    s = make_series()
    result = ensemble_forecast(s, horizon=4)
    assert result.model_name == "Ensemble"
    assert len(result.metadata["members"]) >= 2
    assert len(result.point) == 4
    assert all(np.isfinite(result.point))
    assert_bands_ordered(result)


def test_registry_exposes_new_models():
    for name in ("theta", "gbm", "montecarlo", "ensemble"):
        assert name in MODEL_DESCRIPTIONS
    s = make_series(n=48)
    result = run_model("montecarlo", series=s, horizon=3)
    assert len(result.point) == 3
