"""Named-model dispatch used by the agent forecasting tool."""
from app.forecasting.nowcast import bridge_nowcast
from app.forecasting.result import ForecastResult
from app.forecasting.univariate import arima_forecast, ets_forecast
from app.forecasting.var import var_forecast

MODEL_DESCRIPTIONS = {
    "arima": "ARIMA/SARIMAX with automatic order selection — general univariate trajectories",
    "ets": "Exponential smoothing with damped trend — smooth trending series",
    "var": "Vector autoregression — multivariate dynamics and spillovers",
    "bridge_nowcast": "Bridge/dynamic-factor regression — nowcast a quarterly target from monthly indicators",
}


def run_model(name: str, **kwargs) -> ForecastResult:
    if name == "arima":
        return arima_forecast(kwargs["series"], kwargs["horizon"], kwargs.get("order"))
    if name == "ets":
        return ets_forecast(kwargs["series"], kwargs["horizon"])
    if name == "var":
        return var_forecast(
            kwargs["df"], kwargs["target"], kwargs["horizon"], kwargs.get("maxlags", 4)
        )
    if name == "bridge_nowcast":
        return bridge_nowcast(kwargs["target"], kwargs["indicators"], kwargs.get("use_pca"))
    raise ValueError(f"Unknown model '{name}'. Available: {sorted(MODEL_DESCRIPTIONS)}")
