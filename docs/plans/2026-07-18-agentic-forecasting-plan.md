# Agentic Forecasting Platform Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a local agentic macroeconomic forecasting app: projects/chats UI, dynamic multi-agent workflows over real economic data APIs, econometric forecasting with charts + methodology explanations, 5-type agent memory, multi-LLM providers, full telemetry and token/system usage tracking.

**Architecture:** FastAPI backend (SQLite/SQLAlchemy, SSE streaming) with a custom Planner→DAG→Executor agent engine, pluggable tools (data connectors, forecasting toolbox, web search, HTTP, MCP), pluggable memory backends. React/Vite/TS + Tailwind frontend with collapsible project sidebar, streaming chat, Fragments-style output panel (Charts/Data/Report/Trace), usage dashboard, settings.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy (sync engine, SQLite), pydantic v2, httpx, statsmodels, scikit-learn, pandas, anthropic, openai, google-genai, ddgs, psutil, pynvml (optional), pytest. React 18, Vite, TypeScript, Tailwind CSS, Plotly.js (react-plotly.js), vitest.

**Design doc:** `docs/plans/2026-07-18-agentic-forecasting-design.md`

**Conventions:**
- Backend in `backend/`, frontend in `frontend/`. Backend package name: `app`.
- Run backend tests: `cd backend && python -m pytest -q`. All tests offline (recorded fixtures + FakeLLM); network tests marked `@pytest.mark.network`, excluded by default via `addopts = -m "not network"`.
- Commit after each task. TDD: write the failing test first for every unit of logic.
- IDs: `uuid4().hex`. Timestamps: UTC ISO strings.
- API keys live in `backend/.env` (gitignored), loaded via pydantic-settings; never in DB.

---

### Task 1: Scaffolding

**Files:** `backend/pyproject.toml`, `backend/app/__init__.py`, `backend/app/main.py`, `backend/app/config.py`, `backend/tests/test_health.py`, `frontend/` (Vite React-TS scaffold + Tailwind), `.gitignore`, `README.md`

1. Create backend venv `backend/.venv`; install: fastapi uvicorn[standard] sqlalchemy pydantic pydantic-settings httpx pandas numpy statsmodels scikit-learn anthropic openai google-genai ddgs psutil python-dotenv pytest sse-starlette
2. `app/main.py`: FastAPI app factory, CORS for localhost:5173, `GET /api/health` → `{"status":"ok"}`.
3. Failing test `test_health.py` (httpx ASGI client) → implement → pass.
4. Scaffold frontend: `npm create vite@latest frontend -- --template react-ts`; add tailwind, react-router-dom, react-plotly.js plotly.js-dist-min, zustand.
5. `.gitignore`: .venv, node_modules, *.db, .env, dist, __pycache__. Commit: `feat: scaffold backend and frontend`.

### Task 2: Database schema

**Files:** `backend/app/db.py`, `backend/app/models.py`, `backend/tests/test_models.py`

Tables (SQLAlchemy declarative, sync engine `sqlite:///data/app.db`, `check_same_thread=False`):
- `projects(id, name, description, created_at, updated_at)`
- `chats(id, project_id FK, title, created_at, updated_at)`
- `messages(id, chat_id FK, role[user|assistant|system], content TEXT, run_id NULL, created_at)`
- `runs(id, chat_id FK, project_id, question, status[planning|running|completed|failed], plan_json TEXT, error TEXT, started_at, finished_at)`
- `artifacts(id, run_id FK, project_id, kind[chart|table|report|file], title, payload_json TEXT, created_at)`
- `events(id, project_id, run_id NULL, trace_id, span_id, parent_span_id NULL, actor[user|system|agent:<role>], event_type, payload_json TEXT, ts)`
- `token_usage(id, project_id, run_id NULL, provider, model, agent_role, input_tokens, output_tokens, est_cost_usd REAL, ts)`
- `memory_items(id, project_id NULL, chat_id NULL, mem_type[short_term|episodic|semantic|procedural], key TEXT, content TEXT, meta_json TEXT, created_at, updated_at)` (long-term = persistence of all rows)
- `series_cache(id, source, series_key, params_hash, payload_json TEXT, fetched_at)` with unique(source, series_key, params_hash)
- `resource_samples(id, project_id, run_id, cpu_percent REAL, mem_percent REAL, gpu_util REAL NULL, gpu_mem REAL NULL, ts)`
- `app_settings(key PK, value_json TEXT)` — provider config (non-secret), memory integrations, MCP servers, default paths.

