import pytest

from app.agents.tools import ToolContext, build_toolbelt, execute_tool
from app.connectors.base import SeriesData, SeriesMeta
from app.db import init_db, make_engine, make_session_factory
from app.memory.service import MemoryService
from app.memory.sqlite_backend import SQLiteMemoryBackend


class FakeConnector:
    source = "fake"

    def search(self, query, limit=10):
        return [SeriesMeta(source="fake", series_id="GDP1", title="Fake GDP", frequency="Monthly")]

    def fetch(self, series_id, **params):
        observations = [(f"20{10 + i // 12:02d}-{i % 12 + 1:02d}", 100.0 + i) for i in range(100)]
        return SeriesData(
            meta=SeriesMeta(source="fake", series_id=series_id, title="Fake GDP"),
            observations=observations,
        )


@pytest.fixture
def ctx(tmp_path):
    engine = make_engine(f"sqlite:///{(tmp_path / 'tools.db').as_posix()}")
    init_db(engine)
    factory = make_session_factory(engine)
    return ToolContext(
        session_factory=factory,
        connectors={"fake": FakeConnector()},
        memory=MemoryService(SQLiteMemoryBackend(factory), factory),
        project_id="p1",
    )


@pytest.fixture
def belt():
    return build_toolbelt()


def test_toolbelt_specs_are_complete(belt):
    expected = {
        "search_series", "fetch_series", "list_models", "run_model",
        "fit_yield_curve", "build_chart", "web_search", "http_get",
        "save_fact", "recall_memory", "mcp_list_tools", "mcp_call_tool",
    }
    assert expected <= set(belt)
    for spec in belt.values():
        assert spec.description
        assert spec.input_schema.get("type") == "object"


def test_search_series_queries_connectors(belt, ctx):
    result = execute_tool(belt, "search_series", {"query": "gdp"}, ctx)
    assert result["results"][0]["series_id"] == "GDP1"
    assert result["results"][0]["source"] == "fake"


def test_fetch_series_stores_full_data_and_returns_summary(belt, ctx):
    result = execute_tool(belt, "fetch_series", {"source": "fake", "series_id": "GDP1"}, ctx)
    assert result["series_key"] == "fake:GDP1"
    assert result["count"] == 100
    assert len(result["observations_tail"]) <= 40
    assert "fake:GDP1" in ctx.data_store


def test_run_model_uses_stored_series(belt, ctx):
    execute_tool(belt, "fetch_series", {"source": "fake", "series_id": "GDP1"}, ctx)
    result = execute_tool(
        belt, "run_model",
        {"model": "ets", "series_key": "fake:GDP1", "horizon": 3}, ctx,
    )
    assert len(result["point"]) == 3
    assert result["result_index"] == 0
    assert len(ctx.results) == 1


def test_build_fan_chart_appends_artifact(belt, ctx):
    execute_tool(belt, "fetch_series", {"source": "fake", "series_id": "GDP1"}, ctx)
    execute_tool(belt, "run_model", {"model": "ets", "series_key": "fake:GDP1", "horizon": 3}, ctx)
    result = execute_tool(
        belt, "build_chart",
        {"kind": "fan", "title": "GDP forecast", "series_key": "fake:GDP1", "result_index": 0},
        ctx,
    )
    assert result["status"] == "created"
    assert len(ctx.artifacts) == 1
    chart = ctx.artifacts[0]
    assert chart["kind"] == "chart"
    assert chart["payload"]["data"]
    assert chart["payload"]["layout"]["title"]["text"] == "GDP forecast"


def test_fit_yield_curve_tool(belt, ctx):
    curve = {"0.25": 5.2, "2": 4.6, "10": 4.4, "30": 4.5}
    result = execute_tool(belt, "fit_yield_curve", {"yields_by_maturity": curve}, ctx)
    assert set(result["params"]) == {"beta0", "beta1", "beta2", "tau"}


def test_web_search_delegates_to_ddgs(belt, ctx, monkeypatch):
    import app.agents.tools.web_search as ws

    monkeypatch.setattr(
        ws, "_ddgs_search",
        lambda query, max_results: [{"title": "T", "href": "https://x", "body": "snippet"}],
    )
    result = execute_tool(belt, "web_search", {"query": "fed rate decision"}, ctx)
    assert result["results"][0]["title"] == "T"


def test_http_get_rejects_non_https(belt, ctx):
    result = execute_tool(belt, "http_get", {"url": "http://insecure.example.com"}, ctx)
    assert "error" in result


def test_save_fact_and_recall_roundtrip(belt, ctx):
    execute_tool(belt, "save_fact", {"content": "GDPC1 is quarterly real US GDP from FRED"}, ctx)
    result = execute_tool(belt, "recall_memory", {"query": "real US GDP"}, ctx)
    assert result["facts"]
    assert "GDPC1" in result["facts"][0]["content"]


def test_mcp_tools_report_when_unconfigured(belt, ctx):
    result = execute_tool(belt, "mcp_list_tools", {"server": "nonexistent"}, ctx)
    assert "error" in result


def test_unknown_tool_returns_error(belt, ctx):
    result = execute_tool(belt, "does_not_exist", {}, ctx)
    assert "error" in result


def test_run_model_error_lists_available_series_keys(belt, ctx):
    execute_tool(belt, "fetch_series", {"source": "fake", "series_id": "GDP1"}, ctx)
    result = execute_tool(
        belt, "run_model", {"model": "arima", "series_key": "wrong-key", "horizon": 2}, ctx
    )
    assert "error" in result
    assert "fake:GDP1" in result["error"]


def test_worldbank_error_suggests_country_prefix():
    from app.connectors.base import ConnectorError
    from app.connectors.worldbank import WorldBankConnector

    with pytest.raises(ConnectorError, match="US:NY.GDP.MKTP.KD.ZG"):
        WorldBankConnector().fetch("NY.GDP.MKTP.KD.ZG")
