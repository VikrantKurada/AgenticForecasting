# Capabilities

The complete enumeration. Nobody reads this end to end; everybody greps it.
Every list here comes from a command you can re-run, named beside it. When a
list and the code disagree, the code is right and this page is stale; fix it.

## Agent roles (6)

From `backend/app/agents/engine/roles.py` (`grep -oE '"\w+": AgentRole'`). Each
role is a language model loop with exactly these tools allowed.

| Role | Duty | Allowed tools |
|---|---|---|
| `data_scout` | Choose which series and sources answer the question | `search_series`, `recall_memory`, `web_search` |
| `data_fetcher` | Fetch the chosen series and verify quality | `fetch_series`, `search_series`, `http_get`, `mcp_list_tools`, `mcp_call_tool` |
| `modeler` | Select and run models | `list_models`, `run_model`, `fit_yield_curve` |
| `validator` | Stress-test the modeling choices | `list_models`, `run_model`, `recall_memory` |
| `chart_builder` | Build the chart set | `build_chart` |
| `explainer` | Write the report and cite the figures | `recall_memory`, `save_fact` |

## Tools (12)

From `backend/app/agents/tools/` (`grep -c 'ToolSpec(' app/agents/tools/*.py`).
The allow-list per role is enforced in the executor; a call to a tool a role
does not have returns an error.

| Tool | Does | File |
|---|---|---|
| `search_series` | Search series across connectors | `data_tool.py` |
| `fetch_series` | Fetch and store a series under a key | `data_tool.py` |
| `list_models` | List the models and what each is for | `forecast_tool.py` |
| `run_model` | Run a model, return forecast + backtest | `forecast_tool.py` |
| `fit_yield_curve` | Fit a Nelson-Siegel curve | `forecast_tool.py` |
| `build_chart` | Build one chart or table artifact | `charts.py` |
| `recall_memory` | Recall facts and recent episodes | `memory_tool.py` |
| `save_fact` | Save a durable semantic fact | `memory_tool.py` |
| `web_search` | DuckDuckGo search | `web_search.py` |
| `http_get` | Fetch an arbitrary URL | `http_tool.py` |
| `mcp_list_tools` | List tools on a configured MCP server | `mcp_tool.py` |
| `mcp_call_tool` | Call a tool on an MCP server | `mcp_tool.py` |

## Forecasting models (8)

From `MODEL_DESCRIPTIONS` in `backend/app/forecasting/registry.py`
(`len(MODEL_DESCRIPTIONS)`). Each returns a point forecast, 80/95% bands, fit
metadata, and a backtest against a naive last-value baseline.

| Key | Method |
|---|---|
| `arima` | ARIMA/SARIMAX, automatic order selection |
| `ets` | Exponential smoothing with damped trend |
| `theta` | Theta method |
| `gbm` | Gradient boosting on lag features |
| `montecarlo` | Monte Carlo bootstrap of historical changes |
| `ensemble` | Average of ARIMA + ETS + Theta |
| `var` | Vector autoregression (multivariate) |
| `bridge_nowcast` | Bridge/dynamic-factor nowcast of a quarterly target |

## Chart kinds (9)

From the `builders` dict plus `table` in `backend/app/agents/tools/charts.py`.

| Kind | Shows |
|---|---|
| `fan` | History plus forecast with 80/95% bands |
| `panel` | Multiple indicators, optionally rebased to 100 |
| `backtest` | Model RMSE/MAPE vs naive baseline |
| `yield_curve` | Observed yields plus Nelson-Siegel fit |
| `decomposition` | Trend, seasonal, residual split (STL or rolling) |
| `distribution` | Histogram of period changes with stats |
| `heatmap` | Correlation matrix across series |
| `model_compare` | Several models' forecasts overlaid |
| `table` | Raw observations, saveable as CSV |

## Data connectors (11 wired)

From the connectors dict in `backend/app/connectors/registry.py`. A 45-source
catalog in 7 categories (`backend/app/connectors/catalog.py`, `len(SOURCES)`)
accepts API keys in Settings ahead of the connector shipping.

| Source | Coverage | Key |
|---|---|---|
| `fred` | Federal Reserve economic data | optional (higher limits) |
| `worldbank` | World Bank indicators (`COUNTRY:INDICATOR`) | none |
| `imf` | IMF data services | none |
| `bls` | US Bureau of Labor Statistics | optional |
| `ecb` | European Central Bank | none |
| `oecd` | OECD (SDMX) | none |
| `dbnomics` | 80+ upstream statistical providers | none |
| `treasury` | US Treasury Fiscal Data | none |
| `eia` | US Energy Information Administration | required |
| `faostat` | FAO agricultural commodities | none |
| `alphavantage` | Equities, forex, crypto | required |

