# Agentic Forecasting

A local, chat-driven macroeconomic forecasting platform. Ask a forecasting question in a
project chat — a dynamically planned team of agents picks the data, pulls it from official
sources, runs econometric models, renders charts, and explains its methodology. Every
decision is traceable, and every token is accounted for.

## What it does

- **Forecasting use-cases:** GDP/inflation nowcasting, sovereign default risk, yield-curve
  trajectories, geopolitical & supply-chain spillovers — all through one agentic pipeline.
- **Dynamic agent workflows:** a planner LLM composes a run-specific DAG from specialist
  roles (data scout, fetcher, modeler, validator, chart builder, explainer); an executor
  streams every step live to the UI.
- **Real data:** FRED, World Bank, IMF, BLS, ECB, OECD connectors (BEA & Census registered
  as planned stubs), with retries and a 24 h SQLite cache.
- **Econometrics:** auto-order ARIMA/SARIMAX, ETS, VAR, bridge/dynamic-factor nowcasting,
  Nelson-Siegel yield curves, gradient-boosted credit risk — always backtested against a
  naive baseline so the explanation is honest.
- **Charts:** fan charts with confidence bands, indicator panels, backtest comparisons,
  yield curves, and data tables in a Fragments-style output panel (Charts / Data / Report /
  Trace tabs), exportable to your Desktop.
- **Memory (5 types):** short-term chat context, episodic run history, semantic facts with
  retrieval, procedural workflow templates, all persisted long-term in SQLite — pluggable
  backends with Mem0 and Zep adapters plus connect stubs for Letta, Supermemory, Cognee,
  Hindsight, RetainDB, EverOS, Maximem Synap, and Supabase.
- **LLM providers:** Claude (Anthropic), OpenAI, Gemini, NVIDIA NIM, and local Ollama with
  ordered fallback — plus a deterministic demo mode when nothing is configured.
- **Telemetry:** every user action and agent decision is an event with trace/span ids; a
  per-project dashboard tracks tokens, estimated cost, CPU/RAM/GPU during runs.

## Setup

Backend (Python 3.12+):

```powershell
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install fastapi "uvicorn[standard]" sqlalchemy pydantic pydantic-settings httpx httpx2 pandas numpy statsmodels scikit-learn anthropic openai google-genai ddgs psutil nvidia-ml-py python-dotenv pytest sse-starlette mcp
copy .env.example .env   # then add the keys you have
```

Frontend (Node 20+):

```powershell
cd frontend
npm install
```

### Keys (`backend/.env`, all optional)

| Key | Enables |
| --- | --- |
| `ANTHROPIC_API_KEY` | Claude models (recommended orchestrator) |
| `OPENAI_API_KEY` | OpenAI models |
| `GEMINI_API_KEY` | Gemini models |
| `NVIDIA_API_KEY` | NVIDIA NIM endpoints |
| `OLLAMA_BASE_URL` | Local Ollama (default `http://localhost:11434/v1`) |
| `FRED_API_KEY` | FRED data (free: fred.stlouisfed.org) |
| `BLS_API_KEY` | Higher BLS rate limits (optional) |
| `MEM0_API_KEY`, `ZEP_API_KEY` | Cloud memory backends |

With no keys at all the app still works: Ollama is tried first, then a deterministic demo
workflow produces a real ARIMA forecast from World Bank data, clearly labeled as demo mode.

## Run

```powershell
scripts\dev.ps1
```

or manually in two terminals:

```powershell
cd backend; .venv\Scripts\python -m uvicorn app.main:create_app --factory --port 8000
cd frontend; npm run dev
```

Open http://localhost:5173 — create a project in the sidebar, open a chat, and ask e.g.
*“Nowcast US GDP growth for the current quarter.”*

## Tests

```powershell
cd backend; .venv\Scripts\python -m pytest      # 89 tests, all offline
cd frontend; npx vitest run                      # store tests
```

## Architecture

```
frontend/  React + Vite + TS + Tailwind + Plotly
  src/components/Sidebar        collapsible projects/chats
  src/components/Chat           streaming chat + live workflow progress (SSE)
  src/components/OutputPanel    Charts / Data / Report / Trace + save dialog
  src/pages                     Usage dashboard, Settings

backend/   FastAPI + SQLAlchemy (SQLite) + SSE
  app/agents/engine   planner (LLM→DAG, template fallback), executor, event bus, sampler
  app/agents/tools    search/fetch series, run_model, charts, web search, http, MCP, memory
  app/connectors      FRED, World Bank, IMF, BLS, ECB, OECD (+ cache, retries, stubs)
  app/forecasting     ARIMA/ETS/VAR, nowcast, Nelson-Siegel, credit, backtesting
  app/llm             Anthropic / OpenAI-compatible / Gemini adapters, fallback registry
  app/memory          5-type memory, SQLite backend, Mem0/Zep adapters, catalog
  app/routers         projects, chats, chat pipeline, telemetry, settings, file export
```

Design and plan documents live in `docs/plans/`.
