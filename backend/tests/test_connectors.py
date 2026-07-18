import json

import httpx
import pytest

from app.connectors.base import ConnectorError, request_json
from app.connectors.cache import CachedConnector
from app.connectors.fred import FredConnector
from app.connectors.worldbank import WorldBankConnector
from app.db import init_db, make_engine, make_session_factory

FRED_SEARCH_FIXTURE = {
    "seriess": [
        {"id": "GDPC1", "title": "Real Gross Domestic Product", "frequency": "Quarterly", "units": "Billions of Chained 2017 Dollars"},
        {"id": "GDP", "title": "Gross Domestic Product", "frequency": "Quarterly", "units": "Billions of Dollars"},
    ]
}
FRED_OBS_FIXTURE = {
    "observations": [
        {"date": "2024-01-01", "value": "22112.329"},
        {"date": "2024-04-01", "value": "."},
        {"date": "2024-07-01", "value": "22360.502"},
    ]
}
WB_DATA_FIXTURE = [
    {"page": 1, "pages": 1, "total": 2},
    [
        {"date": "2023", "value": 2.5, "indicator": {"id": "NY.GDP.MKTP.KD.ZG", "value": "GDP growth (annual %)"}},
        {"date": "2022", "value": None, "indicator": {"id": "NY.GDP.MKTP.KD.ZG", "value": "GDP growth (annual %)"}},
    ],
]


def make_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def json_response(payload, status=200):
    return httpx.Response(status, json=payload)


def test_fred_search_parses_fixture():
    fred = FredConnector(api_key="k", client=make_client(lambda req: json_response(FRED_SEARCH_FIXTURE)))
    results = fred.search("real gdp")
    assert results[0].series_id == "GDPC1"
    assert results[0].source == "fred"
    assert "Real Gross" in results[0].title


def test_fred_fetch_parses_observations_with_missing_values():
    fred = FredConnector(api_key="k", client=make_client(lambda req: json_response(FRED_OBS_FIXTURE)))
    data = fred.fetch("GDPC1")
    assert data.meta.series_id == "GDPC1"
    assert data.observations[0] == ("2024-01-01", pytest.approx(22112.329))
    assert data.observations[1] == ("2024-04-01", None)
    assert len(data.observations) == 3


def test_worldbank_fetch_parses():
    wb = WorldBankConnector(client=make_client(lambda req: json_response(WB_DATA_FIXTURE)))
    data = wb.fetch("US:NY.GDP.MKTP.KD.ZG")
    assert data.meta.source == "worldbank"
    # world bank returns newest first; connector must sort ascending by date
    assert data.observations[0][0] == "2022"
    assert data.observations[1] == ("2023", 2.5)


def test_worldbank_search_uses_curated_catalog():
    wb = WorldBankConnector(client=make_client(lambda req: json_response({})))
    results = wb.search("gdp growth")
    assert any("NY.GDP.MKTP.KD.ZG" in r.series_id for r in results)
    assert all(r.source == "worldbank" for r in results)


def test_request_json_retries_on_server_error():
    calls = {"n": 0}

    def flaky(req):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(500)
        return json_response({"ok": True})

    result = request_json(make_client(flaky), "https://x.test/api", {}, backoff=0.001)
    assert result == {"ok": True}
    assert calls["n"] == 3


def test_request_json_raises_connector_error_when_exhausted():
    with pytest.raises(ConnectorError):
        request_json(make_client(lambda req: httpx.Response(500)), "https://x.test/api", {}, retries=2, backoff=0.001)


def test_cached_connector_serves_second_fetch_from_cache(tmp_path):
    engine = make_engine(f"sqlite:///{(tmp_path / 'cache.db').as_posix()}")
    init_db(engine)
    factory = make_session_factory(engine)
    calls = {"n": 0}

    def counting(req):
        calls["n"] += 1
        return json_response(FRED_OBS_FIXTURE)

    fred = CachedConnector(FredConnector(api_key="k", client=make_client(counting)), factory)
    first = fred.fetch("GDPC1")
    second = fred.fetch("GDPC1")
    assert calls["n"] == 1
    assert json.dumps(first.observations) == json.dumps(second.observations)
