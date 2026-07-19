import httpx
import pytest

from app.connectors.alphavantage import AlphaVantageConnector
from app.connectors.base import ConnectorError
from app.connectors.dbnomics import DBnomicsConnector
from app.connectors.eia import EIAConnector
from app.connectors.faostat import FAOSTATConnector
from app.connectors.treasury import TreasuryConnector

DBNOMICS_FIXTURE = {
    "series": {
        "docs": [
            {
                "series_name": "HICP - Euro area (annual rate)",
                "period": ["2024-01", "2024-02", "2024-03"],
                "value": [2.8, "NA", 2.4],
            }
        ]
    }
}

TREASURY_FIXTURE = {
    "data": [
        {"record_date": "2024-02-01", "tot_pub_debt_out_amt": "34215000000000.10"},
        {"record_date": "2024-01-01", "tot_pub_debt_out_amt": "34001000000000.55"},
    ]
}

EIA_FIXTURE = {
    "response": {
        "data": [
            {"period": "2024-02", "value": 102.5},
            {"period": "2024-01", "value": 101.9},
        ]
    }
}

FAOSTAT_FIXTURE = {
    "data": [
        {"Year": 2021, "Value": 776.0, "Item": "Wheat", "Element": "Production"},
        {"Year": 2022, "Value": 808.4, "Item": "Wheat", "Element": "Production"},
    ]
}

AV_EQ_FIXTURE = {
    "Meta Data": {"2. Symbol": "SPY"},
    "Time Series (Daily)": {
        "2024-02-02": {"1. open": "494.0", "4. close": "494.35"},
        "2024-02-01": {"1. open": "490.0", "4. close": "489.20"},
    },
}


def make_client(payload):
    return httpx.Client(
        transport=httpx.MockTransport(lambda req: httpx.Response(200, json=payload))
    )


def test_dbnomics_fetch_parses_series_and_na_values():
    conn = DBnomicsConnector(client=make_client(DBNOMICS_FIXTURE))
    data = conn.fetch("Eurostat/prc_hicp_manr/M.RCH_A.CP00.EA")
    assert data.meta.source == "dbnomics"
    assert data.observations == [("2024-01", 2.8), ("2024-02", None), ("2024-03", 2.4)]
    assert "HICP" in data.meta.title


def test_dbnomics_rejects_malformed_id():
    conn = DBnomicsConnector(client=make_client(DBNOMICS_FIXTURE))
    with pytest.raises(ConnectorError, match="PROVIDER/DATASET/SERIES"):
        conn.fetch("just-one-part")


def test_treasury_fetch_parses_curated_series_ascending():
    conn = TreasuryConnector(client=make_client(TREASURY_FIXTURE))
    data = conn.fetch("debt_to_penny")
    assert data.meta.source == "treasury"
    assert data.observations[0][0] == "2024-01-01"
    assert data.observations[1][1] == pytest.approx(34215000000000.10)


def test_treasury_unknown_series_lists_catalog():
    conn = TreasuryConnector(client=make_client(TREASURY_FIXTURE))
    with pytest.raises(ConnectorError, match="debt_to_penny"):
        conn.fetch("nope")


def test_eia_fetch_requires_key():
    conn = EIAConnector(api_key="", client=make_client(EIA_FIXTURE))
    with pytest.raises(ConnectorError, match="key"):
        conn.fetch("STEO.PAPR_WORLD.M")


def test_eia_fetch_parses_series():
    conn = EIAConnector(api_key="k", client=make_client(EIA_FIXTURE))
    data = conn.fetch("STEO.PAPR_WORLD.M")
    assert data.meta.source == "eia"
    assert data.observations == [("2024-01", 101.9), ("2024-02", 102.5)]


def test_faostat_fetch_parses_year_value():
    conn = FAOSTATConnector(client=make_client(FAOSTAT_FIXTURE))
    data = conn.fetch("QCL/5000/5510/15")
    assert data.meta.source == "faostat"
    assert data.observations == [("2021", 776.0), ("2022", 808.4)]
    assert "Wheat" in data.meta.title


def test_alphavantage_requires_key():
    conn = AlphaVantageConnector(api_key="", client=make_client(AV_EQ_FIXTURE))
    with pytest.raises(ConnectorError, match="key"):
        conn.fetch("EQ:SPY")


def test_alphavantage_parses_equity_closes():
    conn = AlphaVantageConnector(api_key="k", client=make_client(AV_EQ_FIXTURE))
    data = conn.fetch("EQ:SPY")
    assert data.observations == [("2024-02-01", 489.20), ("2024-02-02", 494.35)]


def test_alphavantage_surfaces_api_errors():
    conn = AlphaVantageConnector(
        api_key="k", client=make_client({"Error Message": "Invalid API call"})
    )
    with pytest.raises(ConnectorError, match="Invalid API call"):
        conn.fetch("EQ:NOPE")


def test_all_new_connectors_have_curated_search():
    # Each connector gets a term its own catalog actually covers. Searching one
    # generic word across all of them only ever "passed" because a no-match used
    # to fall back to catalog filler, which misleads the agents downstream.
    cases = [
        (DBnomicsConnector(), "production"),
        (TreasuryConnector(), "debt"),
        (EIAConnector(api_key="k"), "production"),
        (FAOSTATConnector(), "production"),
        (AlphaVantageConnector(api_key="k"), "exchange"),
    ]
    for conn, term in cases:
        results = conn.search(term)
        assert results, f"{conn.source} search returned nothing for {term!r}"
        assert all(r.source == conn.source for r in results)


def test_curated_search_returns_nothing_for_an_unrelated_term():
    for conn in (TreasuryConnector(), EIAConnector(api_key="k"), FAOSTATConnector()):
        assert conn.search("zzzz nonexistent qqqq") == [], conn.source


def test_registry_wires_new_connectors(tmp_path):
    from app.connectors.registry import build_connectors
    from app.db import init_db, make_engine, make_session_factory

    engine = make_engine(f"sqlite:///{(tmp_path / 'wire.db').as_posix()}")
    init_db(engine)
    connectors = build_connectors(make_session_factory(engine))
    for name in ("dbnomics", "treasury", "eia", "faostat", "alphavantage"):
        assert not hasattr(connectors[name], "message"), f"{name} still a stub"
