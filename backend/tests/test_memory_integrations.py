import httpx
import pytest
from fastapi.testclient import TestClient

from app.db import init_db, make_engine, make_session_factory
from app.main import create_app
from app.memory.integrations import INTEGRATION_CATALOG, build_memory_backend
from app.memory.mem0_backend import Mem0Backend
from app.memory.zep_backend import ZepBackend


def make_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_mem0_add_and_search_use_api(tmp_path):
    seen = []

    def handler(req):
        seen.append((req.method, req.url.path))
        if req.url.path.endswith("/memories/search/"):
            return httpx.Response(200, json=[{"id": "m1", "memory": "GDP fact", "metadata": {"mem_type": "semantic"}}])
        return httpx.Response(200, json=[{"id": "m1"}])

    backend = Mem0Backend(api_key="k", client=make_client(handler))
    backend.add("semantic", "GDP fact", project_id="p1")
    hits = backend.search("gdp", project_id="p1")
    assert hits and hits[0].content == "GDP fact"
    assert any("search" in path for _, path in seen)


def test_zep_add_and_search_use_graph_api():
    def handler(req):
        if "search" in req.url.path:
            return httpx.Response(200, json={"edges": [{"uuid": "e1", "fact": "HICP is euro inflation"}]})
        return httpx.Response(200, json={"uuid": "d1"})

    backend = ZepBackend(api_key="k", client=make_client(handler))
    backend.add("semantic", "HICP is euro inflation", project_id="p1")
    hits = backend.search("inflation", project_id="p1")
    assert hits and "HICP" in hits[0].content


def test_catalog_lists_all_requested_platforms():
    names = {i["name"] for i in INTEGRATION_CATALOG}
    expected = {
        "builtin", "mem0", "zep", "letta", "supermemory", "cognee",
        "hindsight", "retaindb", "everos", "maximem_synap", "supabase",
    }
    assert expected <= names


def test_build_memory_backend_falls_back_to_builtin_without_key(tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "mem0_api_key", "")
    engine = make_engine(f"sqlite:///{(tmp_path / 'mi.db').as_posix()}")
    init_db(engine)
    factory = make_session_factory(engine)
    backend = build_memory_backend(factory, active="mem0")
    assert backend.name == "builtin"


def test_integrations_api_get_and_activate(tmp_path):
    engine = make_engine(f"sqlite:///{(tmp_path / 'mi2.db').as_posix()}")
    init_db(engine)
    client = TestClient(create_app(session_factory=make_session_factory(engine)))

    data = client.get("/api/settings/integrations").json()
    assert data["active"] == "builtin"
    assert any(i["name"] == "mem0" for i in data["integrations"])

    resp = client.put("/api/settings/integrations", json={"active": "builtin"})
    assert resp.status_code == 200
    assert client.get("/api/settings/integrations").json()["active"] == "builtin"

    resp = client.put("/api/settings/integrations", json={"active": "not-a-backend"})
    assert resp.status_code == 400
