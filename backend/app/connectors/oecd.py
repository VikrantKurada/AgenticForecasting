"""OECD SDMX API. Series IDs: "AGENCY,DATAFLOW,VERSION/KEY"."""
import httpx

from app.connectors.base import ConnectorError, SeriesData, SeriesMeta, request_json
from app.connectors.sdmx import parse_sdmx_observations

BASE = "https://sdmx.oecd.org/public/rest/data"

CATALOG = [
    (
        "OECD.SDD.NAD,DSD_NAMAIN1@DF_QNA_EXPENDITURE_GROWTH_OECD,1.1/Q..USA.S1..B1GQ......G1.",
        "Quarterly GDP growth — United States",
    ),
    (
        "OECD.SDD.TPS,DSD_PRICES@DF_PRICES_ALL,1.0/USA.M.N.CPI.PA._T.N.GY",
        "CPI inflation (annual growth) — United States",
    ),
    (
        "OECD.SDD.TPS,DSD_LFS@DF_IALFS_UNE_M,1.0/USA..._Z.Y._T.Y_GE15..M",
        "Unemployment rate — United States (monthly)",
    ),
    (
        "OECD.ECO.MAD,DSD_EO@DF_EO,1.2/USA.IRL.A",
        "Long-term interest rate projections — United States",
    ),
    (
        "OECD.SDD.STES,DSD_STES@DF_CLI,4.1/USA.M.LI...AA...H",
        "Composite leading indicator — United States",
    ),
]


class OECDConnector:
    source = "oecd"

    def __init__(self, client: httpx.Client | None = None):
        self.client = client or httpx.Client(follow_redirects=True)

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
            raise ConnectorError(
                f"OECD series id must be 'AGENCY,DATAFLOW,VERSION/KEY', got '{series_id}'"
            )
        flow, key = series_id.split("/", 1)
        payload = request_json(
            self.client, f"{BASE}/{flow}/{key}",
            {"format": "jsondata", "dimensionAtObservation": "TIME_PERIOD", **params},
        )
        observations = parse_sdmx_observations(payload, series_id)
        return SeriesData(
            meta=SeriesMeta(source=self.source, series_id=series_id, title=series_id),
            observations=observations,
        )
