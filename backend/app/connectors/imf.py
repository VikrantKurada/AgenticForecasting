"""IMF SDMX JSON RESTful API. Series IDs: "DATASET/FREQ.AREA.INDICATOR", e.g. "IFS/Q.US.PCPI_IX"."""
import httpx

from app.connectors.base import ConnectorError, SeriesData, SeriesMeta, request_json

BASE = "http://dataservices.imf.org/REST/SDMX_JSON.svc"

CATALOG = [
    ("IFS/M.US.PCPI_IX", "Consumer Price Index, All items — US (monthly)"),
    ("IFS/Q.US.NGDP_R_SA_XDC", "Real GDP, seasonally adjusted — US (quarterly)"),
    ("IFS/M.GB.PCPI_IX", "Consumer Price Index — United Kingdom (monthly)"),
    ("IFS/M.U2.PCPI_IX", "Consumer Price Index — Euro Area (monthly)"),
    ("IFS/A.US.NGDP_XDC", "Nominal GDP — US (annual)"),
    ("IFS/M.US.FITB_3M_PA", "Treasury bill rate, 3-month — US"),
    ("IFS/M.US.ENDE_XDC_USD_RATE", "Exchange rate — US"),
    ("BOP/Q.US.BCA_BP6_USD", "Current account balance — US (quarterly)"),
]


class IMFConnector:
    source = "imf"

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
            raise ConnectorError(f"IMF series id must be 'DATASET/KEY', got '{series_id}'")
        dataset, key = series_id.split("/", 1)
        payload = request_json(self.client, f"{BASE}/CompactData/{dataset}/{key}", params)
        try:
            series = payload["CompactData"]["DataSet"]["Series"]
        except (KeyError, TypeError):
            raise ConnectorError(f"IMF returned no data for {series_id}")
        if isinstance(series, list):
            series = series[0]
        obs = series.get("Obs", [])
        if isinstance(obs, dict):
            obs = [obs]
        observations = [
            (o["@TIME_PERIOD"], float(o["@OBS_VALUE"]) if o.get("@OBS_VALUE") not in (None, "") else None)
            for o in obs
        ]
        observations.sort(key=lambda t: t[0])
        return SeriesData(
            meta=SeriesMeta(source=self.source, series_id=series_id, title=series_id),
            observations=observations,
        )
