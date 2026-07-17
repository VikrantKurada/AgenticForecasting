import pytest
from fastapi.testclient import TestClient

from app import models
from app.db import init_db, make_engine, make_session_factory
from app.main import create_app


@pytest.fixture
def ctx(tmp_path):
    engine = make_engine(f"sqlite:///{(tmp_path / 'api.db').as_posix()}")
    init_db(engine)
    factory = make_session_factory(engine)
    client = TestClient(create_app(session_factory=factory))
    return client, factory


def test_create_and_get_project(ctx):
    client, _ = ctx
    resp = client.post("/api/projects", json={"name": "US Macro", "description": "GDP work"})
    assert resp.status_code == 201
    pid = resp.json()["id"]
    got = client.get(f"/api/projects/{pid}")
    assert got.status_code == 200
    assert got.json()["name"] == "US Macro"


def test_list_and_search_projects(ctx):
    client, _ = ctx
    client.post("/api/projects", json={"name": "US Macro"})
    client.post("/api/projects", json={"name": "EU Inflation", "description": "HICP nowcast"})
    all_projects = client.get("/api/projects").json()
    assert len(all_projects) == 2
    hits = client.get("/api/projects", params={"q": "hicp"}).json()
    assert [p["name"] for p in hits] == ["EU Inflation"]


def test_patch_project(ctx):
    client, _ = ctx
    pid = client.post("/api/projects", json={"name": "Old"}).json()["id"]
    resp = client.patch(f"/api/projects/{pid}", json={"name": "New name"})
    assert resp.status_code == 200
    assert client.get(f"/api/projects/{pid}").json()["name"] == "New name"


def test_delete_project_cascades(ctx):
    client, factory = ctx
    pid = client.post("/api/projects", json={"name": "Doomed"}).json()["id"]
    cid = client.post(f"/api/projects/{pid}/chats", json={"title": "chat"}).json()["id"]
    assert client.delete(f"/api/projects/{pid}").status_code == 204
    assert client.get(f"/api/projects/{pid}").status_code == 404
    assert client.get(f"/api/chats/{cid}").status_code == 404
    with factory() as s:
        assert s.query(models.Chat).count() == 0


def test_chat_crud_and_messages(ctx):
    client, _ = ctx
    pid = client.post("/api/projects", json={"name": "P"}).json()["id"]
    resp = client.post(f"/api/projects/{pid}/chats", json={"title": "Nowcast chat"})
    assert resp.status_code == 201
    cid = resp.json()["id"]
    chats = client.get(f"/api/projects/{pid}/chats").json()
    assert [c["title"] for c in chats] == ["Nowcast chat"]
    assert client.get(f"/api/chats/{cid}/messages").json() == []
    assert client.delete(f"/api/chats/{cid}").status_code == 204
    assert client.get(f"/api/chats/{cid}").status_code == 404


def test_mutations_write_user_events(ctx):
    client, factory = ctx
    pid = client.post("/api/projects", json={"name": "Audited"}).json()["id"]
    with factory() as s:
        events = s.query(models.Event).filter_by(actor="user").all()
        assert any(e.event_type == "project_created" and e.project_id == pid for e in events)
