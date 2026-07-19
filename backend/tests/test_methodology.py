"""The methodology artifact must describe the workflow in readable prose.

The workflow list used to render an entry node as "depends on: —", which reads
as missing data rather than "this step runs first".
"""
import pytest

from app.agents.engine.methodology import build_methodology
from app.agents.tools import ToolContext, build_toolbelt, execute_tool
from app.db import init_db, make_engine, make_session_factory
from app.memory.service import MemoryService
from app.memory.sqlite_backend import SQLiteMemoryBackend
from tests.test_tools import FakeConnector

PLAN = {
    "kind": "nowcast",
    "nodes": [
        {"id": "scout", "role": "data_scout", "depends_on": [],
         "instructions": "Identify the series that answer the question."},
        {"id": "fetch", "role": "data_fetcher", "depends_on": ["scout"],
         "instructions": "Fetch them."},
        {"id": "charts", "role": "chart_builder", "depends_on": ["fetch"],
         "instructions": "Build the chart set."},
    ],
    "metadata": {"source": "llm"},
}


@pytest.fixture
def ctx(tmp_path):
    engine = make_engine(f"sqlite:///{(tmp_path / 'method.db').as_posix()}")
    init_db(engine)
    factory = make_session_factory(engine)
    context = ToolContext(
        session_factory=factory,
        connectors={"fake": FakeConnector()},
        memory=MemoryService(SQLiteMemoryBackend(factory), factory),
        project_id="p1",
    )
    belt = build_toolbelt()
    execute_tool(belt, "fetch_series", {"source": "fake", "series_id": "GDP1"}, context)
    execute_tool(
        belt, "run_model", {"model": "ets", "series_key": "fake:GDP1", "horizon": 3}, context
    )
    execute_tool(
        belt, "build_chart",
        {"kind": "fan", "title": "Fan chart", "series_key": "fake:GDP1", "result_index": 0},
        context,
    )
    execute_tool(
        belt, "build_chart",
        {"kind": "table", "title": "Underlying data", "series_key": "fake:GDP1"}, context,
    )
    return context


def test_entry_node_is_described_not_left_blank(ctx):
    md = build_methodology("Nowcast GDP", PLAN, ctx, {})
    assert "**scout** — role `data_scout`, runs first (entry point, no dependencies)" in md
    # never the old empty rendering
    assert "depends on: —" not in md
    assert "depends on: \n" not in md


def test_dependent_nodes_state_both_directions(ctx):
    md = build_methodology("Nowcast GDP", PLAN, ctx, {})
    assert "**fetch** — role `data_fetcher`, depends on `scout`; feeds `charts`" in md
    assert "**charts** — role `chart_builder`, depends on `fetch`; final step" in md


def test_each_step_shows_its_assignment(ctx):
    md = build_methodology("Nowcast GDP", PLAN, ctx, {})
    assert "Assignment: Identify the series that answer the question." in md


def test_methodology_lists_figures_with_the_same_numbering_as_the_report(ctx):
    md = build_methodology("Nowcast GDP", PLAN, ctx, {})
    assert "**Figure 1** — Fan chart (chart)" in md
    assert "**Figure 2** — Underlying data (data table)" in md


def test_methodology_still_reports_data_and_models(ctx):
    md = build_methodology("Nowcast GDP", PLAN, ctx, {})
    assert "`fake:GDP1`" in md
    assert "ETS" in md
