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


def _data_for(ctx, key):
    """Fetch a stored series, failing with the list of keys that *do* exist.

    A bare KeyError leaves the chart builder guessing names it can never hit;
    naming the available keys lets it self-correct on the next call.
    """
    if not isinstance(key, str) or not key:
        raise KeyError(
            f"'series_key' is required and must be a string. "
            f"Available series_keys: {sorted(ctx.data_store) or '<none fetched yet>'}."
        )
    data = ctx.data_store.get(key)
    if data is None:
        available = sorted(ctx.data_store) or ["<none fetched yet>"]
        raise KeyError(
            f"No fetched series under key '{key}'. Available series_keys: {available}. "
            "Use one of these exact keys — they are 'source:series_id' as returned by fetch_series."
        )
    return data


def _result_for(ctx, index, *, need_forecast: bool = True):
    """Fetch a model result by index, naming what is actually available."""
    if not ctx.results:
        raise IndexError(
            "No model results exist yet — run_model must succeed before this chart "
            "can be built. Build a chart that needs only a series_key instead "
            "(decomposition, distribution, panel, heatmap, table)."
        )
    catalog = [
        f"{i}={getattr(r, 'model_name', 'yield_curve_fit')}" for i, r in enumerate(ctx.results)
    ]
    try:
        idx = int(index)
    except (TypeError, ValueError):
        raise IndexError(f"'result_index' must be an integer. Available results: {catalog}.")
    if not -len(ctx.results) <= idx < len(ctx.results):
        raise IndexError(f"No result at index {idx}. Available results: {catalog}.")
    result = ctx.results[idx]
    if need_forecast and not hasattr(result, "point"):
        raise IndexError(
            f"Result {idx} is a yield-curve fit, not a forecast. Available results: {catalog}."
        )
    return result


def _series_keys_arg(args, ctx) -> list[str]:
    """Normalize the multi-series argument, tolerating a single series_key."""
    keys = args.get("series_keys") or ([args["series_key"]] if args.get("series_key") else [])
    if not keys:
        raise KeyError(
            "'series_keys' is required (a list). Available series_keys: "
            f"{sorted(ctx.data_store) or '<none fetched yet>'}."
        )
    return list(keys)


def _fan_chart(args, ctx) -> dict:
    data = _data_for(ctx, args.get("series_key"))
    result = _result_for(ctx, args.get("result_index", len(ctx.results) - 1))
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
    for i, key in enumerate(_series_keys_arg(args, ctx)):
        series = to_series(_data_for(ctx, key).observations)
        if args.get("indexed", True) and float(series.iloc[0]) != 0:
            series = series / float(series.iloc[0]) * 100
        traces.append(
            {"type": "scatter", "name": _data_for(ctx, key).meta.title or key,
             "x": [d.strftime("%Y-%m-%d") for d in series.index],
             "y": [float(v) for v in series.values], "mode": "lines",
             "line": {"color": SERIES_COLORS[i % len(SERIES_COLORS)], "width": 2}}
        )
    y_title = "Index (first obs = 100)" if args.get("indexed", True) else ""
    return {"data": traces, "layout": _layout(args.get("title", "Indicators"), y_title=y_title)}


def _backtest_chart(args, ctx) -> dict:
    result = _result_for(ctx, args.get("result_index", len(ctx.results) - 1))
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
    result = _result_for(ctx, args.get("result_index", len(ctx.results) - 1), need_forecast=False)
    if not isinstance(result, dict) or "fitted_curve" not in result:
        raise IndexError(
            f"Result {args.get('result_index')} is not a yield-curve fit — "
            "call fit_yield_curve first and use the result_index it returns."
        )
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


