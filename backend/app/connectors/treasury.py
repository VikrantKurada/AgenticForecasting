"""US Treasury Fiscal Data API (no key). Curated series over fiscaldata endpoints."""
import httpx

from app.connectors.base import ConnectorError, SeriesData, SeriesMeta, request_json

BASE = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"

# series_id -> (endpoint, date_field, value_field, title, extra_params)
CATALOG: dict[str, tuple] = {
    "debt_to_penny": (
        "/v2/accounting/od/debt_to_penny", "record_date", "tot_pub_debt_out_amt",
        "Total US public debt outstanding (daily)", {},
    ),
    "avg_interest_rate": (
        "/v2/accounting/od/avg_interest_rates", "record_date", "avg_interest_rate_amt",
        "Average interest rate on total marketable US Treasury securities",
        {"filter": "security_desc:eq:Total Marketable"},
    ),
    "operating_cash_balance": (
        "/v1/accounting/dts/operating_cash_balance", "record_date", "open_today_bal",
        "Treasury General Account opening balance (daily)",
        {"filter": "account_type:eq:Treasury General Account (TGA) Opening Balance"},
    ),
    "monthly_receipts": (
        "/v1/accounting/mts/mts_table_1", "record_date", "current_month_gross_rcpt_amt",
        "Monthly Treasury Statement gross receipts",
        {"filter": "line_code_nbr:eq:110"},
    ),
}


class TreasuryConnector:
    source = "treasury"

    def __init__(self, client: httpx.Client | None = None):
        self.client = client or httpx.Client(follow_redirects=True)

    def search(self, query: str, limit: int = 10) -> list[SeriesMeta]:
        words = query.lower().split()
        hits = [
            SeriesMeta(source=self.source, series_id=sid, title=spec[3])
            for sid, spec in CATALOG.items()
            if any(w in spec[3].lower() or w in sid for w in words)
        ]
        return hits[:limit]  # no match means no match — never return filler

    def fetch(self, series_id: str, **params) -> SeriesData:
        spec = CATALOG.get(series_id)
        if spec is None:
            raise ConnectorError(
                f"Unknown Treasury series '{series_id}'. Available: {sorted(CATALOG)}"
            )
        endpoint, date_field, value_field, title, extra = spec
        query = {
            "sort": f"-{date_field}",
            "page[size]": 2000,
            "fields": f"{date_field},{value_field}",
            **extra,
            **params,
        }
        payload = request_json(self.client, f"{BASE}{endpoint}", query)
        rows = payload.get("data", [])
        if not rows:
            raise ConnectorError(f"Treasury returned no data for '{series_id}'")
        observations = []
        for row in rows:
            raw = row.get(value_field)
            try:
                value = float(raw) if raw not in (None, "", "null") else None
            except (TypeError, ValueError):
                value = None
            observations.append((row.get(date_field, ""), value))
        observations.sort(key=lambda t: t[0])
        return SeriesData(
            meta=SeriesMeta(source=self.source, series_id=series_id, title=title),
            observations=observations,
        )
