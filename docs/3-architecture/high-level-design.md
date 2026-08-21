# High-level design

## Context

What runs inside the machine, what is outside it, and what is optional.

```mermaid
flowchart TD
    subgraph Machine["Local machine"]
      BROWSER["Browser: React app"]
      BACKEND["FastAPI backend"]
      DB[("SQLite: app.db")]
      OLLAMA["Ollama (optional, local)"]
    end
    subgraph Outside["Outside (optional)"]
      DATA["Data APIs:<br/>FRED, World Bank, IMF, ..."]
      LLM["Cloud LLMs:<br/>Anthropic, OpenAI, Gemini, NVIDIA"]
      MCP["MCP servers"]
    end
    BROWSER -->|REST + SSE| BACKEND
    BACKEND --> DB
    BACKEND -->|if key set| DATA
    BACKEND -->|chain, first that answers| LLM
    BACKEND -->|if reachable| OLLAMA
    BACKEND -->|if configured| MCP
    style BROWSER fill:#2a78d6,stroke:#2a78d6,color:#fff
    style DB fill:#eda100,stroke:#eda100,color:#fff
```

Everything outside is optional. With no cloud key and no Ollama, the backend
uses the demo provider and cached or bundled data, and a run still completes.

## Components

Each backend package, what it owns, and the rule it must not break.

| Package | Owns | Must not |
|---|---|---|
| `routers/` | HTTP endpoints, request/response shapes | Contain business logic; it delegates to pipeline and services |
| `agents/engine/` | Planner, executor, event bus, sampler | Know about specific tools; it calls them by name through the belt |
| `agents/tools/` | The 12 typed tools | Reach into the DB directly except through the context or services |
| `connectors/` | Data-source access, cache, retries | Format for a chart or a model; it returns `SeriesData` |
| `forecasting/` | The 8 models, backtests, series helpers | Fetch data or call an LLM; it takes a series and returns a result |
| `llm/` | Provider adapters, the fallback chain, cost | Know what a run is; it takes messages and returns text |
| `memory/` | The 4 memory types, backends, adapters | Be required; a run works with the SQLite default alone |

The "must not" column is the load-bearing part. It is what keeps a change in one
package from rippling into another.

## The main pipeline

```mermaid
flowchart TD
    MSG["User message"] --> INT{"classify_intent"}
    INT -->|forecast / data| RUN["create Run"]
    INT -->|followup| FUP["answer from run context"]
    INT -->|smalltalk| SMALL["brief reply"]
    RUN --> PLAN["make_plan: DAG"]
    PLAN --> EXEC["execute_run"]
    EXEC --> NODES["run nodes in topo order"]
    NODES --> ART["persist artifacts"]
    ART --> REP["append figure index to report"]
    REP --> DONE["run_completed"]
```

The intent gate is the first fork and the one that used to fail; a data question
that missed it fell into `smalltalk` and got a tool-less answer. See
[what-goes-wrong.md](../1-why/what-goes-wrong.md#cluster-2-it-invents-the-response-instead-of-doing-the-work).

## Data flow through one node

Every node is the same loop. The model never sees raw data; it sees tool
results, truncated to 6,000 characters, plus the injected run state.

```mermaid
sequenceDiagram
    participant N as Node (LLM loop)
    participant EX as Executor
    participant B as Toolbelt
    participant C as ToolContext
    EX->>N: system prompt + run state + assignment
    loop up to 8 iterations
        N->>EX: JSON action (tool or finish)
        alt tool
            EX->>B: execute_tool(name, args, ctx)
            B->>C: read/write data_store, results, artifacts
            B-->>EX: result dict
            EX->>N: result (<= 6000 chars)
        else finish
            N-->>EX: output markdown
        end
    end
```

`ToolContext` is the shared state for a run: the fetched series (`data_store`),
the model results (`results`), and the artifacts. A tool reads and writes it; the
executor reads it to build the run-state block that goes into the next prompt.

## Storage

One SQLite file, 12 tables. The core relationships:

```mermaid
erDiagram
    PROJECT ||--o{ CHAT : has
    CHAT ||--o{ MESSAGE : has
    CHAT ||--o{ RUN : has
    RUN ||--o{ ARTIFACT : produces
    RUN ||--o{ EVENT : emits
    RUN ||--o{ TOKEN_USAGE : records
    RUN ||--o{ RESOURCE_SAMPLE : samples
    PROJECT ||--o{ MEMORY_ITEM : accumulates
    PROJECT ||--o{ UPLOADED_FILE : holds
    PROJECT {
        string id PK
        string name
        string updated_at "for ordering"
    }
    RUN {
        string id PK
        string status "planning|running|completed|failed"
        string plan_json "the DAG, replayable"
    }
    ARTIFACT {
        string kind "chart|table|report|methodology"
        string payload_json
    }
    EVENT {
        string trace_id "= run_id for a run"
        string span_id
        string parent_span_id "builds the span tree"
    }
```

The full model, including `series_cache`, `app_settings`, and every column, is in
[blueprints.md](blueprints.md#b2).

## Transport

Two channels between browser and backend.

- **REST** for everything transactional: create a project, post a message, fetch
  a run's artifacts. Plain JSON over HTTP.
- **Server-Sent Events** for a live run. The browser opens
  `GET /api/runs/{id}/stream`; the backend replays the events already recorded,
  then streams new ones off the in-memory `RunEventBus` as they happen, ending
  with an `end` event. SSE rather than WebSockets because the flow is one-way
  (server to browser) and SSE reconnects itself.

## Deployment

Local development only. `scripts/dev.ps1` starts uvicorn on 8000 and Vite on
5173; Vite proxies `/api` to the backend. There is no container, no cloud
target, and no auth. Packaging is a [roadmap](../5-roadmap/) item, and auth is a
precondition for any networked deployment, called out as a risk in
[prd.md](../2-product/prd.md#risks).

## Quality gates

| Gate | What it checks |
|---|---|
| `pytest` (197 tests) | Every guarantee in [prd.md](../2-product/prd.md); all offline |
| `vitest` (7 tests) | The frontend store's project/chat/rename logic |
| `tsc --noEmit` | The frontend types |
| `oxlint` | The frontend lint rules |

---

Sections: [Index](../) · [1 Why](../1-why/) · [2 Product](../2-product/) ·
**3 Architecture** · [4 Decisions](../4-decisions/) · [5 Roadmap](../5-roadmap/) ·
[6 Art of the possible](../6-art-of-the-possible/)

In this section: [Architecture](README.md) · **High-level design** ·
[Low-level design](low-level-design.md) · [Blueprints](blueprints.md) ·
[Integration patterns](integration-patterns.md)
