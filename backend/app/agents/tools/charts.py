"""Plotly figure-spec builders. Colors follow the validated dataviz reference palette:
categorical slots in fixed order, sequential = one blue ramp, thin marks, one axis.
"""
from app.agents.tools import ToolSpec
from app.forecasting.series import to_series

SERIES_COLORS = [  # fixed categorical order — never cycled or re-ranked
    "#2a78d6", "#1baf7a", "#eda100", "#008300",
    "#4a3aa7", "#e34948", "#e87ba4", "#eb6834",
]
BLUE = SERIES_COLORS[0]
BAND_80 = "rgba(42,120,214,0.22)"
BAND_95 = "rgba(42,120,214,0.10)"
MUTED = "#898781"
GRID = "#e1e0d9"


def _layout(title: str, x_title: str = "", y_title: str = "") -> dict:
    return {
        "title": {"text": title, "font": {"size": 15}},
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"family": "system-ui, 'Segoe UI', sans-serif", "size": 12, "color": MUTED},
        "xaxis": {"title": x_title, "gridcolor": GRID, "zeroline": False},
        "yaxis": {"title": y_title, "gridcolor": GRID, "zeroline": False},
        "legend": {"orientation": "h", "y": -0.2},
        "margin": {"l": 50, "r": 20, "t": 48, "b": 40},
        "hovermode": "x unified",
    }


def _add_artifact(ctx, title: str, figure: dict, kind: str = "chart") -> dict:
    ctx.artifacts.append({"kind": kind, "title": title, "payload": figure})
    return {"status": "created", "artifact_index": len(ctx.artifacts) - 1, "title": title}


def _fan_chart(args, ctx) -> dict:
    data = ctx.data_store[args["series_key"]]
    result = ctx.results[int(args.get("result_index", len(ctx.results) - 1))]
    series = to_series(data.observations)
    hist_x = [d.strftime("%Y-%m-%d") for d in series.index]
    hist_y = [float(v) for v in series.values]
    fx = result.forecast_dates
    traces = [
        {"type": "scatter", "name": "History", "x": hist_x, "y": hist_y,
         "mode": "lines", "line": {"color": BLUE, "width": 2}},
        {"type": "scatter", "name": "95% band", "x": fx + fx[::-1],
         "y": result.upper_95 + result.lower_95[::-1], "fill": "toself",
         "fillcolor": BAND_95, "line": {"width": 0}, "hoverinfo": "skip", "showlegend": True},
        {"type": "scatter", "name": "80% band", "x": fx + fx[::-1],
         "y": result.upper_80 + result.lower_80[::-1], "fill": "toself",
         "fillcolor": BAND_80, "line": {"width": 0}, "hoverinfo": "skip", "showlegend": True},
        {"type": "scatter", "name": f"Forecast ({result.model_name})", "x": fx,
         "y": result.point, "mode": "lines+markers",
         "line": {"color": BLUE, "width": 2, "dash": "dash"}, "marker": {"size": 8}},
    ]
    return {"data": traces, "layout": _layout(args.get("title", "Forecast"))}


def _indicator_panel(args, ctx) -> dict:
    traces = []
    for i, key in enumerate(args["series_keys"]):
        series = to_series(ctx.data_store[key].observations)
        if args.get("indexed", True) and float(series.iloc[0]) != 0:
            series = series / float(series.iloc[0]) * 100
        traces.append(
            {"type": "scatter", "name": ctx.data_store[key].meta.title or key,
             "x": [d.strftime("%Y-%m-%d") for d in series.index],
             "y": [float(v) for v in series.values], "mode": "lines",
             "line": {"color": SERIES_COLORS[i % len(SERIES_COLORS)], "width": 2}}
        )
    y_title = "Index (first obs = 100)" if args.get("indexed", True) else ""
    return {"data": traces, "layout": _layout(args.get("title", "Indicators"), y_title=y_title)}


def _backtest_chart(args, ctx) -> dict:
    result = ctx.results[int(args.get("result_index", len(ctx.results) - 1))]
    bt = result.backtest
    if "model_rmse" not in bt:
        raise ValueError(f"Result has no backtest metrics: {bt.get('note', 'missing')}")
    traces = [
        {"type": "bar", "name": result.model_name, "x": ["RMSE", "MAPE %"],
         "y": [bt["model_rmse"], bt["model_mape"]],
         "marker": {"color": BLUE, "cornerradius": 4}},
        {"type": "bar", "name": "Naive baseline", "x": ["RMSE", "MAPE %"],
         "y": [bt["baseline_rmse"], bt["baseline_mape"]],
         "marker": {"color": MUTED, "cornerradius": 4}},
    ]
    layout = _layout(args.get("title", "Backtest vs naive baseline"))
    layout["bargap"] = 0.3
    return {"data": traces, "layout": layout}


def _yield_curve_chart(args, ctx) -> dict:
    result = ctx.results[int(args.get("result_index", len(ctx.results) - 1))]
    observed = result["observed"]
    fitted = result["fitted_curve"]
    traces = [
        {"type": "scatter", "name": "Observed", "mode": "markers",
         "x": [float(m) for m in observed], "y": list(observed.values()),
         "marker": {"color": BLUE, "size": 9}},
        {"type": "scatter", "name": "Nelson-Siegel fit", "mode": "lines",
         "x": [float(m) for m in fitted], "y": list(fitted.values()),
         "line": {"color": SERIES_COLORS[5], "width": 2}},
    ]
    return {
        "data": traces,
        "layout": _layout(args.get("title", "Yield curve"), "Maturity (years)", "Yield (%)"),
    }


def build_chart(args, ctx):
    kind = args["kind"]
    builders = {
        "fan": _fan_chart,
        "panel": _indicator_panel,
        "backtest": _backtest_chart,
        "yield_curve": _yield_curve_chart,
    }
    if kind == "table":
        data = ctx.data_store[args["series_key"]]
        payload = {
            "columns": ["date", "value"],
            "rows": [[d, v] for d, v in data.observations],
            "series": data.meta.title,
        }
        return _add_artifact(ctx, args.get("title", data.meta.title), payload, kind="table")
    if kind not in builders:
        return {"error": f"Unknown chart kind '{kind}'. Available: {sorted(builders) + ['table']}"}
    figure = builders[kind](args, ctx)
    return _add_artifact(ctx, args.get("title", kind), figure)


SPECS = [
    ToolSpec(
        name="build_chart",
        description=(
            "Create a chart artifact for the user. Kinds: 'fan' (history + forecast with "
            "confidence bands; needs series_key + result_index), 'panel' (multi-series "
            "comparison; needs series_keys), 'backtest' (model vs baseline; needs "
            "result_index), 'yield_curve' (needs result_index from fit_yield_curve), "
            "'table' (raw observations; needs series_key). Build the widest appropriate "
            "set of charts for every forecast."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["fan", "panel", "backtest", "yield_curve", "table"]},
                "title": {"type": "string"},
                "series_key": {"type": "string"},
                "series_keys": {"type": "array", "items": {"type": "string"}},
                "result_index": {"type": "integer"},
                "indexed": {"type": "boolean", "description": "panel: rebase each series to 100"},
            },
            "required": ["kind", "title"],
        },
        fn=build_chart,
    ),
]
