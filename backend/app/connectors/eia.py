"""US Energy Information Administration API v2 (key required).

Covers US and world energy production/consumption. Series IDs use the v1-compatible
seriesid route, e.g. "STEO.PAPR_WORLD.M" (world petroleum production).
"""
import httpx

from app.connectors.base import ConnectorError, SeriesData, SeriesMeta, request_json

BASE = "https://api.eia.gov/v2"

CATALOG = [
    ("STEO.PAPR_WORLD.M", "World petroleum and liquids production (mb/d, monthly)"),
    ("STEO.PATC_WORLD.M", "World petroleum and liquids consumption (mb/d, monthly)"),
    ("PET.WCRFPUS2.W", "US crude oil field production (weekly)"),
    ("NG.N9050US2.M", "US natural gas marketed production (monthly)"),
    ("NG.N9140US2.M", "US natural gas consumption (monthly)"),
    ("ELEC.GEN.ALL-US-99.M", "US electricity net generation, all sectors (monthly)"),
    ("TOTAL.TETCBUS.A", "US total primary energy consumption (annual)"),
    ("STEO.COPR_OPEC.M", "OPEC crude oil production (monthly)"),
]


class EIAConnector:
    source = "eia"

    def __init__(self, api_key: str = "", client: httpx.Client | None = None):
        self.api_key = api_key
        self.client = client or httpx.Client(follow_redirects=True)

    def search(self, query: str, limit: int = 10) -> list[SeriesMeta]:
        words = query.lower().split()
        hits = [
            SeriesMeta(source=self.source, series_id=code, title=title)
            for code, title in CATALOG
            if any(w in title.lower() or w in code.lower() for w in words)
        ]
        return hits[:limit]  # no match means no match — never return filler

    def fetch(self, series_id: str, **params) -> SeriesData:
        if not self.api_key:
            raise ConnectorError(
                "EIA requires an API key. Add one in Settings → Data sources "
                "(free at eia.gov/opendata)."
            )
        payload = request_json(
            self.client, f"{BASE}/seriesid/{series_id}",
            {"api_key": self.api_key, **params},
        )
        rows = payload.get("response", {}).get("data", [])
        if not rows:
            raise ConnectorError(f"EIA returned no data for '{series_id}'")
        observations = []
        for row in rows:
            value = row.get("value")
            observations.append(
                (str(row.get("period", "")), float(value) if value is not None else None)
            )
        observations.sort(key=lambda t: t[0])
        title = next((t for c, t in CATALOG if c == series_id), series_id)
        return SeriesData(
            meta=SeriesMeta(source=self.source, series_id=series_id, title=title),
            observations=observations,
        )
