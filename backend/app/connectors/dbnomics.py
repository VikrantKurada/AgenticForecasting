"""DBnomics aggregator (80+ providers: ECB, BoE, Bundesbank, Eurostat, IMF, AMECO…).

Series IDs: "PROVIDER/DATASET/SERIES", e.g. "Eurostat/prc_hicp_manr/M.RCH_A.CP00.EA".
No key needed.
"""
import httpx

from app.connectors.base import ConnectorError, SeriesData, SeriesMeta, request_json

BASE = "https://api.db.nomics.world/v22"

CATALOG = [
    ("Eurostat/prc_hicp_manr/M.RCH_A.CP00.EA", "HICP inflation, euro area (Eurostat via DBnomics)"),
    ("Eurostat/une_rt_m/M.SA.TOTAL.PC_ACT.T.EA20", "Unemployment rate, euro area (Eurostat)"),
    ("AMECO/ZUTN/EA19.1.0.0.0.ZUTN", "Unemployment rate, euro area (AMECO)"),
    ("BOE/IUMABEDR/IUMABEDR", "Bank of England official Bank Rate"),
    ("BUBA/BBK01/SU0202", "German money market rate (Bundesbank)"),
    ("IMF/IFS/M.US.PCPI_IX", "US consumer price index (IMF IFS via DBnomics)"),
    ("WB/WDI/A-NY.GDP.MKTP.KD.ZG-USA", "US GDP growth (World Bank via DBnomics)"),
    ("OECD/KEI/PRINTO01.CZE.GY.M", "Industrial production, Czechia (OECD via DBnomics)"),
]


class DBnomicsConnector:
    source = "dbnomics"

    def __init__(self, client: httpx.Client | None = None):
        self.client = client or httpx.Client(follow_redirects=True)

    def search(self, query: str, limit: int = 10) -> list[SeriesMeta]:
        words = query.lower().split()
        hits = [
            SeriesMeta(source=self.source, series_id=code, title=title)
            for code, title in CATALOG
            if any(w in title.lower() or w in code.lower() for w in words)
        ]
        if hits:
            return hits[:limit]
        # Fall back to the DBnomics dataset search API
        try:
            payload = request_json(self.client, f"{BASE}/search", {"q": query, "limit": limit})
            docs = payload.get("results", {}).get("docs", [])
            return [
                SeriesMeta(
                    source=self.source,
                    series_id=f"{d.get('provider_code', '')}/{d.get('code', '')}",
                    title=f"{d.get('name', '')} (dataset — append /SERIES_CODE)",
                )
                for d in docs
                if d.get("provider_code") and d.get("code")
            ][:limit]
        except Exception:
            return [SeriesMeta(source=self.source, series_id=c, title=t) for c, t in CATALOG[:limit]]

    def fetch(self, series_id: str, **params) -> SeriesData:
        if series_id.count("/") < 2:
            raise ConnectorError(
                f"DBnomics series id must be 'PROVIDER/DATASET/SERIES', got '{series_id}'"
            )
        payload = request_json(
            self.client, f"{BASE}/series/{series_id}", {"observations": 1, **params}
        )
        docs = payload.get("series", {}).get("docs", [])
        if not docs:
            raise ConnectorError(f"DBnomics returned no series for '{series_id}'")
        doc = docs[0]
        periods = doc.get("period", [])
        values = doc.get("value", [])
        observations = [
            (str(p), float(v) if isinstance(v, (int, float)) else None)
            for p, v in zip(periods, values)
        ]
        observations.sort(key=lambda t: t[0])
        return SeriesData(
            meta=SeriesMeta(
                source=self.source, series_id=series_id,
                title=doc.get("series_name", series_id),
            ),
            observations=observations,
        )
