"""Agent toolbelt: every tool an agent node may call during a run."""
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict
    fn: Callable


@dataclass
class ToolContext:
    session_factory: object
    connectors: dict
    memory: object
    project_id: str | None = None
    run_id: str | None = None
    chat_id: str | None = None
    data_store: dict = field(default_factory=dict)   # series_key -> SeriesData
    results: list = field(default_factory=list)      # ForecastResult objects
    artifacts: list = field(default_factory=list)    # chart/table/report dicts


def build_toolbelt() -> dict[str, ToolSpec]:
    from app.agents.tools import (
        charts,
        data_tool,
        forecast_tool,
        http_tool,
        mcp_tool,
        memory_tool,
        web_search,
    )

    specs = [
        *data_tool.SPECS,
        *forecast_tool.SPECS,
        *charts.SPECS,
        *web_search.SPECS,
        *http_tool.SPECS,
        *memory_tool.SPECS,
        *mcp_tool.SPECS,
    ]
    return {spec.name: spec for spec in specs}


def execute_tool(belt: dict[str, ToolSpec], name: str, args: dict, ctx: ToolContext) -> dict:
    spec = belt.get(name)
    if spec is None:
        return {"error": f"Unknown tool '{name}'. Available: {sorted(belt)}"}
    try:
        result = spec.fn(args or {}, ctx)
        return result if isinstance(result, dict) else {"result": result}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
