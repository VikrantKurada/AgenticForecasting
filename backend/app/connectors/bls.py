"""Bureau of Labor Statistics public API v2. Optional key raises rate limits."""
import httpx

from app.connectors.base import ConnectorError, SeriesData, SeriesMeta, request_json

BASE = "https://api.bls.gov/publicAPI/v2/timeseries/data"

CATALOG = [
    ("CUUR0000SA0", "CPI-U, All items, U.S. city average (monthly)"),
    ("CUUR0000SA0L1E", "CPI-U, All items less food and energy (core CPI)"),
    ("LNS14000000", "Unemployment rate (monthly, seasonally adjusted)"),
    ("CES0000000001", "Total nonfarm employment (monthly, thousands)"),
    ("CES0500000003", "Average hourly earnings, private (monthly)"),
    ("LNS11300000", "Labor force participation rate"),
    ("PRS85006092", "Nonfarm business labor productivity (quarterly)"),
    ("WPUFD4", "PPI Final Demand (monthly)"),
]

_PERIOD_MAP = {"M": "-", "Q": "-Q"}


def _period_to_date(year: str, period: str) -> str:
    kind, num = period[0], period[1:]
    if kind == "M":
        return f"{year}-{num}"
    if kind == "Q":
        return f"{year}-Q{int(num)}"
    return year  # annual (A01)


class BLSConnector:
    source = "bls"

    def __init__(self, api_key: str = "", client: httpx.Client | None = None):
        self.api_key = api_key
        self.client = client or httpx.Client()

    def search(self, query: str, limit: int = 10) -> list[SeriesMeta]:
        words = query.lower().split()
        hits = [
            SeriesMeta(source=self.source, series_id=code, title=title, frequency="Monthly")
            for code, title in CATALOG
            if any(w in title.lower() or w in code.lower() for w in words)
        ]
        return (hits or [SeriesMeta(source=self.source, series_id=c, title=t) for c, t in CATALOG])[:limit]

    def fetch(self, series_id: str, **params) -> SeriesData:
        query = dict(params)
        if self.api_key:
            query["registrationkey"] = self.api_key
        payload = request_json(self.client, f"{BASE}/{series_id}", query)
        if payload.get("status") != "REQUEST_SUCCEEDED":
            raise ConnectorError(f"BLS request failed: {payload.get('message')}")
        series_list = payload.get("Results", {}).get("series", [])
        if not series_list or not series_list[0].get("data"):
            raise ConnectorError(f"BLS returned no data for {series_id}")
        observations = [
            (_period_to_date(d["year"], d["period"]), float(d["value"]))
            for d in series_list[0]["data"]
        ]
        observations.sort(key=lambda t: t[0])
        return SeriesData(
            meta=SeriesMeta(source=self.source, series_id=series_id, title=series_id),
            observations=observations,
        )
