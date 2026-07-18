"""Federal Reserve Economic Data (FRED). Requires FRED_API_KEY."""
import httpx

from app.connectors.base import SeriesData, SeriesMeta, request_json

BASE = "https://api.stlouisfed.org/fred"


class FredConnector:
    source = "fred"

    def __init__(self, api_key: str, client: httpx.Client | None = None):
        self.api_key = api_key
        self.client = client or httpx.Client()

    def search(self, query: str, limit: int = 10) -> list[SeriesMeta]:
        payload = request_json(
            self.client,
            f"{BASE}/series/search",
            {
                "search_text": query, "api_key": self.api_key, "file_type": "json",
                "limit": limit, "order_by": "popularity", "sort_order": "desc",
            },
        )
        return [
            SeriesMeta(
                source=self.source, series_id=s["id"], title=s.get("title", ""),
                frequency=s.get("frequency", ""), units=s.get("units", ""),
            )
            for s in payload.get("seriess", [])
        ]

    def fetch(self, series_id: str, **params) -> SeriesData:
        query = {"series_id": series_id, "api_key": self.api_key, "file_type": "json"}
        query.update(params)
        payload = request_json(self.client, f"{BASE}/series/observations", query)
        observations = [
            (o["date"], None if o.get("value") in (".", "", None) else float(o["value"]))
            for o in payload.get("observations", [])
        ]
        return SeriesData(
            meta=SeriesMeta(source=self.source, series_id=series_id, title=series_id),
            observations=observations,
        )
