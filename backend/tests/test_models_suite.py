import numpy as np
import pandas as pd
import pytest

from app.forecasting.credit import fit_credit_model
from app.forecasting.nowcast import bridge_nowcast
from app.forecasting.registry import run_model
from app.forecasting.series import to_series
from app.forecasting.univariate import arima_forecast, ets_forecast
from app.forecasting.var import var_forecast
from app.forecasting.yield_curve import nelson_siegel_curve, nelson_siegel_fit

rng = np.random.default_rng(42)


def make_trend_series(n=60, start=100.0, slope=0.5, noise=0.3):
    dates = pd.date_range("2019-01-01", periods=n, freq="MS")
    values = start + slope * np.arange(n) + rng.normal(0, noise, n)
    return pd.Series(values, index=dates)


def test_arima_forecasts_trending_series_with_bands():
    s = make_trend_series()
    result = arima_forecast(s, horizon=6)
    assert len(result.point) == 6
    expected = 100 + 0.5 * (len(s) + 2)
    assert result.point[2] == pytest.approx(expected, abs=3.0)
    for i in range(6):
        assert result.lower_95[i] <= result.lower_80[i] <= result.point[i]
        assert result.point[i] <= result.upper_80[i] <= result.upper_95[i]
    assert "order" in result.metadata
    assert "model_rmse" in result.backtest and "baseline_rmse" in result.backtest


def test_ets_continues_trend():
    s = make_trend_series(noise=0.05)
    result = ets_forecast(s, horizon=3)
    assert result.point[0] > float(s.iloc[-1]) - 1.0
    assert len(result.forecast_dates) == 3


def test_var_forecasts_target_column():
    n = 80
    dates = pd.date_range("2015-01-01", periods=n, freq="QS")
    x = np.cumsum(rng.normal(0.2, 0.5, n))
    y = 0.8 * np.roll(x, 1) + rng.normal(0, 0.2, n)
    df = pd.DataFrame({"x": x, "y": y}, index=dates).iloc[1:]
    result = var_forecast(df, target="y", horizon=4)
    assert len(result.point) == 4
    assert result.metadata["variables"] == ["x", "y"]


def test_bridge_nowcast_recovers_linear_relationship():
    quarters = pd.date_range("2015-01-01", periods=32, freq="QS")
    indicator_m = pd.Series(
        np.linspace(50, 110, 96) + rng.normal(0, 0.5, 96),
        index=pd.date_range("2015-01-01", periods=96, freq="MS"),
    )
    quarterly_ind = indicator_m.resample("QS").mean()
    target = pd.Series(2.0 * quarterly_ind.values[:32] + 5.0, index=quarters)
    # target published with a lag: last quarter unknown
    result = bridge_nowcast(target.iloc[:-1], {"pmi": indicator_m})
    expected = 2.0 * quarterly_ind.iloc[31] + 5.0
    assert result.point[0] == pytest.approx(expected, rel=0.05)
    assert result.metadata["indicators"] == ["pmi"]


def test_nelson_siegel_fit_recovers_generated_curve():
    maturities = np.array([0.25, 0.5, 1, 2, 3, 5, 7, 10, 20, 30])
    true_params = {"beta0": 4.0, "beta1": -2.0, "beta2": 1.5, "tau": 1.8}
    yields = nelson_siegel_curve(maturities, **true_params)
    fitted = nelson_siegel_fit(maturities, yields)
    refit = nelson_siegel_curve(maturities, **fitted)
    assert np.allclose(refit, yields, atol=0.05)


def test_credit_model_separates_synthetic_classes():
    n = 400
    debt = rng.uniform(10, 150, n)          # debt/GDP
    growth = rng.normal(2, 2, n)            # GDP growth
    reserves = rng.uniform(0, 12, n)        # reserves months
    logit = 0.06 * debt - 0.5 * growth - 0.3 * reserves - 3.0
    prob = 1 / (1 + np.exp(-logit))
    labels = (rng.uniform(0, 1, n) < prob).astype(int)
    X = pd.DataFrame({"debt_gdp": debt, "gdp_growth": growth, "reserves_months": reserves})
    model = fit_credit_model(X, labels)
    assert 0.0 <= model["default_probability"](X.iloc[[0]])[0] <= 1.0
    assert model["accuracy"] > 0.75
    assert set(model["feature_importance"]) == {"debt_gdp", "gdp_growth", "reserves_months"}


def test_registry_dispatches_and_rejects_unknown():
    s = make_trend_series(n=40)
    result = run_model("arima", series=s, horizon=2)
    assert result.model_name.startswith("ARIMA")
    with pytest.raises(ValueError, match="Unknown model"):
        run_model("prophet", series=s, horizon=2)
