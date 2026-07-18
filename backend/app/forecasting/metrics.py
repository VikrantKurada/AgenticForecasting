import numpy as np
import pandas as pd


def rmse(actual, predicted) -> float:
    a, p = np.asarray(actual, dtype=float), np.asarray(predicted, dtype=float)
    return float(np.sqrt(np.mean((a - p) ** 2)))


def mape(actual, predicted) -> float:
    a, p = np.asarray(actual, dtype=float), np.asarray(predicted, dtype=float)
    mask = a != 0
    return float(np.mean(np.abs((a[mask] - p[mask]) / a[mask])) * 100)


def backtest_split(series: pd.Series, holdout: int) -> tuple[pd.Series, pd.Series]:
    holdout = min(holdout, max(1, len(series) // 3))
    return series.iloc[:-holdout], series.iloc[-holdout:]
