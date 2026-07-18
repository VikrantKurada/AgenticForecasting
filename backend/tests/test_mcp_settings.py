import pytest
from fastapi.testclient import TestClient

from app.db import init_db, make_engine, make_session_factory
from app.main import create_app


@pytest.fixture
def client(tmp_path):
    engine = make_engine(f"sqlite:///{(tmp_path / 'mcp.db').as_posix()}")
    init_db(engine)
    return TestClient(create_app(session_factory=make_session_factory(engine)))


def test_mcp_servers_roundtrip(client):
    assert client.get("/api/settings/mcp").json() == {"servers": {}}
    resp = client.put(
        "/api/settings/mcp",
        json={"servers": {"econ-tools": {"url": "https://mcp.example.com/mcp"}}},
    )
    assert resp.status_code == 200
    data = client.get("/api/settings/mcp").json()
    assert data["servers"]["econ-tools"]["url"] == "https://mcp.example.com/mcp"


def test_mcp_servers_rejects_non_dict(client):
    resp = client.put("/api/settings/mcp", json={"servers": {"bad": "not-an-object"}})
    assert resp.status_code == 422
