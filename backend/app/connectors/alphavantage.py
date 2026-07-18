"""Alpha Vantage (key required): equities, forex, and crypto daily series.

Series IDs: "EQ:SPY", "FX:EUR/USD", "CRYPTO:BTC/USD".
"""
import httpx

from app.connectors.base import ConnectorError, SeriesData, SeriesMeta, request_json

BASE = "https://www.alphavantage.co/query"

CATALOG = [
    ("EQ:SPY", "S&P 500 ETF (SPY) daily close"),
    ("EQ:QQQ", "Nasdaq-100 ETF (QQQ) daily close"),
    ("EQ:AAPL", "Apple (AAPL) daily close"),
    ("FX:EUR/USD", "EUR/USD exchange rate, daily"),
    ("FX:USD/JPY", "USD/JPY exchange rate, daily"),
    ("CRYPTO:BTC/USD", "Bitcoin/USD daily close"),
    ("CRYPTO:ETH/USD", "Ethereum/USD daily close"),
]


def _close_value(row: dict) -> float | None:
    for key, value in row.items():
        if "close" in key.lower():
            try:
                return float(value)
            except (TypeError, ValueError):
                return None
    return None


class AlphaVantageConnector:
    source = "alphavantage"

    def __init__(self, api_key: str = "", client: httpx.Client | None = None):
        self.api_key = api_key
        self.client = client or httpx.Client(follow_redirects=True)

    def search(self, query: str, limit: int = 10) -> list[SeriesMeta]:
        words = query.lower().split()
        hits = [
            SeriesMeta(source=self.source, series_id=code, title=title, frequency="Daily")
            for code, title in CATALOG
            if any(w in title.lower() or w in code.lower() for w in words)
        ]
        return (hits or [
            SeriesMeta(source=self.source, series_id=c, title=t) for c, t in CATALOG
        ])[:limit]

    def fetch(self, series_id: str, **params) -> SeriesData:
        if not self.api_key:
            raise ConnectorError(
                "Alpha Vantage requires an API key. Add one in Settings → Data sources "
                "(free at alphavantage.co)."
            )
        if ":" not in series_id:
            raise ConnectorError(
                f"Alpha Vantage series id must be 'EQ:SYM', 'FX:AAA/BBB' or "
                f"'CRYPTO:SYM/MKT', got '{series_id}'"
            )
        kind, symbol = series_id.split(":", 1)
        kind = kind.upper()
        query: dict = {"apikey": self.api_key, "outputsize": "full", **params}
        if kind == "EQ":
            query.update({"function": "TIME_SERIES_DAILY", "symbol": symbol})
        elif kind == "FX":
            base, quote = symbol.split("/", 1)
            query.update({"function": "FX_DAILY", "from_symbol": base, "to_symbol": quote})
        elif kind == "CRYPTO":
            coin, market = symbol.split("/", 1)
            query.update({"function": "DIGITAL_CURRENCY_DAILY", "symbol": coin, "market": market})
        else:
            raise ConnectorError(f"Unknown Alpha Vantage kind '{kind}' (EQ, FX, CRYPTO)")

        payload = request_json(self.client, BASE, query)
        for err_key in ("Error Message", "Note", "Information"):
            if err_key in payload:
                raise ConnectorError(f"Alpha Vantage: {payload[err_key]}")
        series_key = next((k for k in payload if "Time Series" in k), None)
        if series_key is None:
            raise ConnectorError(f"Alpha Vantage returned no time series for '{series_id}'")
        observations = [
            (date, _close_value(row)) for date, row in payload[series_key].items()
        ]
        observations.sort(key=lambda t: t[0])
        title = next((t for c, t in CATALOG if c == series_id), series_id)
        return SeriesData(
            meta=SeriesMeta(source=self.source, series_id=series_id, title=title,
                            frequency="Daily"),
            observations=observations,
        )
