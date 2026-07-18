"""Run econometric models against series stored in the run's data store."""
import pandas as pd

from app.agents.tools import ToolSpec
from app.forecasting.registry import MODEL_DESCRIPTIONS, run_model
from app.forecasting.series import to_series
from app.forecasting.yield_curve import nelson_siegel_curve, nelson_siegel_fit


def list_models(args, ctx):
    return {"models": MODEL_DESCRIPTIONS}


def _series_for(ctx, key: str) -> pd.Series:
    data = ctx.data_store.get(key)
    if data is None:
        raise KeyError(f"No fetched series under key '{key}'. Call fetch_series first.")
    return to_series(data.observations, name=key)


def run_model_tool(args, ctx):
    model = args["model"]
    horizon = int(args.get("horizon", 4))
    kwargs = {"horizon": horizon}

    if model in ("arima", "ets"):
        kwargs["series"] = _series_for(ctx, args["series_key"])
    elif model == "var":
        frames = {key: _series_for(ctx, key) for key in args["series_keys"]}
        kwargs["df"] = pd.DataFrame(frames).dropna()
        kwargs["target"] = args["target_key"]
    elif model == "bridge_nowcast":
        kwargs.pop("horizon")
        kwargs["target"] = _series_for(ctx, args["target_key"])
        kwargs["indicators"] = {
            key: _series_for(ctx, key) for key in args["indicator_keys"]
        }
    result = run_model(model, **kwargs)
    ctx.results.append(result)
    out = result.to_dict()
    out["result_index"] = len(ctx.results) - 1
    out.pop("fitted", None)  # keep the LLM-visible payload compact
    return out


def fit_yield_curve_tool(args, ctx):
    curve = {float(m): float(y) for m, y in args["yields_by_maturity"].items()}
    maturities = sorted(curve)
    yields = [curve[m] for m in maturities]
    params = nelson_siegel_fit(maturities, yields)
    grid = [0.25, 0.5, 1, 2, 3, 5, 7, 10, 20, 30]
    fitted = nelson_siegel_curve(grid, **params)
    payload = {
        "params": params,
        "observed": {str(m): curve[m] for m in maturities},
        "fitted_curve": {str(m): float(v) for m, v in zip(grid, fitted)},
    }
    ctx.results.append(payload)
    payload["result_index"] = len(ctx.results) - 1
    return payload


SPECS = [
    ToolSpec(
        name="list_models",
        description="List available forecasting models and what each is for.",
        input_schema={"type": "object", "properties": {}},
        fn=list_models,
    ),
    ToolSpec(
        name="run_model",
        description=(
            "Run a forecasting model on previously fetched series. "
            "arima/ets need series_key; var needs series_keys + target_key; "
            "bridge_nowcast needs target_key (quarterly) + indicator_keys (monthly). "
            "Returns point forecast, 80/95% bands, fit metadata, and backtest vs naive baseline."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "model": {"type": "string", "enum": list(MODEL_DESCRIPTIONS)},
                "horizon": {"type": "integer", "default": 4},
                "series_key": {"type": "string"},
                "series_keys": {"type": "array", "items": {"type": "string"}},
                "target_key": {"type": "string"},
                "indicator_keys": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["model"],
        },
        fn=run_model_tool,
    ),
    ToolSpec(
        name="fit_yield_curve",
        description=(
            "Fit a Nelson-Siegel curve to observed yields. "
            "Input: {maturity_years: yield_pct} map. Returns factor params and fitted curve."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "yields_by_maturity": {
                    "type": "object",
                    "description": "e.g. {\"0.25\": 5.2, \"2\": 4.6, \"10\": 4.4}",
                }
            },
            "required": ["yields_by_maturity"],
        },
        fn=fit_yield_curve_tool,
    ),
]
