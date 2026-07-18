import pandas as pd


def naive_last(series: pd.Series, horizon: int) -> list[float]:
    return [float(series.iloc[-1])] * horizon


def drift(series: pd.Series, horizon: int) -> list[float]:
    if len(series) < 2:
        return naive_last(series, horizon)
    slope = (float(series.iloc[-1]) - float(series.iloc[0])) / (len(series) - 1)
    last = float(series.iloc[-1])
    return [last + slope * (i + 1) for i in range(horizon)]


def seasonal_naive(series: pd.Series, horizon: int, season: int) -> list[float]:
    if len(series) < season:
        return naive_last(series, horizon)
    last_season = [float(v) for v in series.iloc[-season:]]
    return [last_season[i % season] for i in range(horizon)]
