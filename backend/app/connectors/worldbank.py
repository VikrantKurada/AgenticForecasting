"""World Bank Open Data (no key). Series IDs use "COUNTRY:INDICATOR", e.g. "US:NY.GDP.MKTP.KD.ZG"."""
import httpx

from app.connectors.base import ConnectorError, SeriesData, SeriesMeta, request_json

BASE = "https://api.worldbank.org/v2"

# The WB API has no free-text indicator search; a curated catalog of the
# macro indicators this app forecasts with, filtered by keyword.
CATALOG = [
    ("NY.GDP.MKTP.KD.ZG", "GDP growth (annual %)"),
    ("NY.GDP.MKTP.CD", "GDP (current US$)"),
    ("NY.GDP.PCAP.CD", "GDP per capita (current US$)"),
    ("FP.CPI.TOTL.ZG", "Inflation, consumer prices (annual %)"),
    ("SL.UEM.TOTL.ZS", "Unemployment, total (% of labor force)"),
    ("GC.DOD.TOTL.GD.ZS", "Central government debt, total (% of GDP)"),
    ("DT.DOD.DECT.CD", "External debt stocks, total (current US$)"),
    ("DT.TDS.DECT.EX.ZS", "Total debt service (% of exports)"),
    ("BX.KLT.DINV.WD.GD.ZS", "Foreign direct investment, net inflows (% of GDP)"),
    ("NE.EXP.GNFS.ZS", "Exports of goods and services (% of GDP)"),
    ("NE.IMP.GNFS.ZS", "Imports of goods and services (% of GDP)"),
    ("BN.CAB.XOKA.GD.ZS", "Current account balance (% of GDP)"),
    ("FI.RES.TOTL.MO", "Total reserves in months of imports"),
    ("GC.REV.XGRT.GD.ZS", "Revenue, excluding grants (% of GDP)"),
    ("FR.INR.RINR", "Real interest rate (%)"),
    ("PA.NUS.FCRF", "Official exchange rate (LCU per US$)"),
    ("NE.TRD.GNFS.ZS", "Trade (% of GDP)"),
]


class WorldBankConnector:
    source = "worldbank"

    def __init__(self, client: httpx.Client | None = None):
        self.client = client or httpx.Client()

    def search(self, query: str, limit: int = 10) -> list[SeriesMeta]:
        words = query.lower().split()
        hits = [
            SeriesMeta(source=self.source, series_id=code, title=title, frequency="Annual")
            for code, title in CATALOG
            if any(w in title.lower() or w in code.lower() for w in words)
        ]
        # No match means no match. Returning the head of the catalog as a
        # consolation prize looks like a real hit to an agent, which then
        # fetches an unrelated series or loops searching for something better.
        return hits[:limit]

    def fetch(self, series_id: str, **params) -> SeriesData:
        if ":" not in series_id:
            raise ConnectorError(
                f"World Bank series id must be 'COUNTRY:INDICATOR', got '{series_id}'. "
                f"Example for the United States: 'US:{series_id}'"
            )
        country, indicator = series_id.split(":", 1)
        payload = request_json(
            self.client,
            f"{BASE}/country/{country}/indicator/{indicator}",
            {"format": "json", "per_page": 2000, **params},
        )
        if not isinstance(payload, list) or len(payload) < 2 or payload[1] is None:
            raise ConnectorError(f"World Bank returned no data for {series_id}")
        rows = payload[1]
        title = rows[0]["indicator"]["value"] if rows else indicator
        observations = sorted(
            ((r["date"], r["value"]) for r in rows), key=lambda t: t[0]
        )
        return SeriesData(
            meta=SeriesMeta(
                source=self.source, series_id=series_id, title=f"{title} — {country}",
                frequency="Annual",
            ),
            observations=observations,
        )
