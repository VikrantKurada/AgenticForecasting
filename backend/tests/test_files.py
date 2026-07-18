import json

import pytest
from fastapi.testclient import TestClient

from app import models
from app.db import init_db, make_engine, make_session_factory
from app.main import create_app


@pytest.fixture
def env(tmp_path):
    engine = make_engine(f"sqlite:///{(tmp_path / 'files.db').as_posix()}")
    init_db(engine)
    factory = make_session_factory(engine)
    client = TestClient(create_app(session_factory=factory))
    with factory() as s:
        project = models.Project(name="P")
        s.add(project)
        s.flush()
        chat = models.Chat(project_id=project.id, title="c")
        s.add(chat)
        s.flush()
        run = models.Run(chat_id=chat.id, project_id=project.id, question="q", status="completed")
        s.add(run)
        s.flush()
        report = models.Artifact(
            run_id=run.id, project_id=project.id, kind="report",
            title="GDP Nowcast Report", payload_json=json.dumps({"markdown": "# Report\nBody"}),
        )
        chart = models.Artifact(
            run_id=run.id, project_id=project.id, kind="chart",
            title="Fan chart", payload_json=json.dumps({"data": [], "layout": {}}),
        )
        table = models.Artifact(
            run_id=run.id, project_id=project.id, kind="table",
            title="Data", payload_json=json.dumps(
                {"columns": ["date", "value"], "rows": [["2024-01", 1.5], ["2024-02", 2.0]]}
            ),
        )
        s.add_all([report, chart, table])
        s.commit()
        ids = {"report": report.id, "chart": chart.id, "table": table.id}
    return client, ids


def test_default_dir_points_at_desktop_or_home(env):
    client, _ = env
    path = client.get("/api/fs/default-dir").json()["path"]
    assert path


def test_save_report_writes_markdown(env, tmp_path):
    client, ids = env
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    resp = client.post(f"/api/artifacts/{ids['report']}/save", json={"directory": str(out_dir)})
    assert resp.status_code == 200
    saved = resp.json()["path"]
    assert saved.endswith(".md")
    assert "# Report" in open(saved, encoding="utf-8").read()


def test_save_table_writes_csv(env, tmp_path):
    client, ids = env
    out_dir = tmp_path / "out2"
    out_dir.mkdir()
    saved = client.post(
        f"/api/artifacts/{ids['table']}/save", json={"directory": str(out_dir)}
    ).json()["path"]
    assert saved.endswith(".csv")
    content = open(saved, encoding="utf-8").read()
    assert "date,value" in content
    assert "2024-01" in content


def test_save_chart_writes_html(env, tmp_path):
    client, ids = env
    out_dir = tmp_path / "out3"
    out_dir.mkdir()
    saved = client.post(
        f"/api/artifacts/{ids['chart']}/save", json={"directory": str(out_dir)}
    ).json()["path"]
    assert saved.endswith(".html")
    assert "plotly" in open(saved, encoding="utf-8").read().lower()


def test_save_rejects_missing_directory(env, tmp_path):
    client, ids = env
    resp = client.post(
        f"/api/artifacts/{ids['report']}/save",
        json={"directory": str(tmp_path / "does-not-exist")},
    )
    assert resp.status_code == 400
