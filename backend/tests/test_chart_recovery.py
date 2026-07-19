"""Regression tests for the chart-building failures that left runs chart-less.

The chart builder is an LLM: it only recovers from a bad argument if the error
tells it what the valid arguments are. These tests pin that contract.
"""
import pytest

from app.agents.engine.executor import figure_index, figure_manifest, run_state_block
from app.agents.tools import ToolContext, build_toolbelt, execute_tool
from app.db import init_db, make_engine, make_session_factory
from app.memory.service import MemoryService
from app.memory.sqlite_backend import SQLiteMemoryBackend
from tests.test_tools import FakeConnector


@pytest.fixture
def ctx(tmp_path):
    engine = make_engine(f"sqlite:///{(tmp_path / 'recovery.db').as_posix()}")
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
    return belt, context


def test_unknown_series_key_error_names_the_available_keys(ctx):
    belt, context = ctx
    result = execute_tool(
        belt, "build_chart",
        {"kind": "fan", "title": "T", "series_key": "uk_unemployment_rate", "result_index": 0},
        context,
    )
    # The old behaviour was a bare "KeyError: 'uk_unemployment_rate'", which the
    # agent could only respond to by guessing another name.
    assert "error" in result
    assert "fake:GDP1" in result["error"]


def test_chart_kinds_needing_no_model_survive_a_missing_result(ctx):
    belt, context = ctx
    result = execute_tool(
        belt, "build_chart",
        {"kind": "fan", "title": "T", "series_key": "fake:GDP1", "result_index": 0},
        context,
    )
    assert "error" in result
    assert "run_model" in result["error"]
    # ...and the error points at charts that *can* be built without a model
    assert "decomposition" in result["error"]

    ok = execute_tool(
        belt, "build_chart",
        {"kind": "decomposition", "title": "T", "series_key": "fake:GDP1"}, context,
    )
    assert ok["status"] == "created"


def test_missing_series_key_argument_is_reported_with_available_keys(ctx):
    belt, context = ctx
    result = execute_tool(belt, "build_chart", {"kind": "table", "title": "T"}, context)
    assert "error" in result
    assert "fake:GDP1" in result["error"]


def test_bad_result_index_lists_the_models_that_ran(ctx):
    belt, context = ctx
    execute_tool(
        belt, "run_model", {"model": "ets", "series_key": "fake:GDP1", "horizon": 3}, context
    )
    result = execute_tool(
        belt, "build_chart",
        {"kind": "backtest", "title": "T", "result_index": 7}, context,
    )
    assert "error" in result
    assert "0=" in result["error"]  # names index 0 and its model


def test_heatmap_needs_two_series_and_says_so(ctx):
    belt, context = ctx
    result = execute_tool(
        belt, "build_chart",
        {"kind": "heatmap", "title": "T", "series_keys": ["fake:GDP1"]}, context,
    )
    assert "error" in result
    assert "at least 2" in result["error"]


def test_run_state_block_lists_keys_results_and_figures(ctx):
    belt, context = ctx
    execute_tool(
        belt, "run_model", {"model": "ets", "series_key": "fake:GDP1", "horizon": 3}, context
    )
    execute_tool(
        belt, "build_chart",
        {"kind": "fan", "title": "Forecast", "series_key": "fake:GDP1", "result_index": 0},
        context,
    )
    block = run_state_block(context)
    assert "'fake:GDP1'" in block          # the exact key to pass back
    assert "result_index 0" in block       # the exact index to pass back
    assert "Figure 1: [chart] Forecast" in block


def test_run_state_block_is_explicit_when_nothing_has_been_fetched(tmp_path):
    engine = make_engine(f"sqlite:///{(tmp_path / 'empty.db').as_posix()}")
    init_db(engine)
    factory = make_session_factory(engine)
    context = ToolContext(session_factory=factory, connectors={}, memory=None)
    block = run_state_block(context)
    assert "No series have been fetched yet." in block
    assert "No model results yet." in block


def test_figure_index_numbers_charts_and_tables_together():
    artifacts = [
        {"kind": "chart", "title": "Fan chart"},
        {"kind": "table", "title": "Underlying data"},
        {"kind": "chart", "title": "Backtest"},
        {"kind": "methodology", "title": "Method"},  # not a figure
    ]
    manifest = figure_manifest(artifacts)
    assert [f["number"] for f in manifest] == [1, 2, 3]

    index = figure_index(artifacts)
    assert "**Figure 2** — Underlying data (Data table)" in index
    assert "**Figure 3** — Backtest (Chart)" in index
    assert "Method" not in index


def test_figure_index_is_empty_when_no_figures_exist():
    assert figure_index([{"kind": "report", "title": "R"}]) == ""
