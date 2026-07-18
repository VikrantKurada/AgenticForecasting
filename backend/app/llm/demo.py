"""Deterministic last-resort adapter: drives a real workflow without any LLM.

Used when no provider (cloud key or local Ollama) is reachable, so the app still
produces a real forecast from real data — clearly labeled as demo mode.
"""
import json

from app.llm.base import LLMResponse

SERIES = {"source": "worldbank", "series_id": "US:NY.GDP.MKTP.KD.ZG"}
SERIES_KEY = f"{SERIES['source']}:{SERIES['series_id']}"

REPORT = """## Forecast (demo mode)

No LLM provider was reachable, so a built-in deterministic workflow produced this
forecast: US GDP growth (World Bank, annual) modeled with auto-selected ARIMA.

The fan chart shows the point forecast with 80% and 95% confidence bands; the
backtest chart compares the model against a naive last-value baseline on held-out
data.

### Methodology
- **Data:** World Bank `NY.GDP.MKTP.KD.ZG` (GDP growth, annual %) for the US.
- **Model:** ARIMA with automatic order selection by AIC.
- **Validation:** tail holdout backtest vs a naive baseline (RMSE / MAPE).

Configure an LLM provider in Settings for question-specific agentic forecasts.
"""


def _count_tool_results(messages: list[dict]) -> int:
    # Node conversations alternate: instructions, then (assistant, tool-result) pairs.
    return sum(1 for m in messages[1:] if m.get("role") == "user")


def _tool(name: str, args: dict) -> str:
    return json.dumps({"action": "tool", "tool": name, "args": args})


def _finish(output: str) -> str:
    return json.dumps({"action": "finish", "output": output})


class DemoLLM:
    provider = "demo"

    def complete(self, system, messages, model="demo-1", json_mode=False):
        text = self._respond(system.lower(), messages)
        return LLMResponse(
            text=text, input_tokens=0, output_tokens=0, model=model, provider=self.provider
        )

    def _respond(self, system: str, messages: list[dict]) -> str:
        step = _count_tool_results(messages)

        if "planning agent" in system:
            return "demo mode: use the template plan"  # invalid JSON → planner template
        if "data scout" in system:
            return _finish(
                f"Use {SERIES['source']} series {SERIES['series_id']} "
                "(GDP growth, annual %) — the standard series for this question in demo mode."
            )
        if "data fetcher" in system:
            if step == 0:
                return _tool("fetch_series", SERIES)
            return _finish(f"Fetched. Stored under series_key {SERIES_KEY}.")
        if "econometrician" in system:
            if step == 0:
                return _tool("run_model", {"model": "arima", "series_key": SERIES_KEY, "horizon": 4})
            return _finish("ARIMA forecast produced at result_index 0 with backtest metrics.")
        if "validator" in system:
            return _finish(
                "Demo-mode check: ARIMA order chosen by AIC; see the backtest chart for "
                "how it compares to the naive baseline."
            )
        if "chart builder" in system:
            charts = [
                _tool("build_chart", {"kind": "fan", "title": "Forecast with confidence bands",
                                      "series_key": SERIES_KEY, "result_index": 0}),
                _tool("build_chart", {"kind": "backtest", "title": "Backtest vs naive baseline",
                                      "result_index": 0}),
                _tool("build_chart", {"kind": "table", "title": "Underlying data",
                                      "series_key": SERIES_KEY}),
            ]
            if step < len(charts):
                return charts[step]
            return _finish("Created fan chart, backtest comparison, and data table.")
        if "explainer" in system:
            return _finish(REPORT)
        return _finish("Demo mode: done.")
