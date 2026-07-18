"""Additional predictive algorithms: Theta, gradient-boosted ML, Monte Carlo, ensemble."""
import warnings

import numpy as np
import pandas as pd

from app.forecasting.result import ForecastResult, compute_backtest
from app.forecasting.series import future_index, infer_periods_per_year

Z80, Z95 = 1.282, 1.96


def _dates(series: pd.Series, horizon: int) -> list[str]:
    return [d.strftime("%Y-%m-%d") for d in future_index(series, horizon)]


def _bands(point: list[float], sigma: float) -> dict:
    steps = np.sqrt(np.arange(1, len(point) + 1))
    return {
        "lower_80": [p - Z80 * sigma * s for p, s in zip(point, steps)],
        "upper_80": [p + Z80 * sigma * s for p, s in zip(point, steps)],
        "lower_95": [p - Z95 * sigma * s for p, s in zip(point, steps)],
        "upper_95": [p + Z95 * sigma * s for p, s in zip(point, steps)],
    }


# --- Theta ------------------------------------------------------------------
def _fit_theta(series: pd.Series):
    from statsmodels.tsa.forecasting.theta import ThetaModel

    period = infer_periods_per_year(series)
    deseasonalize = period >= 4 and len(series) >= 2 * period
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = ThetaModel(
            series, period=period if deseasonalize else 1, deseasonalize=deseasonalize
        )
        return model.fit(), deseasonalize


def theta_forecast(series: pd.Series, horizon: int) -> ForecastResult:
    fit, deseasonalized = _fit_theta(series)
    point = [float(v) for v in fit.forecast(horizon)]
    ci80 = fit.prediction_intervals(horizon, alpha=0.2)
    ci95 = fit.prediction_intervals(horizon, alpha=0.05)

    def refit_predict(train, h):
        refit, _ = _fit_theta(train)
        return [float(v) for v in refit.forecast(h)]

    return ForecastResult(
        model_name="Theta",
        forecast_dates=_dates(series, horizon),
        point=point,
        lower_80=[float(v) for v in ci80.iloc[:, 0]],
        upper_80=[float(v) for v in ci80.iloc[:, 1]],
        lower_95=[float(v) for v in ci95.iloc[:, 0]],
        upper_95=[float(v) for v in ci95.iloc[:, 1]],
        metadata={"deseasonalized": deseasonalized, "n_obs": len(series)},
        backtest=compute_backtest(series, refit_predict),
    )


# --- Gradient boosting on lag features -------------------------------------
def _lag_matrix(values: np.ndarray, n_lags: int):
    X, y = [], []
    for i in range(n_lags, len(values)):
        X.append(values[i - n_lags:i])
        y.append(values[i])
    return np.array(X), np.array(y)


def _fit_gbm(series: pd.Series):
    from sklearn.ensemble import GradientBoostingRegressor

    values = series.to_numpy(dtype=float)
    n_lags = int(min(12, max(4, len(values) // 5)))
    X, y = _lag_matrix(values, n_lags)
    model = GradientBoostingRegressor(random_state=7).fit(X, y)
    residuals = y - model.predict(X)
    return model, n_lags, float(np.std(residuals))


def _gbm_predict(model, values: np.ndarray, n_lags: int, horizon: int) -> list[float]:
    window = list(values[-n_lags:])
    out = []
    for _ in range(horizon):
        nxt = float(model.predict(np.array(window[-n_lags:]).reshape(1, -1))[0])
        out.append(nxt)
        window.append(nxt)
    return out


def gbm_forecast(series: pd.Series, horizon: int) -> ForecastResult:
    model, n_lags, sigma = _fit_gbm(series)
    point = _gbm_predict(model, series.to_numpy(dtype=float), n_lags, horizon)

    def refit_predict(train, h):
        m, lags, _ = _fit_gbm(train)
        return _gbm_predict(m, train.to_numpy(dtype=float), lags, h)

    return ForecastResult(
        model_name="Gradient Boosting (lags)",
        forecast_dates=_dates(series, horizon),
        point=point,
        **_bands(point, sigma),
        metadata={"n_lags": n_lags, "resid_sigma": sigma, "n_obs": len(series)},
        backtest=compute_backtest(series, refit_predict),
    )


# --- Monte Carlo bootstrap --------------------------------------------------
def montecarlo_forecast(
    series: pd.Series, horizon: int, n_paths: int = 1000
) -> ForecastResult:
    rng = np.random.default_rng(7)
    diffs = series.diff().dropna().to_numpy(dtype=float)
    if len(diffs) < 4:
        raise ValueError("Series too short for Monte Carlo simulation")
    last = float(series.iloc[-1])
    steps = rng.choice(diffs, size=(n_paths, horizon), replace=True)
    paths = last + np.cumsum(steps, axis=1)

    percentile = lambda q: [float(v) for v in np.percentile(paths, q, axis=0)]  # noqa: E731

    def refit_predict(train, h):
        r = np.random.default_rng(7)
        d = train.diff().dropna().to_numpy(dtype=float)
        p = float(train.iloc[-1]) + np.cumsum(
            r.choice(d, size=(n_paths, h), replace=True), axis=1
        )
        return [float(v) for v in np.median(p, axis=0)]

    return ForecastResult(
        model_name="Monte Carlo (bootstrap)",
        forecast_dates=_dates(series, horizon),
        point=percentile(50),
        lower_80=percentile(10),
        upper_80=percentile(90),
        lower_95=percentile(2.5),
        upper_95=percentile(97.5),
        metadata={
            "n_paths": n_paths,
            "method": "bootstrap of historical first differences",
            "n_obs": len(series),
        },
        backtest=compute_backtest(series, refit_predict),
    )


# --- Ensemble ---------------------------------------------------------------
def ensemble_forecast(series: pd.Series, horizon: int) -> ForecastResult:
    from app.forecasting.univariate import arima_forecast, ets_forecast

    candidates = [
        ("arima", lambda s, h: arima_forecast(s, h)),
        ("ets", lambda s, h: ets_forecast(s, h)),
        ("theta", lambda s, h: theta_forecast(s, h)),
    ]
    members: list[tuple[str, ForecastResult]] = []
    for name, fn in candidates:
        try:
            members.append((name, fn(series, horizon)))
        except Exception:
            continue
    if len(members) < 2:
        raise ValueError("Ensemble needs at least two successful member models")

    mean_of = lambda attr: [  # noqa: E731
        float(np.mean([getattr(r, attr)[i] for _, r in members]))
        for i in range(horizon)
    ]

    def refit_predict(train, h):
        preds = []
        for name, fn in candidates:
            try:
                preds.append(fn(train, h).point)
            except Exception:
                continue
        return [float(np.mean([p[i] for p in preds])) for i in range(h)]

    return ForecastResult(
        model_name="Ensemble",
        forecast_dates=_dates(series, horizon),
        point=mean_of("point"),
        lower_80=mean_of("lower_80"),
        upper_80=mean_of("upper_80"),
        lower_95=mean_of("lower_95"),
        upper_95=mean_of("upper_95"),
        metadata={
            "members": [r.model_name for _, r in members],
            "member_backtests": {
                name: r.backtest for name, r in members if "model_rmse" in r.backtest
            },
            "n_obs": len(series),
        },
        backtest=compute_backtest(series, refit_predict),
    )
