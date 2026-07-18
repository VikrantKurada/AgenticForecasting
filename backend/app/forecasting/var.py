"""Vector autoregression for multivariate trajectories and spillover analysis."""
import warnings

import pandas as pd

from app.forecasting.result import ForecastResult
from app.forecasting.series import future_index


def var_forecast(df: pd.DataFrame, target: str, horizon: int, maxlags: int = 4) -> ForecastResult:
    # Import from the concrete module: the tsa.api aggregate eagerly imports
    # regime-switching C extensions that Windows App Control can block.
    from statsmodels.tsa.vector_ar.var_model import VAR

    df = df.dropna()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = VAR(df)
        fit = model.fit(maxlags=min(maxlags, len(df) // 4), ic="aic")
    lag_order = fit.k_ar or 1
    history = df.values[-lag_order:]
    target_idx = list(df.columns).index(target)

    point_all, lower80, upper80 = fit.forecast_interval(history, steps=horizon, alpha=0.2)
    _, lower95, upper95 = fit.forecast_interval(history, steps=horizon, alpha=0.05)
    target_series = df[target]
    dates = [d.strftime("%Y-%m-%d") for d in future_index(target_series, horizon)]

    return ForecastResult(
        model_name=f"VAR({lag_order})",
        forecast_dates=dates,
        point=[float(v[target_idx]) for v in point_all],
        lower_80=[float(v[target_idx]) for v in lower80],
        upper_80=[float(v[target_idx]) for v in upper80],
        lower_95=[float(v[target_idx]) for v in lower95],
        upper_95=[float(v[target_idx]) for v in upper95],
        metadata={
            "variables": list(df.columns),
            "target": target,
            "lag_order": int(lag_order),
            "aic": float(fit.aic),
            "n_obs": len(df),
        },
    )