Plus an `uploads` connector that serves attached CSV/Excel files as a data
source.

## LLM providers (5 + demo)

From `DEFAULT_ORDER` in `backend/app/llm/builder.py`. Tried in order; the first
that responds wins. The demo provider is always last and needs nothing.

| Provider | Default model | Reached |
|---|---|---|
| `anthropic` | `claude-opus-4-8` | `ANTHROPIC_API_KEY` |
| `openai` | `gpt-4o` | `OPENAI_API_KEY` |
| `gemini` | `gemini-2.5-flash` | `GEMINI_API_KEY` |
| `nvidia` | `meta/llama-3.3-70b-instruct` | `NVIDIA_API_KEY` |
| `ollama` | `llama3.2` | local `OLLAMA_BASE_URL` |
| `demo` | `demo-1` | always |

## Memory (4 types, 3 backends, 8 stubs)

Types are the `mem_type` values in `backend/app/models.py` and the methods on
`MemoryService`. All persist long-term in SQLite (the fifth property the README
sometimes counts as a "type").

| Type | Holds |
|---|---|
| `short_term` | Rolling window over a chat's messages |
| `episodic` | Past run questions, plans, and outcomes |
| `semantic` | Durable facts, retrieved by TF-IDF similarity |
| `procedural` | Successful plan templates per question kind |

Backends: `sqlite` (default), `mem0`, `zep`. Connect stubs, from
`backend/app/memory/integrations.py`: Letta, Supermemory, Cognee, Hindsight,
RetainDB, EverOS, Maximem Synap, Supabase.

## API endpoints (40 + health)

From `@router.(get|post|patch|put|delete)` across `backend/app/routers/`.
`/api/health` is defined inline in `main.py` and is the 41st.

<details>
<summary><strong>Full endpoint list</strong></summary>

```
GET    /api/health
GET    /api/projects
POST   /api/projects
GET    /api/projects/{project_id}
PATCH  /api/projects/{project_id}
DELETE /api/projects/{project_id}
GET    /api/projects/{project_id}/chats
POST   /api/projects/{project_id}/chats
GET    /api/projects/{project_id}/usage
GET    /api/projects/{project_id}/events
GET    /api/projects/{project_id}/files
POST   /api/projects/{project_id}/files
POST   /api/projects/{project_id}/export
GET    /api/chats/{chat_id}
PATCH  /api/chats/{chat_id}
DELETE /api/chats/{chat_id}
GET    /api/chats/{chat_id}/messages
POST   /api/chats/{chat_id}/messages
GET    /api/chats/{chat_id}/runs
GET    /api/chats/{chat_id}/files
POST   /api/chats/{chat_id}/files
POST   /api/chats/{chat_id}/export
GET    /api/runs/{run_id}
GET    /api/runs/{run_id}/artifacts
GET    /api/runs/{run_id}/trace
GET    /api/runs/{run_id}/stream
POST   /api/runs/{run_id}/rerun
GET    /api/datasources
GET    /api/settings/providers
PUT    /api/settings/providers
POST   /api/settings/providers/test
GET    /api/settings/datasource-keys
PUT    /api/settings/datasource-keys
GET    /api/settings/integrations
PUT    /api/settings/integrations
POST   /api/settings/integrations/test
GET    /api/settings/mcp
PUT    /api/settings/mcp
GET    /api/fs/default-dir
POST   /api/artifacts/{artifact_id}/save
DELETE /api/files/{file_id}
```

</details>

## Database tables (12)

Model classes in `backend/app/models.py`: `projects`, `chats`, `messages`,
`runs`, `artifacts`, `events`, `token_usage`, `memory_items`, `series_cache`,
`resource_samples`, `uploaded_files`, `app_settings`. The data model is drawn in
[../3-architecture/blueprints.md](../3-architecture/blueprints.md#b2).

## Output panel tabs (6)

From `frontend/src/components/OutputPanel/index.tsx`: Charts, Data, Report,
Method, Steps, Trace.

---

Sections: [Index](../) · [1 Why](../1-why/) · **2 Product** ·
[3 Architecture](../3-architecture/) · [4 Decisions](../4-decisions/) ·
[5 Roadmap](../5-roadmap/) · [6 Art of the possible](../6-art-of-the-possible/)

In this section: [Product](README.md) · [PRD](prd.md) · **Capabilities** ·
[Journeys](journeys.md)
