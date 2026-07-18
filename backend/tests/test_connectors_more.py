import httpx
import pytest
from fastapi.testclient import TestClient

from app.connectors.base import ConnectorError
from app.connectors.bls import BLSConnector
from app.connectors.ecb import ECBConnector
from app.connectors.imf import IMFConnector
from app.connectors.oecd import OECDConnector
from app.connectors.registry import build_connectors, datasource_catalog
from app.connectors.stubs import StubConnector
from app.db import init_db, make_engine, make_session_factory
from app.main import create_app

IMF_FIXTURE = {
    "CompactData": {
        "DataSet": {
            "Series": {
                "@FREQ": "Q",
                "@REF_AREA": "US",
                "@INDICATOR": "PCPI_IX",
                "Obs": [
                    {"@TIME_PERIOD": "2023-Q1", "@OBS_VALUE": "302.5"},
                    {"@TIME_PERIOD": "2023-Q2", "@OBS_VALUE": "304.1"},
                ],
            }
        }
    }
}

BLS_FIXTURE = {
    "status": "REQUEST_SUCCEEDED",
    "Results": {
        "series": [
            {
                "seriesID": "CUUR0000SA0",
                "data": [
                    {"year": "2024", "period": "M02", "periodName": "February", "value": "310.326"},
                    {"year": "2024", "period": "M01", "periodName": "January", "value": "308.417"},
                ],
            }
        ]
    },
}

ECB_FIXTURE = {
    "dataSets": [
        {"series": {"0:0:0:0:0:0": {"observations": {"0": [2.9], "1": [2.8]}}}}
    ],
    "structure": {
        "name": "HICP - Overall index",
        "dimensions": {
            "observation": [
                {"id": "TIME_PERIOD", "values": [{"id": "2024-01"}, {"id": "2024-02"}]}
            ]
        },
    },
}

OECD_FIXTURE = {
    "data": {
        "dataSets": [
            {"series": {"0:0:0": {"observations": {"0": [1.4], "1": [1.6]}}}}
        ],
        "structures": [
            {
                "dimensions": {
                    "observation": [
                        {"id": "TIME_PERIOD", "values": [{"id": "2023-Q3"}, {"id": "2023-Q4"}]}
                    ]
                }
            }
        ],
    }
}


def make_client(payload):
    return httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, json=payload)))


def test_imf_fetch_parses_compact_data():
    imf = IMFConnector(client=make_client(IMF_FIXTURE))
    data = imf.fetch("IFS/Q.US.PCPI_IX")
    assert data.meta.source == "imf"
    assert data.observations == [("2023-Q1", 302.5), ("2023-Q2", 304.1)]


def test_bls_fetch_parses_monthly_ascending():
    bls = BLSConnector(client=make_client(BLS_FIXTURE))
    data = bls.fetch("CUUR0000SA0")
    assert data.meta.source == "bls"
    assert data.observations == [("2024-01", 308.417), ("2024-02", 310.326)]


def test_ecb_fetch_parses_sdmx_json():
    ecb = ECBConnector(client=make_client(ECB_FIXTURE))
    data = ecb.fetch("ICP/M.U2.N.000000.4.ANR")
    assert data.meta.source == "ecb"
    assert data.observations == [("2024-01", 2.9), ("2024-02", 2.8)]


def test_oecd_fetch_parses_wrapped_sdmx_json():
    oecd = OECDConnector(client=make_client(OECD_FIXTURE))
    data = oecd.fetch("OECD.SDD.NAD,DSD_NAMAIN1@DF_QNA,1.1/Q..USA.S1..B1GQ......G1.")
    assert data.meta.source == "oecd"
    assert data.observations == [("2023-Q3", 1.4), ("2023-Q4", 1.6)]


def test_all_connectors_have_curated_search():
    for conn in (IMFConnector(), BLSConnector(), ECBConnector(), OECDConnector()):
        results = conn.search("inflation")
        assert results, f"{conn.source} search returned nothing"
        assert all(r.source == conn.source for r in results)


def test_stub_connector_raises_helpful_error():
    stub = StubConnector("bea", "Bureau of Economic Analysis connector is not yet implemented")
    with pytest.raises(ConnectorError, match="not yet implemented"):
        stub.fetch("T10101")
    assert stub.search("gdp") == []


def test_registry_builds_all_sources(tmp_path):
    engine = make_engine(f"sqlite:///{(tmp_path / 'reg.db').as_posix()}")
    init_db(engine)
    factory = make_session_factory(engine)
    connectors = build_connectors(factory)
    for name in ("fred", "worldbank", "imf", "bls", "ecb", "oecd", "bea", "census"):
        assert name in connectors


def test_datasources_endpoint(tmp_path):
    engine = make_engine(f"sqlite:///{(tmp_path / 'ds.db').as_posix()}")
    init_db(engine)
    client = TestClient(create_app(session_factory=make_session_factory(engine)))
    resp = client.get("/api/datasources")
    assert resp.status_code == 200
    names = {d["name"] for d in resp.json()}
    assert {"fred", "worldbank", "imf", "bls", "ecb", "oecd", "bea", "census"} <= names
    catalog = {d["name"]: d for d in resp.json()}
    assert catalog["bea"]["available"] is False
    assert catalog["worldbank"]["available"] is True
