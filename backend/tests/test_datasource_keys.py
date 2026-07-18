import pytest
from fastapi.testclient import TestClient

from app.connectors.catalog import CATEGORIES, SOURCES
from app.connectors.keys import get_datasource_key
from app.db import init_db, make_engine, make_session_factory
from app.main import create_app

REQUIRED_SOURCES = {
    # Sovereign & macro
    "fred", "bls", "bea", "eia", "treasury", "census", "ecb", "boe",
    "bank_of_london", "bundesbank", "rbi", "cnb", "eurostat", "gus",
    "undata", "faostat", "worldbank", "imf", "oecd",
    # Aggregators
    "dbnomics", "chinadata",
    # Equities / FX / crypto
    "polygon", "finnhub", "alphavantage", "fmp", "twelvedata",
    "eodhd", "tiingo", "marketstack",
    # Brokerage
    "alpaca", "tradier",
    # Fixed income & commodities
    "apininjas", "commoditiesapi", "cbonds", "usda_psd", "jodi",
    # Alternative / civic / real estate
    "companieshouse", "globalscreen", "landregistry", "propertydata",
    "homedata", "idealpostcodes", "geodojo", "civiq",
}


@pytest.fixture
def env(tmp_path):
    engine = make_engine(f"sqlite:///{(tmp_path / 'keys.db').as_posix()}")
    init_db(engine)
    factory = make_session_factory(engine)
    return TestClient(create_app(session_factory=factory)), factory


def test_catalog_covers_all_requested_sources():
    names = {s["name"] for s in SOURCES}
    missing = REQUIRED_SOURCES - names
    assert not missing, f"catalog missing: {sorted(missing)}"
    for source in SOURCES:
        assert source["category"] in CATEGORIES
        assert source["label"]
        assert isinstance(source["needs_key"], bool)
        assert isinstance(source["implemented"], bool)


def test_keys_endpoint_masks_and_never_returns_raw(env):
    client, _ = env
    resp = client.put(
        "/api/settings/datasource-keys",
        json={"keys": {"alphavantage": "SECRETKEY1234"}},
    )
    assert resp.status_code == 200
    data = client.get("/api/settings/datasource-keys").json()
    assert data["alphavantage"]["present"] is True
    assert data["alphavantage"]["masked"].endswith("1234")
    assert "SECRETKEY1234" not in str(data)


def test_put_empty_string_removes_key(env):
    client, _ = env
    client.put("/api/settings/datasource-keys", json={"keys": {"eia": "abc123xyz"}})
    client.put("/api/settings/datasource-keys", json={"keys": {"eia": ""}})
    data = client.get("/api/settings/datasource-keys").json()
    assert data["eia"]["present"] is False


def test_get_datasource_key_prefers_db_over_env(env, monkeypatch):
    client, factory = env
    monkeypatch.setenv("FRED_API_KEY", "env-key")
    from app.config import settings

    monkeypatch.setattr(settings, "fred_api_key", "env-key")
    assert get_datasource_key(factory, "fred") == "env-key"
    client.put("/api/settings/datasource-keys", json={"keys": {"fred": "db-key"}})
    assert get_datasource_key(factory, "fred") == "db-key"


def test_datasources_endpoint_lists_catalog_with_categories(env):
    client, _ = env
    sources = client.get("/api/datasources").json()
    names = {s["name"] for s in sources}
    assert REQUIRED_SOURCES <= names
    by_name = {s["name"]: s for s in sources}
    assert by_name["worldbank"]["available"] is True
    assert by_name["polygon"]["available"] is False
    assert by_name["polygon"]["category"] == "Equities, Forex & Crypto"
    assert by_name["faostat"]["category"] == "Fixed Income & Commodities" or by_name[
        "faostat"
    ]["category"] == "Sovereign & Macroeconomic"


def test_key_save_marks_key_present_in_datasources(env):
    client, _ = env
    client.put("/api/settings/datasource-keys", json={"keys": {"polygon": "pk_live_x"}})
    sources = {s["name"]: s for s in client.get("/api/datasources").json()}
    assert sources["polygon"]["key_present"] is True