TDD: test create-all + insert/roundtrip of each table. Commit: `feat: database schema`.

### Task 3: Projects/Chats/Messages CRUD + search API

**Files:** `backend/app/routers/projects.py`, `chats.py`, `backend/app/schemas.py`, `backend/tests/test_projects_api.py`

Endpoints: `POST/GET /api/projects` (GET supports `?q=` substring search on name/description), `GET/DELETE /api/projects/{id}` (delete cascades chats/messages/runs/artifacts), `PATCH /api/projects/{id}`; `POST /api/projects/{id}/chats`, `GET /api/projects/{id}/chats`, `GET/DELETE /api/chats/{id}`, `GET /api/chats/{id}/messages`. Every mutation writes a user-actor event row. TDD each endpoint. Commit: `feat: projects and chats API`.

### Task 4: LLM provider layer

**Files:** `backend/app/llm/base.py`, `anthropic_adapter.py`, `openai_adapter.py`, `gemini_adapter.py`, `fake.py`, `registry.py`, `backend/app/routers/providers.py`, `backend/tests/test_llm.py`

Interface:
```python
@dataclass
class LLMResponse: text: str; input_tokens: int; output_tokens: int; model: str; provider: str
class LLMAdapter(Protocol):
    def complete(self, system: str, messages: list[dict], model: str, json_mode: bool = False) -> LLMResponse: ...
```
- `openai_adapter` takes `base_url` → covers OpenAI, NVIDIA (`https://integrate.api.nvidia.com/v1`), Ollama (`http://localhost:11434/v1`).
- `registry.py`: reads provider config (env keys + app_settings for model names/order), exposes `complete_with_fallback(...)` that walks the configured provider chain, records a `token_usage` row per call (cost table for known models, 0 for local), emits `llm_call` event.
- `fake.py`: scripted FakeLLM returning queued responses — used by all engine tests.
- Router: `GET/PUT /api/settings/providers` (models, order, enabled; key presence reported as boolean only), `POST /api/settings/providers/test` (live ping, network-marked in tests).
TDD with FakeLLM + monkeypatched adapters. Commit: `feat: multi-provider LLM layer with fallback and token ledger`.

### Task 5: Connector framework + FRED + World Bank

**Files:** `backend/app/connectors/base.py`, `cache.py`, `fred.py`, `worldbank.py`, `registry.py`, `backend/tests/test_connectors.py`, fixtures in `backend/tests/fixtures/`

```python
class Connector(Protocol):
    source: str
    def search(self, query: str, limit: int = 10) -> list[SeriesMeta]: ...
    def fetch(self, series_id: str, **params) -> SeriesData: ...  # SeriesData: meta + list[(date, value)]
```
- `cache.py`: get/put via series_cache table, TTL 24h.
- httpx with 3-retry exponential backoff; failures raise `ConnectorError` (becomes trace event upstream).
- FRED: `series/search` + `series/observations` (key from env `FRED_API_KEY`). World Bank: `api.worldbank.org/v2` indicator search + country/indicator data (no key).
- Tests: recorded JSON fixtures, httpx transport mocked; cache hit test; retry test.
Commit: `feat: connector framework with FRED and World Bank`.

### Task 6: Remaining connectors + registry

**Files:** `backend/app/connectors/imf.py`, `bls.py`, `ecb.py`, `oecd.py`, `stubs.py` (BEA, Census raise `NotImplementedConnector` with helpful message), extend registry + tests.

- IMF: `dataservices.imf.org/REST/SDMX_JSON.svc` (CompactData/DataStructure). BLS: `api.bls.gov/publicAPI/v2/timeseries/data` (optional key). ECB: `data-api.ecb.europa.eu/service/data` (SDMX-JSON). OECD: `sdmx.oecd.org/public/rest/data` (SDMX-JSON, csv fallback).
- `registry.get(source)` + `registry.available()` reporting key status. `GET /api/datasources` endpoint.
- Fixture-based tests per connector. Commit: `feat: IMF, BLS, ECB, OECD connectors`.

### Task 7: Forecasting toolbox — utils, baselines, metrics

**Files:** `backend/app/forecasting/series.py` (to_pandas, align frequencies, resample), `metrics.py` (rmse, mape, backtest split), `baselines.py` (naive last-value, seasonal naive, drift), `backend/tests/test_forecasting_basics.py`

TDD on synthetic series with known answers. Commit: `feat: forecasting utils, baselines, backtest metrics`.

### Task 8: Forecasting toolbox — models

