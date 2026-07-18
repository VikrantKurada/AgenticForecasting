"""ARIMA and ETS univariate forecasters (statsmodels)."""
import warnings

import numpy as np
import pandas as pd

from app.forecasting.result import ForecastResult, compute_backtest
from app.forecasting.series import future_index


def _fit_sarimax(series: pd.Series, order):
    from statsmodels.tsa.statespace.sarimax import SARIMAX

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = SARIMAX(
            series, order=order, enforce_stationarity=False, enforce_invertibility=False
        )
        return model.fit(disp=False)


def _select_order(series: pd.Series):
    best_order, best_aic = (1, 1, 1), np.inf
    for p in range(3):
        for d in range(2):
            for q in range(3):
                if p == 0 and q == 0:
                    continue
                try:
                    fit = _fit_sarimax(series, (p, d, q))
                except Exception:
                    continue
                if fit.aic < best_aic:
                    best_aic, best_order = fit.aic, (p, d, q)
    return best_order


def arima_forecast(series: pd.Series, horizon: int, order: tuple | None = None) -> ForecastResult:
    order = order or _select_order(series)
    fit = _fit_sarimax(series, order)
    forecast = fit.get_forecast(steps=horizon)
    point = [float(v) for v in forecast.predicted_mean]
    ci80 = forecast.conf_int(alpha=0.2)
    ci95 = forecast.conf_int(alpha=0.05)
    dates = [d.strftime("%Y-%m-%d") for d in future_index(series, horizon)]

    def refit_predict(train, h):
        return [float(v) for v in _fit_sarimax(train, order).get_forecast(h).predicted_mean]

    return ForecastResult(
        model_name=f"ARIMA{order}",
        forecast_dates=dates,
        point=point,
        lower_80=[float(v) for v in ci80.iloc[:, 0]],
        upper_80=[float(v) for v in ci80.iloc[:, 1]],
        lower_95=[float(v) for v in ci95.iloc[:, 0]],
        upper_95=[float(v) for v in ci95.iloc[:, 1]],
        fitted=[float(v) for v in fit.fittedvalues],
        metadata={
            "order": list(order),
            "aic": float(fit.aic),
            "bic": float(fit.bic),
            "n_obs": len(series),
        },
        backtest=compute_backtest(series, refit_predict),
    )


def ets_forecast(series: pd.Series, horizon: int) -> ForecastResult:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fit = ExponentialSmoothing(series, trend="add", damped_trend=True).fit()
    point = [float(v) for v in fit.forecast(horizon)]
    resid_sigma = float(np.std(fit.resid)) if len(fit.resid) else 0.0
    steps = np.sqrt(np.arange(1, horizon + 1))
    dates = [d.strftime("%Y-%m-%d") for d in future_index(series, horizon)]

    def band(z):
        return [z * resid_sigma * s for s in steps]

    def refit_predict(train, h):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            refit = ExponentialSmoothing(train, trend="add", damped_trend=True).fit()
        return [float(v) for v in refit.forecast(h)]

    return ForecastResult(
        model_name="ETS(A,Ad,N)",
        forecast_dates=dates,
        point=point,
        lower_80=[p - b for p, b in zip(point, band(1.282))],
        upper_80=[p + b for p, b in zip(point, band(1.282))],
        lower_95=[p - b for p, b in zip(point, band(1.96))],
        upper_95=[p + b for p, b in zip(point, band(1.96))],
        fitted=[float(v) for v in fit.fittedvalues],
        metadata={"trend": "additive damped", "resid_sigma": resid_sigma, "n_obs": len(series)},
        backtest=compute_backtest(series, refit_predict),
    )