def _decomposition_chart(args, ctx) -> dict:
    from app.forecasting.series import infer_periods_per_year, to_series

    series = to_series(_data_for(ctx, args.get("series_key")).observations)
    x = [d.strftime("%Y-%m-%d") for d in series.index]
    period = infer_periods_per_year(series)
    seasonal = None
    if period >= 4 and len(series) >= 2 * period + 1:
        from statsmodels.tsa.seasonal import STL

        stl = STL(series, period=period).fit()
        trend, seasonal, resid = stl.trend, stl.seasonal, stl.resid
        method = f"STL (period={period})"
    else:
        window = max(3, len(series) // 8)
        trend = series.rolling(window, center=True, min_periods=1).mean()
        resid = series - trend
        method = f"rolling-mean trend (window={window})"

    traces = [
        {"type": "scatter", "name": "Observed", "x": x, "y": [float(v) for v in series],
         "mode": "lines", "line": {"color": MUTED, "width": 1.5}, "yaxis": "y"},
        {"type": "scatter", "name": "Trend", "x": x, "y": [float(v) for v in trend],
         "mode": "lines", "line": {"color": BLUE, "width": 2}, "yaxis": "y"},
    ]
    if seasonal is not None:
        traces.append(
            {"type": "scatter", "name": "Seasonal", "x": x,
             "y": [float(v) for v in seasonal], "mode": "lines",
             "line": {"color": SERIES_COLORS[1], "width": 2}, "yaxis": "y2"}
        )
    traces.append(
        {"type": "bar", "name": "Residual", "x": x, "y": [float(v) for v in resid],
         "marker": {"color": SERIES_COLORS[4]}, "yaxis": "y3" if seasonal is not None else "y2"}
    )
    layout = _layout(args.get("title", "Decomposition"))
    if seasonal is not None:
        layout["yaxis"] = {"domain": [0.72, 1.0], "gridcolor": GRID, "title": "Level"}
        layout["yaxis2"] = {"domain": [0.38, 0.66], "gridcolor": GRID, "anchor": "x", "title": "Seasonal"}
        layout["yaxis3"] = {"domain": [0.0, 0.32], "gridcolor": GRID, "anchor": "x", "title": "Residual"}
    else:
        layout["yaxis"] = {"domain": [0.55, 1.0], "gridcolor": GRID, "title": "Level"}
        layout["yaxis2"] = {"domain": [0.0, 0.45], "gridcolor": GRID, "anchor": "x", "title": "Residual"}
    layout["annotations"] = [{
        "text": f"Method: {method}", "showarrow": False, "xref": "paper", "yref": "paper",
        "x": 0, "y": 1.08, "font": {"size": 10, "color": MUTED},
    }]
    return {"data": traces, "layout": layout}


def _distribution_chart(args, ctx) -> dict:
    import numpy as np

    from app.forecasting.series import to_series

    series = to_series(_data_for(ctx, args.get("series_key")).observations)
    # Percent changes only make sense for strictly positive level series;
    # rates that cross zero get absolute changes instead.
    use_pct = bool(args.get("pct", True)) and (series > 0).all()
    changes = (series.pct_change() * 100 if use_pct else series.diff()).dropna()
    values = [float(v) for v in changes]
    mean, sigma = float(np.mean(values)), float(np.std(values))
    unit = "% change" if use_pct else "change"
    layout = _layout(args.get("title", "Distribution of changes"), x_title=unit, y_title="Count")
    layout["annotations"] = [{
        "text": f"mean {mean:.2f} · σ {sigma:.2f} · n {len(values)}",
        "showarrow": False, "xref": "paper", "yref": "paper",
        "x": 1, "y": 1.08, "font": {"size": 10, "color": MUTED},
    }]
    layout["shapes"] = [
        {"type": "line", "x0": mean, "x1": mean, "y0": 0, "y1": 1, "yref": "paper",
         "line": {"color": BLUE, "width": 2, "dash": "dash"}},
    ]
    return {
        "data": [{"type": "histogram", "name": unit, "x": values, "nbinsx": 30,
                  "marker": {"color": BAND_80, "line": {"color": BLUE, "width": 1}}}],
        "layout": layout,
    }


def _heatmap_chart(args, ctx) -> dict:
    import pandas as pd

    from app.forecasting.series import to_series

    keys = _series_keys_arg(args, ctx)
    if len(keys) < 2:
        raise KeyError(
            "A correlation heatmap needs at least 2 series_keys. Available: "
            f"{sorted(ctx.data_store) or '<none fetched yet>'}."
        )
    frame = pd.DataFrame(
        {key: to_series(_data_for(ctx, key).observations) for key in keys}
    ).dropna()
    if frame.empty:
        raise ValueError(
            "These series have no overlapping dates, so no correlation can be computed. "
            "Pick series that cover a common period."
        )
    changes = frame.pct_change().dropna()
    corr = (changes if len(changes) >= 8 else frame).corr()
    labels = [(_data_for(ctx, k).meta.title or k)[:40] for k in keys]
    layout = _layout(args.get("title", "Correlation matrix"))
    layout["xaxis"] = {"tickangle": -30}
    return {
        "data": [{
            "type": "heatmap",
            "z": [[float(v) for v in row] for row in corr.values],
            "x": labels, "y": labels,
            "zmin": -1, "zmax": 1,
            "colorscale": [[0, "#e34948"], [0.5, "#f0efec"], [1, "#2a78d6"]],
            "texttemplate": "%{z:.2f}",
            "colorbar": {"thickness": 12},
        }],
        "layout": layout,
    }


def _model_compare_chart(args, ctx) -> dict:
    data = _data_for(ctx, args.get("series_key"))
    series = to_series(data.observations)
    tail = series.iloc[-24:]
    traces = [
        {"type": "scatter", "name": "History", "mode": "lines",
         "x": [d.strftime("%Y-%m-%d") for d in tail.index],
         "y": [float(v) for v in tail.values],
         "line": {"color": MUTED, "width": 2}},
    ]
    indices = args.get("result_indices") or list(range(len(ctx.results)))
    for i, idx in enumerate(indices):
        result = _result_for(ctx, idx, need_forecast=False)
        if not hasattr(result, "point"):
            continue
        traces.append(
            {"type": "scatter", "name": result.model_name, "mode": "lines+markers",
             "x": result.forecast_dates, "y": result.point,
             "line": {"color": SERIES_COLORS[i % len(SERIES_COLORS)], "width": 2,
                      "dash": "dash"},
             "marker": {"size": 7}}
        )
    return {"data": traces, "layout": _layout(args.get("title", "Model comparison"))}


def build_chart(args, ctx):
    kind = args["kind"]
    builders = {
        "fan": _fan_chart,
        "panel": _indicator_panel,
        "backtest": _backtest_chart,
        "yield_curve": _yield_curve_chart,
        "decomposition": _decomposition_chart,
        "distribution": _distribution_chart,
        "heatmap": _heatmap_chart,
        "model_compare": _model_compare_chart,
    }
    if kind == "table":
        data = _data_for(ctx, args.get("series_key"))
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
            "'decomposition' (trend/seasonal/residual split; needs series_key), "
            "'distribution' (histogram of period changes with stats; needs series_key), "
            "'heatmap' (correlation matrix; needs series_keys), 'model_compare' "
            "(overlay several models' forecasts; needs series_key + result_indices), "
            "'table' (raw observations; needs series_key). Build the widest appropriate "
            "set of charts for every forecast."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "kind": {"type": "string",
                         "enum": ["fan", "panel", "backtest", "yield_curve", "decomposition",
                                  "distribution", "heatmap", "model_compare", "table"]},
                "title": {"type": "string"},
                "series_key": {"type": "string"},
                "series_keys": {"type": "array", "items": {"type": "string"}},
                "result_index": {"type": "integer"},
                "result_indices": {"type": "array", "items": {"type": "integer"},
                                   "description": "model_compare: which results to overlay"},
                "indexed": {"type": "boolean", "description": "panel: rebase each series to 100"},
                "pct": {"type": "boolean", "description": "distribution: percent (default) vs absolute changes"},
            },
            "required": ["kind", "title"],
        },
        fn=build_chart,
    ),
]
