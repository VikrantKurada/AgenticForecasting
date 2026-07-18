from dataclasses import asdict, dataclass, field

import pandas as pd

from app.forecasting.baselines import naive_last
from app.forecasting.metrics import backtest_split, mape, rmse


@dataclass
class ForecastResult:
    model_name: str
    forecast_dates: list[str]
    point: list[float]
    lower_80: list[float] = field(default_factory=list)
    upper_80: list[float] = field(default_factory=list)
    lower_95: list[float] = field(default_factory=list)
    upper_95: list[float] = field(default_factory=list)
    fitted: list[float] | None = None
    metadata: dict = field(default_factory=dict)
    backtest: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def compute_backtest(series: pd.Series, predict_fn, holdout: int | None = None) -> dict:
    """Refit on a training slice and score against the held-out tail vs a naive baseline."""
    holdout = holdout or min(6, max(2, len(series) // 5))
    if len(series) < holdout + 8:
        return {"holdout": 0, "note": "series too short for backtest"}
    train, test = backtest_split(series, holdout)
    actual = list(test.values)
    baseline = naive_last(train, len(test))
    try:
        predicted = predict_fn(train, len(test))
        model_rmse, model_mape = rmse(actual, predicted), mape(actual, predicted)
    except Exception as exc:
        return {"holdout": len(test), "note": f"backtest refit failed: {exc}"}
    return {
        "holdout": len(test),
        "model_rmse": model_rmse,
        "model_mape": model_mape,
        "baseline_rmse": rmse(actual, baseline),
        "baseline_mape": mape(actual, baseline),
    }
