# Agentic Macroeconomic Forecasting Platform — Design

**Date:** 2026-07-18
**Status:** Approved
**Decisions:** FastAPI + React stack · "Core platform, deep" scope · Providers: Claude, OpenAI, Gemini, NVIDIA, Ollama · SQLite storage · Custom lightweight orchestrator (over LangGraph / CrewAI)

## Purpose

A local, single-user application for agentic macroeconomic forecasting. Users create projects containing chats; in a chat they ask a forecasting question (GDP/inflation nowcasting, sovereign default risk, yield-curve trajectories, geopolitical/supply-chain spillovers). A dynamically composed multi-agent workflow fetches real data from official sources, runs econometric models, and returns a forecast with rich charts and a methodology explanation. Everything — agent decisions, tool calls, tokens, system load — is traceable.

## Architecture overview

```
React/Vite/TS frontend (Tailwind, Plotly.js)
        │  REST + SSE
FastAPI backend (Python 3.12)
 ├── Domain: Projects → Chats → Messages → Runs → Artifacts
 ├── Agent engine: Planner → JSON DAG → Executor (streaming)
 ├── Tools: data connectors, forecasting toolbox, web search, HTTP, MCP client
 ├── Memory: 5 types over pluggable MemoryBackend (SQLite builtin; Mem0, Zep adapters)
 ├── LLM providers: Anthropic / OpenAI-compatible (OpenAI, NVIDIA, Ollama) / Gemini
 └── Telemetry: unified event store + token ledger + psutil/pynvml sampling
SQLite (SQLAlchemy + aiosqlite), one DB file
```

## Agent engine (custom orchestrator)

- **Planner agent** receives the question + project memory context and emits a run-specific workflow plan: a JSON DAG whose nodes reference an **agent-role registry** — `data_scout` (select indicators/sources), `data_fetcher`, `modeler`, `validator` (critique/backtest), `explainer` (methodology), `chart_builder` (chart specs). Roles declare which tools they may use.
- **Executor** walks the DAG (parallel where independent), streaming node status, LLM calls, tool calls, and intermediate outputs as trace events over SSE.
- Chosen over LangGraph (heavy, obscures tracing, awkward for LLM-decided graph shapes) and CrewAI/AutoGen (opinionated, weak telemetry/token accounting).
- Successful DAGs are saved as **procedural memory** templates the planner can adapt for similar questions.
- Follow-up questions in chat ("why did you pick that model?") route to a lightweight explainer flow that reads the run's trace + artifacts rather than spawning a full workflow.

## Tools available to every agent

- **Data connector tool** (see below), **forecasting toolbox tool**, **web search** (DuckDuckGo, keyless), **generic HTTP/API tool**, and an **MCP client** for user-configured MCP servers (settings UI: name, transport, URL/command).

## Data connectors

Common interface: `search(query) -> series metadata`, `fetch(series_id, params) -> observations DataFrame`, with SQLite response caching and retry/backoff. Implemented: **FRED** (key), **World Bank**, **IMF**, **BLS** (optional key), **ECB**, **OECD SDMX**. **BEA** and **Census** are registered behind the same interface as not-yet-implemented stubs with settings entries. Connector failures are trace events; the planner may re-route to an alternative source.

## Forecasting toolbox (statsmodels / scikit-learn)

- **Nowcasting:** dynamic factor model + bridge regressions on higher-frequency indicators.
- **Trajectories:** ARIMA/SARIMAX, VAR, ETS.
- **Yield curve:** Nelson-Siegel fitting and factor extrapolation.
- **Default/credit risk:** gradient-boosted classifier + logistic baseline on macro-fiscal features.
- **Geopolitical/spillover:** indicator-panel analysis + VAR impulse responses on trade/FDI series.
- Naive baselines and backtest metrics (RMSE, MAPE) always computed; the explainer generates the methodology narrative from actual run metadata (chosen model, features, fit stats, backtest results) — never boilerplate.

## Memory (5 types, pluggable)

| Type | Implementation |
|---|---|
| Short-term | Per-chat rolling context buffer |
| Episodic | Per-project record of past runs: question, DAG, data used, outcome, metrics |
| Semantic | Embedded fact store (indicator definitions, country facts) with vector retrieval |
| Procedural | Saved successful workflow DAGs as reusable templates |
| Long-term | The persistent SQLite substrate underlying all of the above |

`MemoryBackend` interface; built-in SQLite backend ships working. Real adapters: **Mem0**, **Zep**. Config-UI connect stubs: Letta, Supermemory, Cognee, Hindsight, RetainDB, EverOS, Maximem Synap, Supabase.

## LLM providers

Three adapters cover five providers: Anthropic SDK (Claude), OpenAI SDK with configurable base URL (OpenAI, NVIDIA NIM, Ollama `/v1`), Google GenAI (Gemini). Global default model, per-project override, per-agent-role override. Keys in a local config file (never in the DB, never committed). Provider failure falls back to the next configured provider. Every call writes a token-ledger row: provider, model, input/output tokens, estimated cost, agent role, run/trace IDs.

## Telemetry & usage

- Unified **event table**: user actions (project/chat CRUD, question asked, file saved) and agent events (plan created, node started/finished, tool call, decision, error) with trace_id/span_id/parent_span/timestamps/payload.
- **Trace viewer** UI per run: the DAG with per-node timeline, expandable to raw LLM/tool payloads.
- **Usage dashboard** per project: token spend by provider/model/agent role over time, cost estimate, CPU/RAM (psutil) and GPU (pynvml when NVIDIA present) sampled during runs.

## Frontend

- Minimalist, professional, neutral palette (Tailwind). Collapsible left sidebar: project search/list, new/delete project, chats within.
- Center: chat with streamed agent progress — visible plan, live node statuses, then the answer.
- Right: Fragments-style output panel, tabs **Charts / Data / Report / Trace**. Charts via Plotly.js: fan charts with confidence bands, indicator panels, backtest comparisons, yield-curve surfaces; the chart_builder agent picks the widest appropriate set per forecast type.
- Pages: Usage dashboard, Trace viewer, Settings (providers, data-source keys, memory integrations, MCP servers).
- **File outputs:** save dialog asking destination path (default: Desktop); backend writes the file.

## Error handling

Connector retries with backoff → failure trace events → planner re-routing; LLM fallback chain; runs resumable per-node; all errors surface in chat as readable status, never silent.

## Testing

pytest: connectors (recorded fixtures), forecasting toolbox (known synthetic/real series with expected properties), engine (fake LLM adapter), memory backends (interface contract tests). One smoke e2e running a real nowcast through the full stack. Frontend: vitest for stores/components.
