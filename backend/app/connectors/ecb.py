"""ECB Data Portal API. Series IDs: "FLOW/KEY", e.g. "ICP/M.U2.N.000000.4.ANR"."""
import httpx

from app.connectors.base import ConnectorError, SeriesData, SeriesMeta, request_json
from app.connectors.sdmx import parse_sdmx_observations

BASE = "https://data-api.ecb.europa.eu/service/data"

CATALOG = [
    ("ICP/M.U2.N.000000.4.ANR", "HICP inflation, Euro area (annual rate, monthly)"),
    ("ICP/M.U2.N.XEF000.4.ANR", "Core HICP inflation, Euro area (ex energy/food)"),
    ("MNA/Q.Y.I9.W2.S1.S1.B.B1GQ._Z._Z._Z.EUR.LR.GY", "Real GDP growth, Euro area (quarterly)"),
    ("FM/B.U2.EUR.4F.KR.MRR_FR.LEV", "ECB main refinancing rate"),
    ("YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y", "Euro area 10-year government bond yield"),
    ("YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y", "Euro area 2-year government bond yield"),
    ("EXR/D.USD.EUR.SP00.A", "EUR/USD exchange rate (daily)"),
    ("LFSI/M.I9.S.UNEHRT.TOTAL0.15_74.T", "Unemployment rate, Euro area"),
]


class ECBConnector:
    source = "ecb"

    def __init__(self, client: httpx.Client | None = None):
        self.client = client or httpx.Client()

    def search(self, query: str, limit: int = 10) -> list[SeriesMeta]:
        words = query.lower().split()
        hits = [
            SeriesMeta(source=self.source, series_id=code, title=title)
            for code, title in CATALOG
            if any(w in title.lower() or w in code.lower() for w in words)
        ]
        return (hits or [SeriesMeta(source=self.source, series_id=c, title=t) for c, t in CATALOG])[:limit]

    def fetch(self, series_id: str, **params) -> SeriesData:
        if "/" not in series_id:
            raise ConnectorError(f"ECB series id must be 'FLOW/KEY', got '{series_id}'")
        flow, key = series_id.split("/", 1)
        payload = request_json(
            self.client, f"{BASE}/{flow}/{key}", {"format": "jsondata", **params}
        )
        observations = parse_sdmx_observations(payload, series_id)
        title = payload.get("structure", {}).get("name", series_id)
        return SeriesData(
            meta=SeriesMeta(source=self.source, series_id=series_id, title=title),
            observations=observations,
        )
