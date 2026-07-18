"""Convert connector observations into clean pandas Series."""
import re

import pandas as pd

_QUARTER = re.compile(r"^(\d{4})-?Q([1-4])$")
_YEAR = re.compile(r"^\d{4}$")


def parse_date(raw: str) -> pd.Timestamp:
    raw = str(raw).strip()
    match = _QUARTER.match(raw)
    if match:
        year, quarter = int(match.group(1)), int(match.group(2))
        return pd.Timestamp(year=year, month=(quarter - 1) * 3 + 1, day=1)
    if _YEAR.match(raw):
        return pd.Timestamp(year=int(raw), month=1, day=1)
    return pd.Timestamp(raw)


def to_series(observations: list[tuple], name: str = "value") -> pd.Series:
    dates, values = [], []
    for date, value in observations:
        if value is None:
            continue
        dates.append(parse_date(date))
        values.append(float(value))
    series = pd.Series(values, index=pd.DatetimeIndex(dates), name=name)
    return series.sort_index()


def infer_periods_per_year(series: pd.Series) -> int:
    if len(series) < 2:
        return 1
    median_days = series.index.to_series().diff().dt.days.median()
    if median_days <= 3:
        return 252
    if median_days <= 8:
        return 52
    if median_days <= 45:
        return 12
    if median_days <= 135:
        return 4
    return 1


def future_index(series: pd.Series, horizon: int) -> pd.DatetimeIndex:
    """Extend the series index into the future at its native spacing."""
    freq = pd.infer_freq(series.index)
    if freq is None:
        step = series.index[-1] - series.index[-2] if len(series) > 1 else pd.Timedelta(days=30)
        return pd.DatetimeIndex([series.index[-1] + step * (i + 1) for i in range(horizon)])
    return pd.date_range(start=series.index[-1], periods=horizon + 1, freq=freq)[1:]
