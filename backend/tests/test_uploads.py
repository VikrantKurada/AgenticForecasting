import io
import json

import pytest
from fastapi.testclient import TestClient

from app import models
from app.connectors.uploads import UploadsConnector
from app.db import init_db, make_engine, make_session_factory
from app.main import create_app

CSV_BODY = (
    "date,revenue,units\n"
    "2023-01-01,100.5,10\n"
    "2023-02-01,110.0,11\n"
    "2023-03-01,,12\n"
    "2023-04-01,125.25,13\n"
)


def make_xlsx() -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["year", "gdp"])
    for year, gdp in [(2020, 1.1), (2021, 2.2), (2022, 3.3)]:
        ws.append([year, gdp])
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


@pytest.fixture
def env(tmp_path, monkeypatch):
    import app.routers.uploads as uploads_router

    monkeypatch.setattr(uploads_router, "UPLOAD_DIR", tmp_path / "uploads")
    engine = make_engine(f"sqlite:///{(tmp_path / 'up.db').as_posix()}")
    init_db(engine)
    factory = make_session_factory(engine)
    client = TestClient(create_app(session_factory=factory))
    pid = client.post("/api/projects", json={"name": "P"}).json()["id"]
    cid = client.post(f"/api/projects/{pid}/chats", json={"title": "c"}).json()["id"]
    return client, factory, pid, cid


def upload_csv(client, cid, name="sales.csv", body=CSV_BODY):
    return client.post(
        f"/api/chats/{cid}/files",
        files={"file": (name, io.BytesIO(body.encode()), "text/csv")},
    )


def test_csv_upload_parses_columns(env):
    client, factory, pid, cid = env
    resp = upload_csv(client, cid)
    assert resp.status_code == 200
    meta = resp.json()
    assert meta["filename"] == "sales.csv"
    assert meta["n_rows"] == 4
    assert meta["columns"]["date_column"] == "date"
    assert set(meta["columns"]["numeric_columns"]) == {"revenue", "units"}
    assert meta["scope"] == "chat"


def test_chat_file_listing_and_delete(env):
    client, factory, pid, cid = env
    file_id = upload_csv(client, cid).json()["id"]
    listed = client.get(f"/api/chats/{cid}/files").json()
    assert [f["id"] for f in listed] == [file_id]
    assert client.delete(f"/api/files/{file_id}").status_code == 204
    assert client.get(f"/api/chats/{cid}/files").json() == []


def test_project_upload_visible_in_chat_listing(env):
    client, factory, pid, cid = env
    resp = client.post(
        f"/api/projects/{pid}/files",
        files={"file": ("macro.csv", io.BytesIO(CSV_BODY.encode()), "text/csv")},
    )
    assert resp.json()["scope"] == "project"
    listed = client.get(f"/api/chats/{cid}/files").json()
    assert any(f["filename"] == "macro.csv" and f["scope"] == "project" for f in listed)


def test_xlsx_upload_with_year_column(env):
    client, factory, pid, cid = env
    resp = client.post(
        f"/api/chats/{cid}/files",
        files={"file": ("gdp.xlsx", io.BytesIO(make_xlsx()),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code == 200
    meta = resp.json()
    assert meta["columns"]["date_column"] == "year"
    assert meta["columns"]["numeric_columns"] == ["gdp"]


def test_uploads_connector_search_and_fetch(env):
    client, factory, pid, cid = env
    file_id = upload_csv(client, cid).json()["id"]
    connector = UploadsConnector(factory)

    hits = connector.search("sales revenue")
    assert any(h.series_id == f"{file_id}:revenue" for h in hits)

    data = connector.fetch(f"{file_id}:revenue")
    assert data.meta.source == "uploads"
    assert data.observations[0] == ("2023-01-01", 100.5)
    assert data.observations[2][1] is None  # blank cell preserved as missing
    assert len(data.observations) == 4


def test_attached_files_appear_in_run_question(env, tmp_path, monkeypatch):
    import app.routers.uploads as uploads_router

    monkeypatch.setattr(uploads_router, "UPLOAD_DIR", tmp_path / "uploads2")
    from tests.test_chat_pipeline import RUN_SCRIPT
    from tests.test_tools import FakeConnector
    from app.llm.fake import FakeLLM
    from app.llm.registry import LLMRegistry

    engine = make_engine(f"sqlite:///{(tmp_path / 'up2.db').as_posix()}")
    init_db(engine)
    factory = make_session_factory(engine)
    llm = LLMRegistry(factory, adapters={"fake": FakeLLM(list(RUN_SCRIPT))}, chain=[("fake", "fake-1")])
    client = TestClient(create_app(
        session_factory=factory, llm_registry=llm,
        connectors={"fake": FakeConnector()}, run_inline=True,
    ))
    pid = client.post("/api/projects", json={"name": "P"}).json()["id"]
    cid = client.post(f"/api/projects/{pid}/chats", json={"title": "c"}).json()["id"]
    file_id = upload_csv(client, cid, name="indicators.csv").json()["id"]

    run_id = client.post(
        f"/api/chats/{cid}/messages", json={"content": "Nowcast US GDP growth"},
    ).json()["run_id"]
    question = client.get(f"/api/runs/{run_id}").json()["question"]
    assert "indicators.csv" in question
    assert f"{file_id}:revenue" in question
    assert "uploads" in question
