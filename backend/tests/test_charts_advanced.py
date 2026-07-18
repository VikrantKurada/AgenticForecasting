import pytest

from app.agents.tools import ToolContext, build_toolbelt, execute_tool
from app.db import init_db, make_engine, make_session_factory
from app.memory.service import MemoryService
from app.memory.sqlite_backend import SQLiteMemoryBackend
from tests.test_tools import FakeConnector


@pytest.fixture
def ctx(tmp_path):
    engine = make_engine(f"sqlite:///{(tmp_path / 'charts.db').as_posix()}")
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
    execute_tool(belt, "fetch_series", {"source": "fake", "series_id": "CPI1"}, context)
    execute_tool(
        belt, "run_model", {"model": "ets", "series_key": "fake:GDP1", "horizon": 4}, context
    )
    execute_tool(
        belt, "run_model",
        {"model": "montecarlo", "series_key": "fake:GDP1", "horizon": 4}, context,
    )
    return belt, context


def last_chart(context):
    return context.artifacts[-1]["payload"]


def test_decomposition_chart_has_stacked_panels(ctx):
    belt, context = ctx
    result = execute_tool(
        belt, "build_chart",
        {"kind": "decomposition", "title": "GDP decomposition", "series_key": "fake:GDP1"},
        context,
    )
    assert result["status"] == "created"
    figure = last_chart(context)
    assert len(figure["data"]) >= 2
    assert "yaxis2" in figure["layout"]


def test_distribution_chart_is_histogram_with_stats(ctx):
    belt, context = ctx
    execute_tool(
        belt, "build_chart",
        {"kind": "distribution", "title": "GDP changes", "series_key": "fake:GDP1"},
        context,
    )
    figure = last_chart(context)
    assert figure["data"][0]["type"] == "histogram"
    assert "mean" in str(figure["layout"]).lower()


def test_correlation_heatmap_across_series(ctx):
    belt, context = ctx
    execute_tool(
        belt, "build_chart",
        {"kind": "heatmap", "title": "Correlations",
         "series_keys": ["fake:GDP1", "fake:CPI1"]},
        context,
    )
    figure = last_chart(context)
    assert figure["data"][0]["type"] == "heatmap"
    assert len(figure["data"][0]["z"]) == 2


def test_model_compare_overlays_forecasts(ctx):
    belt, context = ctx
    execute_tool(
        belt, "build_chart",
        {"kind": "model_compare", "title": "Model comparison",
         "series_key": "fake:GDP1", "result_indices": [0, 1]},
        context,
    )
    figure = last_chart(context)
    names = [t.get("name", "") for t in figure["data"]]
    assert len(figure["data"]) >= 3  # history + two model forecasts
    assert any("Monte Carlo" in n for n in names)
