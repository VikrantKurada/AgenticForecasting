"""End-to-end wiring: what a full run hands its agents and what it produces.

Charts used to be missing because the chart-building node was never told which
series_key the fetcher stored, and the report never mentioned the charts.
"""
import json

import pytest

from app import models
from app.agents.engine.events import RunEventBus
from app.agents.engine.executor import execute_run
from app.db import init_db, make_engine, make_session_factory
from app.llm.fake import FakeLLM
from app.llm.registry import LLMRegistry
from app.memory.service import MemoryService
from app.memory.sqlite_backend import SQLiteMemoryBackend
from tests.test_tools import FakeConnector

PLAN = json.dumps({
    "kind": "nowcast",
    "nodes": [
        {"id": "fetch", "role": "data_fetcher",
         "instructions": "Fetch GDP1 from fake", "depends_on": []},
        {"id": "model", "role": "modeler",
         "instructions": "ets on the fetched series", "depends_on": ["fetch"]},
        {"id": "charts", "role": "chart_builder",
         "instructions": "Build the chart set", "depends_on": ["model"]},
        {"id": "explain", "role": "explainer",
         "instructions": "Write the report", "depends_on": ["charts"]},
    ],
})

SCRIPT = [
    PLAN,
    json.dumps({"action": "tool", "tool": "fetch_series",
                "args": {"source": "fake", "series_id": "GDP1"}}),
    json.dumps({"action": "finish", "output": "Fetched."}),
    json.dumps({"action": "tool", "tool": "run_model",
                "args": {"model": "ets", "series_key": "fake:GDP1", "horizon": 3}}),
    json.dumps({"action": "finish", "output": "Modeled."}),
    json.dumps({"action": "tool", "tool": "build_chart",
                "args": {"kind": "fan", "title": "GDP fan chart",
                         "series_key": "fake:GDP1", "result_index": 0}}),
    json.dumps({"action": "tool", "tool": "build_chart",
                "args": {"kind": "table", "title": "Underlying data",
                         "series_key": "fake:GDP1"}}),
    json.dumps({"action": "finish", "output": "Charted."}),
    json.dumps({"action": "finish", "output": "## Nowcast\nGrowth holds up."}),
]


@pytest.fixture
def run_env(tmp_path):
    engine = make_engine(f"sqlite:///{(tmp_path / 'wiring.db').as_posix()}")
    init_db(engine)
    factory = make_session_factory(engine)
    with factory() as s:
        project = models.Project(name="P")
        s.add(project)
        s.flush()
        chat = models.Chat(project_id=project.id, title="c")
        s.add(chat)
        s.flush()
        run = models.Run(chat_id=chat.id, project_id=project.id,
                         question="Nowcast GDP", status="planning")
        s.add(run)
        s.commit()
        run_id = run.id
    fake = FakeLLM(list(SCRIPT))
    llm = LLMRegistry(factory, adapters={"fake": fake}, chain=[("fake", "fake-1")])
    outcome = execute_run(
        run_id, session_factory=factory, llm=llm,
        connectors={"fake": FakeConnector()},
        memory=MemoryService(SQLiteMemoryBackend(factory), factory), bus=RunEventBus(),
    )
    return outcome, fake, factory, run_id


def prompt_for_role(fake: FakeLLM, role_marker: str) -> str:
    """The user-turn prompt of the first call made by a given agent role."""
    call = next(c for c in fake.calls if role_marker in c["system"])
    return call["messages"][0]["content"]


def test_chart_node_is_told_the_exact_series_key_and_result_index(run_env):
    _outcome, fake, _factory, _run_id = run_env
    prompt = prompt_for_role(fake, "chart builder")
    assert "'fake:GDP1'" in prompt
    assert "result_index 0" in prompt


def test_modeler_is_told_the_series_key_the_fetcher_stored(run_env):
    _outcome, fake, _factory, _run_id = run_env
    prompt = prompt_for_role(fake, "econometrician")
    assert "'fake:GDP1'" in prompt


def test_explainer_is_told_which_figures_exist(run_env):
    _outcome, fake, _factory, _run_id = run_env
    prompt = prompt_for_role(fake, "You are the explainer")
    assert "Figure 1: [chart] GDP fan chart" in prompt
    assert "Figure 2: [table] Underlying data" in prompt


def test_report_ends_with_a_figure_index_referencing_every_chart(run_env):
    _outcome, _fake, factory, run_id = run_env
    with factory() as s:
        report = (
            s.query(models.Artifact).filter_by(run_id=run_id, kind="report").one()
        )
        payload = json.loads(report.payload_json)
    markdown = payload["markdown"]
    assert "## Figures" in markdown
    assert "**Figure 1** — GDP fan chart (Chart)" in markdown
    assert "**Figure 2** — Underlying data (Data table)" in markdown
    # the machine-readable manifest travels with the report too
    assert [f["number"] for f in payload["figures"]] == [1, 2]


def test_run_still_produces_the_chart_artifacts(run_env):
    outcome, _fake, factory, run_id = run_env
    assert outcome["status"] == "completed"
    with factory() as s:
        kinds = [
            a.kind for a in s.query(models.Artifact).filter_by(run_id=run_id).all()
        ]
    assert "chart" in kinds
    assert "table" in kinds
    assert "report" in kinds
    assert "methodology" in kinds
