"""FAO FAOSTAT (no key): global agricultural commodity production, area, trade.

Series IDs: "DOMAIN/AREA/ELEMENT/ITEM", e.g. "QCL/5000/5510/15" =
crops & livestock / World / Production (t) / Wheat.
"""
import httpx

from app.connectors.base import ConnectorError, SeriesData, SeriesMeta, request_json

BASE = "https://faostatservices.fao.org/api/v1/en"

# (series_id, title) - domain QCL, area 5000 = World, element 5510 = production (t)
CATALOG = [
    ("QCL/5000/5510/15", "World Wheat production (tonnes, annual)"),
    ("QCL/5000/5510/56", "World Maize production (tonnes, annual)"),
    ("QCL/5000/5510/27", "World Rice production (tonnes, annual)"),
    ("QCL/5000/5510/236", "World Soybean production (tonnes, annual)"),
    ("QCL/5000/5510/156", "World Sugar Cane production (tonnes, annual)"),
    ("QCL/5000/5510/656", "World Green Coffee production (tonnes, annual)"),
    ("QCL/5000/5312/15", "World Wheat area harvested (ha, annual)"),
    ("FBS/5000/664/2901", "World food supply per capita (kcal/day, annual)"),
]


class FAOSTATConnector:
    source = "faostat"

    def __init__(self, client: httpx.Client | None = None):
        self.client = client or httpx.Client(follow_redirects=True)

    def search(self, query: str, limit: int = 10) -> list[SeriesMeta]:
        words = query.lower().split()
        hits = [
            SeriesMeta(source=self.source, series_id=code, title=title, frequency="Annual")
            for code, title in CATALOG
            if any(w in title.lower() for w in words)
        ]
        return hits[:limit]  # no match means no match — never return filler

    def fetch(self, series_id: str, **params) -> SeriesData:
        parts = series_id.split("/")
        if len(parts) != 4:
            raise ConnectorError(
                f"FAOSTAT series id must be 'DOMAIN/AREA/ELEMENT/ITEM', got '{series_id}'"
            )
        domain, area, element, item = parts
        payload = request_json(
            self.client, f"{BASE}/data/{domain}",
            {"area": area, "element": element, "item": item,
             "output_type": "objects", **params},
        )
        rows = payload.get("data", [])
        if not rows:
            raise ConnectorError(f"FAOSTAT returned no data for '{series_id}'")
        observations = []
        item_name = ""
        for row in rows:
            year = row.get("Year")
            value = row.get("Value")
            item_name = row.get("Item", item_name)
            if year is None:
                continue
            observations.append(
                (str(year), float(value) if value is not None else None)
            )
        observations.sort(key=lambda t: t[0])
        title = next(
            (t for c, t in CATALOG if c == series_id),
            f"{item_name or series_id} ({domain})",
        )
        return SeriesData(
            meta=SeriesMeta(source=self.source, series_id=series_id, title=title,
                            frequency="Annual"),
            observations=observations,
        )
