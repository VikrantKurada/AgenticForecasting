import pytest
from fastapi.testclient import TestClient

from app.db import init_db, make_engine, make_session_factory
from app.main import create_app


@pytest.fixture
def client(tmp_path):
    engine = make_engine(f"sqlite:///{(tmp_path / 'prov.db').as_posix()}")
    init_db(engine)
    return TestClient(create_app(session_factory=make_session_factory(engine)))


def test_get_providers_lists_all_five(client):
    data = client.get("/api/settings/providers").json()
    names = [p["name"] for p in data["providers"]]
    assert names == ["anthropic", "openai", "gemini", "nvidia", "ollama"]
    for p in data["providers"]:
        assert isinstance(p["configured"], bool)
        assert "api_key" not in p  # never leak secrets


def test_put_providers_persists_order_and_model(client):
    resp = client.put(
        "/api/settings/providers",
        json={"order": ["ollama", "anthropic"], "models": {"ollama": "qwen2.5"}},
    )
    assert resp.status_code == 200
    data = client.get("/api/settings/providers").json()
    assert data["order"] == ["ollama", "anthropic"]
    ollama = next(p for p in data["providers"] if p["name"] == "ollama")
    assert ollama["model"] == "qwen2.5"
