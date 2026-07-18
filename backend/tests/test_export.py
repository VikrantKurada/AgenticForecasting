import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import models
from app.db import init_db, make_engine, make_session_factory
from app.main import create_app


@pytest.fixture
def env(tmp_path):
    engine = make_engine(f"sqlite:///{(tmp_path / 'exp.db').as_posix()}")
    init_db(engine)
    factory = make_session_factory(engine)
    client = TestClient(create_app(session_factory=factory))
    with factory() as s:
        project = models.Project(name="US Macro")
        s.add(project)
        s.flush()
        chat = models.Chat(project_id=project.id, title="GDP nowcast chat")
        s.add(chat)
        s.flush()
        s.add(models.Message(chat_id=chat.id, role="user", content="Nowcast US GDP"))
        s.add(models.Message(chat_id=chat.id, role="assistant", content="Growth continues."))
        run = models.Run(chat_id=chat.id, project_id=project.id,
                         question="Nowcast US GDP", status="completed")
        s.add(run)
        s.flush()
        s.add_all([
            models.Artifact(run_id=run.id, project_id=project.id, kind="report",
                            title="Report", payload_json=json.dumps({"markdown": "# R"})),
            models.Artifact(run_id=run.id, project_id=project.id, kind="methodology",
                            title="Prediction methodology",
                            payload_json=json.dumps({"markdown": "# M"})),
            models.Artifact(run_id=run.id, project_id=project.id, kind="chart",
                            title="Fan", payload_json=json.dumps({"data": [], "layout": {}})),
            models.Artifact(run_id=run.id, project_id=project.id, kind="table",
                            title="Data", payload_json=json.dumps(
                                {"columns": ["d", "v"], "rows": [["2024", 1.0]]})),
            models.Event(project_id=project.id, run_id=run.id, trace_id=run.id,
                         span_id="s1", actor="system", event_type="run_started",
                         payload_json="{}"),
        ])
        s.commit()
        ids = {"project": project.id, "chat": chat.id}
    return client, ids


def test_chat_export_writes_folder_tree(env, tmp_path):
    client, ids = env
    out = tmp_path / "desktop"
    out.mkdir()
    resp = client.post(f"/api/chats/{ids['chat']}/export", json={"directory": str(out)})
    assert resp.status_code == 200
    base = Path(resp.json()["path"])
    assert base.parent == out
    assert (base / "transcript.md").exists()
    transcript = (base / "transcript.md").read_text(encoding="utf-8")
    assert "Nowcast US GDP" in transcript
    run_dir = next(base.glob("run-1*"))
    files = {p.name for p in run_dir.iterdir()}
    assert any(f.endswith(".md") for f in files)
    assert any(f.endswith(".html") for f in files)
    assert any(f.endswith(".csv") for f in files)
    assert "trace.json" in files
    assert resp.json()["files"] >= 5


def test_project_export_contains_chat_folder(env, tmp_path):
    client, ids = env
    out = tmp_path / "desktop2"
    out.mkdir()
    resp = client.post(f"/api/projects/{ids['project']}/export", json={"directory": str(out)})
    assert resp.status_code == 200
    base = Path(resp.json()["path"])
    assert (base / "GDP_nowcast_chat" / "transcript.md").exists()


def test_export_rejects_missing_directory(env, tmp_path):
    client, ids = env
    resp = client.post(
        f"/api/chats/{ids['chat']}/export",
        json={"directory": str(tmp_path / "missing")},
    )
    assert resp.status_code == 400