**Files:** `backend/app/forecasting/univariate.py` (ARIMA/SARIMAX auto-order lite, ETS), `var.py`, `nowcast.py` (bridge regression on hi-freq indicators + PCA dynamic-factor lite), `yield_curve.py` (Nelson-Siegel fit + factor AR extrapolation), `credit.py` (GradientBoosting + logistic baseline; features from macro panel), `registry.py` (`run_model(name, data, horizon, **kw) -> ForecastResult`), tests.

`ForecastResult`: point forecast, CI bands (80/95), fitted values, model metadata (order, params, fit stats), backtest metrics vs baselines. Each model tested on synthetic data (e.g., AR(1) recovered; Nelson-Siegel fits generated curve within tol). Commit: `feat: econometric model suite`.

### Task 9: Memory system — interface + SQLite backend

**Files:** `backend/app/memory/base.py`, `sqlite_backend.py`, `service.py`, `backend/tests/test_memory.py`

```python
class MemoryBackend(Protocol):
    name: str
    def add(self, mem_type, content, *, project_id=None, chat_id=None, key=None, meta=None) -> str: ...
    def search(self, query, mem_type=None, project_id=None, limit=5) -> list[MemoryItem]: ...
    def get_recent(self, mem_type, project_id=None, chat_id=None, limit=20) -> list[MemoryItem]: ...
    def delete(self, item_id) -> None: ...
```
- SQLite backend: semantic search via TF-IDF (sklearn) over content, rebuilt lazily.
- `service.py`: typed helpers — `remember_episode(run)`, `remember_procedure(question_kind, dag, metrics)`, `semantic_facts(query)`, `short_term(chat_id)` (last N messages), all delegating to active backend.
- Contract test suite parametrized over backends (SQLite now; adapters reuse it). Commit: `feat: five-type memory system with SQLite backend`.

### Task 10: Memory integrations (Mem0, Zep, stubs)

**Files:** `backend/app/memory/mem0_backend.py`, `zep_backend.py`, `integrations.py` (catalog: letta, supermemory, cognee, hindsight, retaindb, everos, maximem_synap, supabase — status `configurable`, connect stub storing config in app_settings), `backend/app/routers/integrations.py`, tests (adapters tested against mocked HTTP; contract tests reused).

`GET/PUT /api/settings/integrations`, `POST .../test`. Active backend selectable; falls back to SQLite if unreachable (event logged). Commit: `feat: pluggable memory integrations`.

### Task 11: Agent tools

**Files:** `backend/app/agents/tools/__init__.py` (ToolSpec registry: name, description, json schema, fn), `data_tool.py` (search_series, fetch_series across connectors), `forecast_tool.py` (list_models, run_model), `web_search.py` (ddgs, top-5 title/url/snippet), `http_tool.py` (GET, https-only, 15s timeout, 256KB cap), `mcp_tool.py` (connect to user-configured MCP servers from app_settings via `mcp` package; graceful if none), `charts.py` (build Plotly figure dicts: line+CI fan chart, multi-indicator panel, backtest comparison, yield-curve surface, bar/heatmap), tests for each tool with mocks.

Every tool invocation returns JSON-serializable result + emits `tool_call` event with args/result-summary. Commit: `feat: agent toolbelt`.

### Task 12: Agent engine — roles, planner, executor

**Files:** `backend/app/agents/roles.py`, `planner.py`, `executor.py`, `events.py` (emit helper writing events table + pushing to in-memory run queue for SSE), `backend/tests/test_planner.py`, `test_executor.py`

- `roles.py`: registry — data_scout, data_fetcher, modeler, validator, explainer, chart_builder; each: system prompt, allowed tools, output contract.
- `planner.py`: prompt = question + role registry + procedural-memory templates + episodic summaries → JSON plan `{kind, nodes:[{id, role, instructions, depends_on[]}]}`. Validate (pydantic; DAG acyclic; roles known); on invalid JSON retry once; on failure fall back to built-in template DAG per question kind (nowcast, default_risk, yield_curve, geopolitical, generic).
- `executor.py`: topo-order execution (ThreadPoolExecutor for independent nodes), each node = agentic loop (LLM + allowed tools, max 8 iterations), node outputs passed to dependents; per-node span events (`node_started/finished/failed`), resource sampler thread (psutil/pynvml) writing resource_samples every 2s during run; on node failure → validator-driven single replan attempt, else run failed with readable error.
- Outputs collected: charts (Plotly dicts) → artifacts kind=chart; report markdown → kind=report; data tables → kind=table.
- After success: episodic memory write + procedural template save.
- All tests with FakeLLM scripts (plan JSON, node responses); no network. Commit: `feat: dynamic agent engine (planner + DAG executor)`.

