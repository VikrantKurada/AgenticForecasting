import json

import pytest

from app import models
from app.agents.engine.events import RunEventBus
from app.agents.engine.executor import execute_run
from app.agents.engine.planner import classify_kind, make_plan, parse_action
from app.agents.engine.roles import ROLES
from app.db import init_db, make_engine, make_session_factory
from app.llm.fake import FakeLLM
from app.llm.registry import LLMRegistry
from app.memory.service import MemoryService
from app.memory.sqlite_backend import SQLiteMemoryBackend
from tests.test_tools import FakeConnector


@pytest.fixture
def env(tmp_path):
    engine = make_engine(f"sqlite:///{(tmp_path / 'engine.db').as_posix()}")
    init_db(engine)
    factory = make_session_factory(engine)
    with factory() as s:
        project = models.Project(name="P")
        s.add(project)
        s.flush()
        chat = models.Chat(project_id=project.id, title="c")
        s.add(chat)
        s.flush()
        run = models.Run(
            chat_id=chat.id, project_id=project.id,
            question="Nowcast US GDP growth", status="planning",
        )
        s.add(run)
        s.commit()
        ids = {"project": project.id, "chat": chat.id, "run": run.id}
    return factory, ids


def make_llm(factory, responses):
    return LLMRegistry(factory, adapters={"fake": FakeLLM(responses)}, chain=[("fake", "fake-1")])


def test_parse_action_handles_fences_and_prose():
    assert parse_action('{"action": "finish", "output": "done"}')["action"] == "finish"
    fenced = "Here you go:\n```json\n{\"action\": \"tool\", \"tool\": \"x\", \"args\": {}}\n```"
    assert parse_action(fenced)["tool"] == "x"
    assert parse_action("no json here") is None


def test_classify_kind_keywords():
    assert classify_kind("Nowcast US GDP for this quarter") == "nowcast"
    assert classify_kind("probability Argentina defaults on its debt") == "default_risk"
    assert classify_kind("where are 10y treasury yields heading") == "yield_curve"
    assert classify_kind("impact of red sea shipping disruption on trade") == "geopolitical"
    assert classify_kind("forecast german exports") == "generic"


def test_planner_accepts_valid_llm_plan(env):
    factory, ids = env
    plan_json = json.dumps({
        "kind": "nowcast",
        "nodes": [
            {"id": "a", "role": "data_scout", "instructions": "find gdp", "depends_on": []},
            {"id": "b", "role": "modeler", "instructions": "model it", "depends_on": ["a"]},
        ],
    })
    llm = make_llm(factory, [plan_json])
    memory = MemoryService(SQLiteMemoryBackend(factory), factory)
    plan = make_plan(llm, "Nowcast US GDP", memory, project_id=ids["project"])
    assert [n["id"] for n in plan["nodes"]] == ["a", "b"]


def test_planner_falls_back_to_template_on_garbage(env):
    factory, ids = env
    llm = make_llm(factory, ["not json at all", "still not json"])
    memory = MemoryService(SQLiteMemoryBackend(factory), factory)
    plan = make_plan(llm, "Nowcast euro area inflation", memory, project_id=ids["project"])
    assert plan["kind"] == "nowcast"
    assert plan["metadata"]["source"] == "template"
    roles_used = {n["role"] for n in plan["nodes"]}
    assert roles_used <= set(ROLES)


def test_planner_rejects_cyclic_plan_and_falls_back(env):
    factory, ids = env
    cyclic = json.dumps({
        "kind": "generic",
        "nodes": [
            {"id": "a", "role": "modeler", "instructions": "x", "depends_on": ["b"]},
            {"id": "b", "role": "modeler", "instructions": "y", "depends_on": ["a"]},
        ],
    })
    llm = make_llm(factory, [cyclic, cyclic])
    memory = MemoryService(SQLiteMemoryBackend(factory), factory)
    plan = make_plan(llm, "forecast something", memory, project_id=ids["project"])
    assert plan["metadata"]["source"] == "template"


def test_execute_run_end_to_end_with_fake_llm(env):
    factory, ids = env
    plan_json = json.dumps({
        "kind": "nowcast",
        "nodes": [
            {"id": "fetch", "role": "data_fetcher",
             "instructions": "Fetch series GDP1 from source fake", "depends_on": []},
            {"id": "model", "role": "modeler",
             "instructions": "Run ets horizon 3 on fake:GDP1", "depends_on": ["fetch"]},
            {"id": "chart", "role": "chart_builder",
             "instructions": "Fan chart of the forecast", "depends_on": ["model"]},
        ],
    })
    responses = [
        plan_json,
        json.dumps({"action": "tool", "tool": "fetch_series",
                    "args": {"source": "fake", "series_id": "GDP1"}}),
        json.dumps({"action": "finish", "output": "Fetched 100 observations of Fake GDP."}),
        json.dumps({"action": "tool", "tool": "run_model",
                    "args": {"model": "ets", "series_key": "fake:GDP1", "horizon": 3}}),
        json.dumps({"action": "finish", "output": "ETS forecast: growth continues."}),
        json.dumps({"action": "tool", "tool": "build_chart",
                    "args": {"kind": "fan", "title": "GDP nowcast",
                             "series_key": "fake:GDP1", "result_index": 0}}),
        json.dumps({"action": "finish", "output": "Fan chart created."}),
    ]
    llm = make_llm(factory, responses)
    memory = MemoryService(SQLiteMemoryBackend(factory), factory)
    bus = RunEventBus()

    outcome = execute_run(
        ids["run"], session_factory=factory, llm=llm,
        connectors={"fake": FakeConnector()}, memory=memory, bus=bus,
    )

    assert outcome["status"] == "completed"
    with factory() as s:
        run = s.get(models.Run, ids["run"])
        assert run.status == "completed"
        assert run.finished_at is not None
        assert json.loads(run.plan_json)["kind"] == "nowcast"

        artifacts = s.query(models.Artifact).filter_by(run_id=ids["run"]).all()
        assert any(a.kind == "chart" for a in artifacts)

        event_types = {e.event_type for e in s.query(models.Event).filter_by(run_id=ids["run"])}
        assert {"run_started", "plan_created", "node_started", "tool_call",
                "node_finished", "run_completed"} <= event_types

        episodes = s.query(models.MemoryItem).filter_by(mem_type="episodic").all()
        assert len(episodes) == 1
        procedures = s.query(models.MemoryItem).filter_by(mem_type="procedural").all()
        assert len(procedures) == 1

        methodology = next(a for a in artifacts if a.kind == "methodology")
        text = json.loads(methodology.payload_json)["markdown"]
        assert "## Data" in text
        assert "fake:GDP1" in text
        assert "ETS" in text
        assert "naive baseline" in text.lower()
        assert "## Workflow" in text


def test_execute_run_marks_failure_when_llm_unavailable(env):
    factory, ids = env

    class Boom:
        provider = "boom"

        def complete(self, *a, **k):
            raise RuntimeError("dead")

    llm = LLMRegistry(factory, adapters={"boom": Boom()}, chain=[("boom", "x")])
    memory = MemoryService(SQLiteMemoryBackend(factory), factory)
    outcome = execute_run(
        ids["run"], session_factory=factory, llm=llm,
        connectors={}, memory=memory, bus=RunEventBus(),
    )
    assert outcome["status"] == "failed"
    with factory() as s:
        run = s.get(models.Run, ids["run"])
        assert run.status == "failed"
        assert run.error
