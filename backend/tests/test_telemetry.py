import pytest
from fastapi.testclient import TestClient

from app import models
from app.db import init_db, make_engine, make_session_factory
from app.main import create_app


@pytest.fixture
def env(tmp_path):
    engine = make_engine(f"sqlite:///{(tmp_path / 'tel.db').as_posix()}")
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
        s.add_all([
            models.Event(project_id=project.id, run_id=run.id, trace_id=run.id,
                         span_id="s1", parent_span_id=None, actor="system",
                         event_type="run_started", payload_json="{}"),
            models.Event(project_id=project.id, run_id=run.id, trace_id=run.id,
                         span_id="s2", parent_span_id=None, actor="agent:modeler",
                         event_type="node_started", payload_json="{}"),
            models.Event(project_id=project.id, run_id=run.id, trace_id=run.id,
                         span_id="s3", parent_span_id="s2", actor="agent:modeler",
                         event_type="tool_call", payload_json='{"tool": "run_model"}'),
            models.TokenUsage(project_id=project.id, run_id=run.id, provider="anthropic",
                              model="claude-opus-4-8", agent_role="modeler",
                              input_tokens=1000, output_tokens=500, est_cost_usd=0.0175),
            models.TokenUsage(project_id=project.id, run_id=run.id, provider="ollama",
                              model="llama3.2", agent_role="planner",
                              input_tokens=800, output_tokens=300, est_cost_usd=0.0),
            models.ResourceSample(project_id=project.id, run_id=run.id,
                                  cpu_percent=25.0, mem_percent=60.0),
            models.ResourceSample(project_id=project.id, run_id=run.id,
                                  cpu_percent=75.0, mem_percent=70.0),
        ])
        s.commit()
        ids = {"project": project.id, "run": run.id}
    return client, ids


def test_trace_endpoint_builds_span_tree(env):
    client, ids = env
    trace = client.get(f"/api/runs/{ids['run']}/trace").json()
    assert len(trace["spans"]) == 2  # two roots
    node = next(s for s in trace["spans"] if s["event_type"] == "node_started")
    assert len(node["children"]) == 1
    assert node["children"][0]["payload"]["tool"] == "run_model"


def test_project_usage_aggregates_tokens_and_resources(env):
    client, ids = env
    usage = client.get(f"/api/projects/{ids['project']}/usage").json()
    assert usage["tokens"]["total_input"] == 1800
    assert usage["tokens"]["total_output"] == 800
    assert usage["tokens"]["est_cost_usd"] == pytest.approx(0.0175)
    providers = {p["provider"]: p for p in usage["tokens"]["by_provider"]}
    assert providers["anthropic"]["input_tokens"] == 1000
    roles = {r["agent_role"]: r for r in usage["tokens"]["by_role"]}
    assert roles["planner"]["output_tokens"] == 300
    assert usage["resources"]["avg_cpu"] == pytest.approx(50.0)
    assert usage["runs"]["total"] == 1
    assert usage["runs"]["completed"] == 1


def test_project_events_audit_list(env):
    client, ids = env
    events = client.get(f"/api/projects/{ids['project']}/events", params={"limit": 2}).json()
    assert len(events["events"]) == 2
    assert events["total"] >= 3
    filtered = client.get(
        f"/api/projects/{ids['project']}/events", params={"actor": "agent:modeler"}
    ).json()
    assert all(e["actor"] == "agent:modeler" for e in filtered["events"])
