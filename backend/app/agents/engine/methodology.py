"""Builds the run's methodology explainer from what the workflow actually did."""
import json

BAND_NOTES = {
    "ARIMA": "80/95% bands from the state-space forecast error variance",
    "ETS": "80/95% bands from in-sample residual dispersion scaled by horizon",
    "Theta": "80/95% bands from the Theta model's analytic prediction intervals",
    "Gradient Boosting": "80/95% bands from in-sample residual dispersion scaled by horizon",
    "Monte Carlo": "bands are empirical percentiles across bootstrap simulation paths",
    "Ensemble": "bands average the member models' intervals",
    "VAR": "80/95% bands from the VAR forecast error covariance",
    "Bridge": "80/95% bands from the OLS prediction interval",
}


def _band_note(model_name: str) -> str:
    for prefix, note in BAND_NOTES.items():
        if model_name.startswith(prefix):
            return note
    return "confidence bands as reported by the model"


def _fmt(value) -> str:
    if isinstance(value, float):
        return f"{value:,.4g}"
    if isinstance(value, dict):
        return json.dumps(value, default=str)[:200]
    return str(value)


def build_methodology(question: str, plan: dict, ctx, dep_outputs: dict) -> str:
    lines: list[str] = ["# Prediction methodology", ""]
    lines += [f"**Question:** {question}", ""]

    # Workflow
    source = plan.get("metadata", {}).get("source", "llm")
    lines += [
        "## Workflow", "",
        f"Task classified as **{plan.get('kind', 'generic').replace('_', ' ')}**; the "
        f"workflow DAG was {'composed by the planner LLM' if source == 'llm' else 'instantiated from the built-in template'} "
        f"with {len(plan.get('nodes', []))} agent nodes:", "",
    ]
    for node in plan.get("nodes", []):
        # An entry node legitimately has no dependencies; saying so beats an
        # empty "depends on:" that reads like missing data.
        deps = [d for d in (node.get("depends_on") or []) if d]
        relation = (
            "runs first (entry point, no dependencies)" if not deps
            else f"depends on {', '.join(f'`{d}`' for d in deps)}"
        )
        feeds = [
            other["id"] for other in plan.get("nodes", [])
            if node["id"] in (other.get("depends_on") or [])
        ]
        feeds_note = f"; feeds {', '.join(f'`{f}`' for f in feeds)}" if feeds else "; final step"
        lines.append(f"- **{node['id']}** — role `{node['role']}`, {relation}{feeds_note}")
        instructions = (node.get("instructions") or "").strip().replace("\n", " ")
        if instructions:
            lines.append(f"  - Assignment: {instructions[:300]}")
    lines.append("")

    # Data
    lines += ["## Data", ""]
    if ctx.data_store:
        for key, data in ctx.data_store.items():
            obs = data.observations
            non_null = [o for o in obs if o[1] is not None]
            span = f"{obs[0][0]} → {obs[-1][0]}" if obs else "empty"
            latest = f", latest = {_fmt(non_null[-1][1])}" if non_null else ""
            lines.append(
                f"- `{key}` — {data.meta.title} ({data.meta.source}); "
                f"{len(obs)} observations, {span}{latest}"
            )
    else:
        lines.append("- No series were fetched during this run.")
    lines.append("")

    # Models
    lines += ["## Models", ""]
    forecast_results = [r for r in ctx.results if hasattr(r, "point")]
    other_results = [r for r in ctx.results if not hasattr(r, "point")]
    if not ctx.results:
        lines.append("No models were run.")
    for i, result in enumerate(forecast_results):
        lines += [f"### {result.model_name}", ""]
        if result.metadata:
            for meta_key, meta_val in result.metadata.items():
                lines.append(f"- {meta_key}: {_fmt(meta_val)}")
        lines.append(f"- Uncertainty: {_band_note(result.model_name)}")
        backtest = result.backtest or {}
        if "model_rmse" in backtest:
            model_rmse, base_rmse = backtest["model_rmse"], backtest["baseline_rmse"]
            verdict = (
                f"beats the naive baseline by {(1 - model_rmse / base_rmse) * 100:.1f}% RMSE"
                if base_rmse > 0 and model_rmse < base_rmse
                else "does **not** beat the naive baseline on this holdout — treat with caution"
            )
            lines += [
                "",
                f"Backtest (holdout = {backtest.get('holdout', '?')} periods): "
                f"model RMSE { _fmt(model_rmse)} vs naive baseline RMSE {_fmt(base_rmse)} — {verdict}.",
                f"MAPE: model {_fmt(backtest.get('model_mape', 0))}% vs baseline "
                f"{_fmt(backtest.get('baseline_mape', 0))}%.",
            ]
        elif backtest:
            lines.append(f"- Validation: {_fmt(backtest)}")
        lines.append("")
    for result in other_results:
        if isinstance(result, dict) and "params" in result:
            lines += [
                "### Nelson-Siegel yield curve fit", "",
                f"- Fitted factors: {_fmt(result['params'])}", "",
            ]

    # Validation commentary from the validator agent, when the plan had one
    validator_nodes = [n["id"] for n in plan.get("nodes", []) if n.get("role") == "validator"]
    for node_id in validator_nodes:
        if dep_outputs.get(node_id):
            lines += ["## Validation", "", dep_outputs[node_id][:2000], ""]

    # Figures — same numbering the report cites, so the two documents agree
    visuals = [a for a in ctx.artifacts if a["kind"] in ("chart", "table")]
    if visuals:
        lines += ["## Figures", ""]
        for i, artifact in enumerate(visuals, start=1):
            label = "data table" if artifact["kind"] == "table" else "chart"
            lines.append(f"- **Figure {i}** — {artifact['title']} ({label})")
        lines.append("")

    lines += [
        "## Reproducibility & caveats", "",
        "- Every step above is recorded in the run trace (Trace tab) with the exact "
        "tool calls and arguments.",
        "- Backtests refit each model on a training slice and score the held-out tail "
        "against a naive last-value baseline; a model that cannot beat that baseline "
        "carries little forecasting signal.",
        "- Point forecasts are conditional on the fetched history only; structural "
        "breaks, revisions, and policy shifts are not modeled unless an agent "
        "explicitly included them.",
    ]
    return "\n".join(lines)
