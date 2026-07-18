import json

import pytest
from fastapi.testclient import TestClient

from app import models
from app.db import init_db, make_engine, make_session_factory
from app.llm.fake import FakeLLM
from app.llm.registry import LLMRegistry
from app.main import create_app
from tests.test_tools import FakeConnector

PLAN = json.dumps({
    "kind": "nowcast",
    "nodes": [
        {"id": "fetch", "role": "data_fetcher",
         "instructions": "Fetch GDP1 from fake", "depends_on": []},
        {"id": "model", "role": "modeler",
         "instructions": "ets horizon 3 on fake:GDP1", "depends_on": ["fetch"]},
        {"id": "chart", "role": "chart_builder",
         "instructions": "fan chart", "depends_on": ["model"]},
        {"id": "explain", "role": "explainer",
         "instructions": "final report", "depends_on": ["chart"]},
    ],
})
RUN_SCRIPT = [
    PLAN,
    json.dumps({"action": "tool", "tool": "fetch_series",
                "args": {"source": "fake", "series_id": "GDP1"}}),
    json.dumps({"action": "finish", "output": "Fetched."}),
    json.dumps({"action": "tool", "tool": "run_model",
                "args": {"model": "ets", "series_key": "fake:GDP1", "horizon": 3}}),
    json.dumps({"action": "finish", "output": "Modeled."}),
    json.dumps({"action": "tool", "tool": "build_chart",
                "args": {"kind": "fan", "title": "GDP nowcast",
                         "series_key": "fake:GDP1", "result_index": 0}}),
    json.dumps({"action": "finish", "output": "Charted."}),
    json.dumps({"action": "finish",
                "output": "## GDP Nowcast\nGrowth continues.\n\n### Methodology\nETS on Fake GDP."}),
]


@pytest.fixture
def client(tmp_path):
    engine = make_engine(f"sqlite:///{(tmp_path / 'chat.db').as_posix()}")
    init_db(engine)
    factory = make_session_factory(engine)
    llm = LLMRegistry(
        factory, adapters={"fake": FakeLLM(list(RUN_SCRIPT))}, chain=[("fake", "fake-1")]
    )
    app = create_app(
        session_factory=factory, llm_registry=llm,
        connectors={"fake": FakeConnector()}, run_inline=True,
    )
    test_client = TestClient(app)
    pid = test_client.post("/api/projects", json={"name": "P"}).json()["id"]
    cid = test_client.post(f"/api/projects/{pid}/chats", json={"title": "c"}).json()["id"]
    return test_client, factory, cid


def test_forecast_message_runs_workflow_and_persists_answer(client):
    test_client, factory, cid = client
    resp = test_client.post(
        f"/api/chats/{cid}/messages",
        json={"content": "Nowcast US GDP growth for this quarter"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "forecast_request"
    run_id = body["run_id"]
    assert run_id

    run = test_client.get(f"/api/runs/{run_id}").json()
    assert run["status"] == "completed"
    assert run["plan"]["kind"] == "nowcast"

    artifacts = test_client.get(f"/api/runs/{run_id}/artifacts").json()
    assert any(a["kind"] == "chart" for a in artifacts)
    report = next(a for a in artifacts if a["kind"] == "report")
    assert "Methodology" in report["payload"]["markdown"]

    messages = test_client.get(f"/api/chats/{cid}/messages").json()
    assert messages[-1]["role"] == "assistant"
    assert "Methodology" in messages[-1]["content"]
    assert messages[-1]["run_id"] == run_id


def test_first_message_auto_names_chat(client):
    test_client, factory, cid = client
    assert test_client.get(f"/api/chats/{cid}").json()["title"] == "c"
    # rename to the default so auto-naming applies
    test_client.patch(f"/api/chats/{cid}", json={"title": "New chat"})
    test_client.post(
        f"/api/chats/{cid}/messages",
        json={"content": "Nowcast US GDP growth for the current quarter please"},
    )
    title = test_client.get(f"/api/chats/{cid}").json()["title"]
    assert title.startswith("Nowcast US GDP growth")
    assert title != "New chat"


def test_chat_rename_endpoint(client):
    test_client, factory, cid = client
    resp = test_client.patch(f"/api/chats/{cid}", json={"title": "Q3 GDP work"})
    assert resp.status_code == 200
    assert test_client.get(f"/api/chats/{cid}").json()["title"] == "Q3 GDP work"
    assert test_client.patch("/api/chats/nope", json={"title": "x"}).status_code == 404


def test_preferences_flow_into_run_question(client):
    test_client, factory, cid = client
    resp = test_client.post(
        f"/api/chats/{cid}/messages",
        json={
            "content": "Nowcast US GDP growth",
            "preferences": {"source": "worldbank", "horizon": 8},
        },
    )
    run_id = resp.json()["run_id"]
    question = test_client.get(f"/api/runs/{run_id}").json()["question"]
    assert "worldbank" in question
    assert "8" in question
    # the chat message itself stays clean
    messages = test_client.get(f"/api/chats/{cid}/messages").json()
    assert messages[0]["content"] == "Nowcast US GDP growth"


def test_followup_answers_from_run_context(client):
    test_client, factory, cid = client
    test_client.post(
        f"/api/chats/{cid}/messages",
        json={"content": "Nowcast US GDP growth for this quarter"},
    )
    resp = test_client.post(
        f"/api/chats/{cid}/messages",
        json={"content": "Why did you choose that model?"},
    )
    body = resp.json()
    assert body["intent"] == "followup"
    assert body["assistant_message"]["content"]


def test_run_stream_replays_events_to_completion(client):
    test_client, factory, cid = client
    run_id = test_client.post(
        f"/api/chats/{cid}/messages",
        json={"content": "Nowcast US GDP growth"},
    ).json()["run_id"]

    with test_client.stream("GET", f"/api/runs/{run_id}/stream") as stream:
        text = "".join(stream.iter_text())
    assert "run_started" in text
    assert "run_completed" in text
    assert "end" in text