### Task 13: Chat pipeline + SSE

**Files:** `backend/app/routers/chat.py`, `backend/app/agents/pipeline.py`, `backend/tests/test_chat_pipeline.py`

- `POST /api/chats/{id}/messages` → persist user message → classify intent (LLM w/ heuristic fallback: forecast_request | followup | smalltalk) → forecast: create run, launch engine in background thread; followup: explainer answers from latest run's trace/artifacts/memory; response includes `run_id`.
- `GET /api/runs/{id}/stream` (SSE): replay persisted events then live-stream queue until terminal; event JSON: `{type, span_id, parent, role, payload, ts}`.
- `GET /api/runs/{id}` (status+plan+artifacts), `GET /api/runs/{id}/artifacts`.
- Assistant message (forecast summary + methodology from explainer) persisted on completion.
TDD with FakeLLM end-to-end through ASGI client. Commit: `feat: chat pipeline with streaming runs`.

### Task 14: Telemetry + usage APIs

**Files:** `backend/app/routers/telemetry.py`, `backend/tests/test_telemetry.py`

- `GET /api/runs/{id}/trace` → span tree (nested by parent_span_id).
- `GET /api/projects/{id}/usage` → tokens by provider/model/role, est cost, time buckets; resource sample series; run counts.
- `GET /api/projects/{id}/events?limit&offset&actor` audit list.
TDD on seeded rows. Commit: `feat: telemetry and usage endpoints`.

### Task 15: File save flow

**Files:** `backend/app/routers/files.py`, tests.

- `POST /api/artifacts/{id}/save` body `{directory}` → validates dir exists (default `~/Desktop`), writes artifact (report→.md, table→.csv, chart→.html self-contained Plotly or .json) → returns path; emits user event. `GET /api/fs/default-dir`. Commit: `feat: artifact file export`.

### Task 16: Frontend shell + projects sidebar

**Files:** `frontend/src/` — `api/client.ts`, `store/` (zustand), `components/Sidebar.tsx`, `Layout.tsx`, pages `ChatPage.tsx`, `UsagePage.tsx`, `SettingsPage.tsx`, router in `App.tsx`; minimal design system (`styles`: neutral slate palette, Inter font, light+dark).

Collapsible left sidebar: search box (server `?q=`), project list w/ chats nested, new project/chat, delete w/ confirm. Vitest: sidebar renders/filters (msw-mocked API). Commit: `feat: app shell and project sidebar`.

### Task 17: Chat view with streaming run progress

**Files:** `frontend/src/components/Chat/*` — `MessageList.tsx`, `Composer.tsx`, `RunProgress.tsx` (plan DAG as step list with live statuses), `useRunStream.ts` (EventSource hook).

Markdown rendering (react-markdown) for messages/reports; agent progress card shows plan then per-node status/spinners/errors; suggestion chips for the 4 use-cases on empty chat. Commit: `feat: streaming chat view`.

### Task 18: Output panel (Charts/Data/Report/Trace)

**Files:** `frontend/src/components/OutputPanel/*` — `ChartsTab.tsx` (react-plotly from artifact payloads), `DataTab.tsx` (tables), `ReportTab.tsx` (markdown methodology), `TraceTab.tsx` (span tree with expand, durations, token counts), `SaveDialog.tsx` (directory prompt → save API).

Load `dataviz` skill before building chart components. Panel opens on run completion; resizable; per-run artifact selector. Commit: `feat: fragments-style output panel`.

### Task 19: Usage dashboard + settings pages

**Files:** `frontend/src/pages/UsagePage.tsx` (token spend charts, cost, CPU/GPU sparklines, per-role breakdown), `SettingsPage.tsx` tabs: Providers (order, models, test), Data sources (key status), Memory integrations (catalog + connect forms), MCP servers (add name/url/transport).

Commit: `feat: usage dashboard and settings`.

### Task 20: E2E smoke, README, verify

- Offline e2e: FakeLLM-driven nowcast through API creating artifacts/trace/usage (pytest).
- `README.md`: setup (keys, Ollama), run commands, architecture map.
- Manual verify with browser: create project → ask nowcast question (real provider if key present, else Ollama/FakeLLM demo mode) → charts/report/trace render → save file → dashboard shows tokens.
- `scripts/dev.ps1` to launch both servers. Commit: `feat: e2e smoke and docs`.
