"""Orchestrator access: inspecting a run's DAG and replaying it (edited or not)."""
import json

import pytest
from fastapi.testclient import TestClient

from app import models
from app.db import init_db, make_engine, make_session_factory
from app.llm.fake import FakeLLM
from app.llm.registry import LLMRegistry
from app.main import create_app
from tests.test_chat_pipeline import RUN_SCRIPT
from tests.test_tools import FakeConnector


@pytest.fixture
def client(tmp_path):
    engine = make_engine(f"sqlite:///{(tmp_path / 'orch.db').as_posix()}")
    init_db(engine)
    factory = make_session_factory(engine)
    # Two runs' worth of scripted turns: the original plus a replay. The replay
    # skips the planner, so its script starts after the plan response.
    script = list(RUN_SCRIPT) + list(RUN_SCRIPT[1:]) + list(RUN_SCRIPT[1:])
    llm = LLMRegistry(
        factory, adapters={"fake": FakeLLM(script)}, chain=[("fake", "fake-1")]
    )
    app = create_app(
        session_factory=factory, llm_registry=llm,
        connectors={"fake": FakeConnector()}, run_inline=True,
    )
    test_client = TestClient(app)
    pid = test_client.post("/api/projects", json={"name": "P"}).json()["id"]
    cid = test_client.post(f"/api/projects/{pid}/chats", json={"title": "c"}).json()["id"]
    return test_client, cid, factory


def start_run(test_client, cid) -> str:
    resp = test_client.post(
        f"/api/chats/{cid}/messages", json={"content": "Nowcast US GDP growth"}
    )
    return resp.json()["run_id"]


def test_chat_runs_endpoint_exposes_every_run_and_its_plan(client):
    test_client, cid, _factory = client
    run_id = start_run(test_client, cid)

    runs = test_client.get(f"/api/chats/{cid}/runs").json()
    assert [r["id"] for r in runs] == [run_id]
    assert runs[0]["plan"]["nodes"][0]["id"] == "fetch"
    assert runs[0]["status"] == "completed"


def test_rerun_replays_the_same_plan_without_replanning(client):
    test_client, cid, _factory = client
    run_id = start_run(test_client, cid)
    original = test_client.get(f"/api/runs/{run_id}").json()["plan"]

    resp = test_client.post(f"/api/runs/{run_id}/rerun", json={})
    assert resp.status_code == 200
    new_run_id = resp.json()["run_id"]
    assert new_run_id != run_id

    replay = test_client.get(f"/api/runs/{new_run_id}").json()
    assert replay["status"] == "completed"
    assert [n["id"] for n in replay["plan"]["nodes"]] == [n["id"] for n in original["nodes"]]
    assert replay["plan"]["metadata"]["source"] == "rerun"
    # the replay is a real run: it produced its own artifacts
    artifacts = test_client.get(f"/api/runs/{new_run_id}/artifacts").json()
    assert any(a["kind"] == "chart" for a in artifacts)


def test_rerun_accepts_user_edited_step_instructions(client):
    test_client, cid, _factory = client
    run_id = start_run(test_client, cid)
    plan = test_client.get(f"/api/runs/{run_id}").json()["plan"]
    plan["nodes"][0]["instructions"] = "Fetch GDP1 from fake, quarterly only"

    resp = test_client.post(f"/api/runs/{run_id}/rerun", json={"plan": plan})
    assert resp.status_code == 200
    new_plan = test_client.get(f"/api/runs/{resp.json()['run_id']}").json()["plan"]
    assert new_plan["nodes"][0]["instructions"] == "Fetch GDP1 from fake, quarterly only"


def test_rerun_rejects_an_invalid_edited_plan(client):
    test_client, cid, _factory = client
    run_id = start_run(test_client, cid)
    plan = test_client.get(f"/api/runs/{run_id}").json()["plan"]
    plan["nodes"][0]["role"] = "not_a_real_role"

    resp = test_client.post(f"/api/runs/{run_id}/rerun", json={"plan": plan})
    assert resp.status_code == 400
    assert "not_a_real_role" in resp.json()["detail"]
    # and no doomed run was created
    assert len(test_client.get(f"/api/chats/{cid}/runs").json()) == 1


def test_rerun_of_unknown_run_is_404(client):
    test_client, _cid, _factory = client
    assert test_client.post("/api/runs/nope/rerun", json={}).status_code == 404


def test_rerun_is_recorded_as_an_event(client):
    test_client, cid, factory = client
    run_id = start_run(test_client, cid)
    new_run_id = test_client.post(f"/api/runs/{run_id}/rerun", json={}).json()["run_id"]

    with factory() as s:
        event = (
            s.query(models.Event).filter_by(event_type="run_rerun").one()
        )
        payload = json.loads(event.payload_json)
    assert payload["source_run_id"] == run_id
    assert payload["run_id"] == new_run_id
    assert payload["edited"] is False
