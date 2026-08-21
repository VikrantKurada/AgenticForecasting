# Blueprints

Reference drawings, numbered. No argument here; the reasoning is in
[high-level-design.md](high-level-design.md) and
[low-level-design.md](low-level-design.md).

<a id="b1"></a>
## B1. Module dependency map

Solid arrows are allowed dependencies. Dashed arrows are the edges the
architecture forbids: the frontend does not call the engine directly, tools do
not touch the database except through the context, and forecasting never calls
an LLM.

```mermaid
flowchart TD
    ROUT["routers"] --> PIPE["agents.pipeline"]
    PIPE --> ENG["agents.engine"]
    ENG --> TOOLS["agents.tools"]
    TOOLS --> CONN["connectors"]
    TOOLS --> FCAST["forecasting"]
    TOOLS --> MEM["memory"]
    ENG --> LLM["llm"]
    ROUT --> DB[("db / models")]
    CONN --> DB
    MEM --> DB
    LLM --> DB
    FE["frontend"] -.->|"must not: use REST"| ENG
    TOOLS -.->|"must not: use context"| DB
    FCAST -.->|"must not"| LLM
    style FE fill:#2a78d6,stroke:#2a78d6,color:#fff
    style DB fill:#eda100,stroke:#eda100,color:#fff
```

<a id="b2"></a>
## B2. Full data model

All 12 tables. Ids are 32-character hex; timestamps are ISO strings.

```mermaid
erDiagram
    PROJECT ||--o{ CHAT : has
    CHAT ||--o{ MESSAGE : has
    CHAT ||--o{ RUN : has
    RUN ||--o{ ARTIFACT : produces
    PROJECT ||--o{ MEMORY_ITEM : accumulates
    PROJECT ||--o{ UPLOADED_FILE : holds
    PROJECT {
        string id PK
        string name
        string description
        string created_at
        string updated_at
    }
    CHAT {
        string id PK
        string project_id FK
        string title
    }
    MESSAGE {
        string id PK
        string chat_id FK
        string role "user|assistant|system"
        string content
        string run_id "nullable link to a run"
    }
    RUN {
        string id PK
        string chat_id FK
        string project_id
        string question
        string status "planning|running|completed|failed"
        string plan_json
        string error
        string finished_at "nullable"
    }
    ARTIFACT {
        string id PK
        string run_id FK
        string kind "chart|table|report|methodology"
        string title
        string payload_json
    }
    EVENT {
        string id PK
        string run_id "nullable"
        string trace_id
        string span_id
        string parent_span_id "nullable"
        string actor "user|system|agent:role"
        string event_type
        string payload_json
    }
    TOKEN_USAGE {
        string id PK
        string run_id "nullable"
        string provider
        string model
        string agent_role
        int input_tokens
        int output_tokens
        float est_cost_usd
    }
    RESOURCE_SAMPLE {
        string id PK
        string run_id "nullable"
        float cpu_percent
        float mem_percent
        float gpu_util "nullable"
    }
    MEMORY_ITEM {
        string id PK
        string mem_type "short_term|episodic|semantic|procedural"
        string content
        string meta_json
    }
    SERIES_CACHE {
        string id PK
        string source
        string series_key
        string params_hash
        string fetched_at "24h TTL"
    }
    UPLOADED_FILE {
        string id PK
        string filename
        string columns_json
        int n_rows
    }
    APP_SETTING {
        string key PK
        string value_json "provider order, keys, integrations"
    }
```

`EVENT`, `TOKEN_USAGE`, and `RESOURCE_SAMPLE` link to a run by id but are not
foreign-keyed, so they survive a run's deletion for audit. `MEMORY_ITEM`,
`SERIES_CACHE`, and `APP_SETTING` are standalone.

<a id="b3"></a>
## B3. Run status state machine

```mermaid
stateDiagram-v2
    [*] --> planning: create Run
    planning --> running: plan built
    running --> completed: all nodes done, artifacts persisted
    running --> failed: exception in a node or the executor
    planning --> failed: planner raised
    completed --> [*]
    failed --> [*]
    note right of running
        Nodes run in topological order.
        Independent nodes run concurrently
        on a 3-worker thread pool.
    end note
    note right of failed
        The error is stored on the Run
        and emitted as run_failed.
    end note
```

<a id="b4"></a>
## B4. Live run request lifecycle

```mermaid
sequenceDiagram
    participant B as Browser
    participant API as API
    participant EX as Executor (thread)
    participant BUS as RunEventBus
    B->>API: POST /chats/{id}/messages
    API->>EX: start run (async)
    API-->>B: { run_id }
    B->>API: GET /runs/{run_id}/stream (SSE)
    API->>API: replay recorded events
    loop live
        EX->>BUS: publish event
        BUS-->>API: event
        API-->>B: SSE run_event
    end
    EX->>BUS: close(run_id)
    BUS-->>API: __end__
    API-->>B: SSE end
```

<a id="b5"></a>
## B5. Provider fallback chain

```mermaid
flowchart LR
    START["complete()"] --> A{"anthropic?"}
    A -->|ok| DONE["record usage, return"]
    A -->|fail/none| O{"openai?"}
    O -->|ok| DONE
    O -->|fail/none| G{"gemini?"}
    G -->|ok| DONE
    G -->|fail/none| N{"nvidia?"}
    N -->|ok| DONE
    N -->|fail/none| OL{"ollama?"}
    OL -->|ok| DONE
    OL -->|fail/none| D["demo (always)"]
    D --> DONE
    style D fill:#1baf7a,stroke:#1baf7a,color:#fff
```

Each failure records an `llm_error` event before falling through, so a run that
lands on demo still shows why every earlier provider was skipped.

<a id="b6"></a>
## B6. Deployment topology

```mermaid
flowchart LR
    subgraph Local["localhost"]
      VITE["Vite dev server :5173"]
      UVI["uvicorn :8000"]
      SQLITE[("app.db")]
    end
    VITE -->|proxy /api| UVI
    UVI --> SQLITE
    UVI -.->|optional| NET["internet: data + LLM APIs"]
    style NET fill:#8d97a5,stroke:#8d97a5,color:#fff
```

---

Sections: [Index](../) · [1 Why](../1-why/) · [2 Product](../2-product/) ·
**3 Architecture** · [4 Decisions](../4-decisions/) · [5 Roadmap](../5-roadmap/) ·
[6 Art of the possible](../6-art-of-the-possible/)

In this section: [Architecture](README.md) · [High-level design](high-level-design.md) ·
[Low-level design](low-level-design.md) · **Blueprints** ·
[Integration patterns](integration-patterns.md)
