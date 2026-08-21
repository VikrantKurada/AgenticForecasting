# Low-level design

Module by module: the types, the contracts, and the constraints that are not
obvious from reading the code. The last of those is the point of this page. A
constraint you can see in the source does not need a document; the ones here are
the platform quirks, the library behaviours, and the parameters that cannot be
defaulted.

## `agents/engine/planner.py`

**Contract.** `make_plan(llm, question, memory, project_id) -> dict` returns a
validated plan: a `kind` and a list of nodes, each with an `id`, a `role`, an
`instructions` string, and a `depends_on` list. `validate_plan` enforces unique
ids, known roles, resolvable dependencies, and an acyclic graph.

**Algorithm.** Classify the question into a kind by keyword, seed the planner
prompt with prior successful plans and recent episodes from memory, ask the LLM
for JSON, validate, and retry once on invalid JSON. If both attempts fail, fall
back to a hand-written template for that kind.

**Non-obvious constraints.**

- `parse_action` is deliberately tolerant. Different providers wrap JSON in
  prose or fences, or name the fields differently (`tool_name`, `arguments`,
  `parameters`). It extracts the first JSON object and normalises the field
  names, because the tool protocol is text, not a typed API. This tolerance is
  the cost of the [central decision](../4-decisions/) and it lives here.
- `classify_kind` checks the specific forecasting kinds before the generic
  `history` check, so "forecast the yield curve trend" still plans a yield-curve
  run rather than a history one. Retrospective phrasing only wins when no
  forecasting kind and no forward-looking word matched.

## `agents/engine/executor.py`

**Contract.** `execute_run(run_id, ...)` runs a plan to completion, persisting
artifacts and a methodology document, recording events, and returning a status.
`_run_node` runs one node's LLM loop.

**Algorithm.** Topologically sort the DAG. Run ready nodes on a thread pool
(`max_workers=3`). Each node loops up to `max_node_iterations` (8) times:
complete, parse an action, execute the tool or finish, feed the result back.
Append the report and a figure index, then a methodology artifact, then persist.

**Non-obvious constraints.**

- `run_state_block(ctx)` is injected into every node's prompt. It lists the
  fetched series keys, the model result indices, and the figures so far. Without
  it, a downstream node has to guess the key a prior node stored, which is
  exactly [how charts used to fail](../1-why/what-goes-wrong.md#cluster-1-it-cannot-see-prior-state-so-it-guesses).
- `MAX_IDENTICAL_ERRORS = 3`. A node that makes the same failing call three
  times in a row aborts with a message rather than burning all eight iterations.
- Tool results fed back to the model are truncated to `MAX_TOOL_RESULT_CHARS`
  (6,000). A full series would blow the context; the model works from the
  summary and the tail.
- A node with two or fewer iterations left is told, in the tool-result feedback,
  to stop exploring and perform its core action. This is why the data fetcher no
  longer searches until it runs out of budget.

## `agents/engine/events.py` and `app/events.py`

**Contract.** `emit(...)` writes an `Event` row and publishes it to the
`RunEventBus`. `record_event(...)` writes an event within an existing session.

**Non-obvious constraints.**

- `trace_id` defaults to the `run_id`, and `parent_span_id` links a tool call to
  its node, so the Trace tab can render a span tree. The `events.trace_id`
  column is NOT NULL, so a caller outside a run must pass one; `record_event`
  generates a fresh id when none is given.
- The bus is in-memory. It fans out live events to SSE subscribers and is not a
  durable queue; the durable copy is the events table, which the stream replays
  before going live.

## `agents/tools/`

**Contract.** Every tool is a `ToolSpec(name, description, input_schema, fn)`.
`fn(args, ctx)` returns a dict. `execute_tool` wraps the call and turns any
exception into `{"error": ...}`.

**Non-obvious constraints.**

- A tool's error text is part of its contract. `run_model` and `build_chart`
  name the available series keys and result indices on failure, because the
  caller is a language model that recovers only from an informative error. A
  bare `KeyError` is a dead end. This is the single most important lesson in the
  codebase; see [Why](../1-why/).
- `build_chart`'s `distribution` kind uses percent changes only for a strictly
  positive series. A rate that crosses zero gets absolute changes instead,
  because a percent change across zero is meaningless.

## `forecasting/`

**Contract.** `run_model(name, **kwargs) -> ForecastResult` dispatches to one of
8 models. A result carries the point forecast, 80/95% bands, fit metadata, and a
backtest against a naive last-value baseline.

**Non-obvious constraints.**

- **Do not import from `statsmodels.tsa.api`.** On Windows with App Control
  enabled, importing it pulls in a DLL (`regime_switching\_kim_smoother`) that
  the OS blocks, and the process dies at import time. Import concrete modules
  instead: `statsmodels.tsa.forecasting.theta`,
  `statsmodels.tsa.vector_ar.var_model`, and so on. This is the single most
  surprising constraint in the project and it is not visible from reading the
  model code, only from the import that is deliberately avoided.
- Every model refits during its backtest. The real cost of a run is roughly
  double the naive fit cost, because the holdout score requires a refit on the
  training slice. This is where the CPU in a run actually goes.
- The `ensemble` model fits ARIMA, ETS, and Theta, so it costs three fits, not
  one.

## `connectors/`

**Contract.** A connector satisfies the `Connector` protocol: `search(query,
limit) -> list[SeriesMeta]` and `fetch(series_id, **params) -> SeriesData`.
`SeriesData` is a `SeriesMeta` plus a list of `(date_str, value_or_None)` tuples
ascending by date.

**Non-obvious constraints.**

- **`search` must return `[]` on no match.** Five catalog-backed connectors once
  returned the head of their catalog as filler, which an agent cannot tell from
  a real hit. See [what-goes-wrong.md](../1-why/what-goes-wrong.md#cluster-3-a-source-returns-filler-instead-of-nothing).
- Ids are not uniform. World Bank wants `COUNTRY:INDICATOR` and raises a
  `ConnectorError` naming the format when it gets a bare indicator. FAOSTAT wants
  `DOMAIN/AREA/ELEMENT/ITEM`. The error messages carry the format because the
  caller is an agent.
- Every real connector is wrapped in `CachedConnector`, which keys on
  `(source, series_key, params_hash)` with a 24-hour TTL. `request_json` retries
  three times with exponential backoff, treats 5xx as retryable and 4xx as
  fatal, and raises `ConnectorError` after the last attempt.

## `llm/`

**Contract.** An adapter satisfies `LLMAdapter`: `complete(system, messages,
model, json_mode) -> LLMResponse`. `LLMRegistry.complete` walks the provider
chain, records token usage and a cost estimate, and falls through on failure.

**Non-obvious constraints.**

- **The demo provider dispatches on substring matches of the system prompt**
  (`"chart builder" in system`, `"explainer" in system`). If a role's prompt
  mentions another role's marker phrase, the demo routes that role to the wrong
  branch. A prompt edit that added "chart builder" to the explainer's prompt
  broke a test for exactly this reason. Keep role prompts free of other roles'
  names.
- `estimate_cost` prefix-matches the model name, longest prefix wins, so
  `claude-opus-4-8` matches the `claude-opus` price. An unknown model estimates
  at zero rather than guessing, which is honest but means a new model shows no
  cost until its price is added.
- The registry records an `llm_error` event for every failed provider before
  falling through, so a run that ends on the demo provider still shows why each
  earlier provider was skipped.

## `memory/`

**Contract.** `MemoryService` exposes the 4 types: `short_term` (a window over
the messages table), `episodic` (`remember_episode` / `recent_episodes`),
`semantic` (`add_fact` / `semantic_facts`), and `procedural`
(`remember_procedure` / `procedures_for`).

**Non-obvious constraints.**

- Semantic recall is TF-IDF cosine similarity over stored facts
  (scikit-learn), computed locally. There is no embedding API call, so recall
  works offline and adds no token cost. It also means recall is lexical, not
  semantic in the embedding sense; a fact phrased differently from the query may
  not surface.
- The three alternate backends (Mem0, Zep) and the eight connect stubs share the
  memory-item shape, so the service does not change when the backend does. The
  stubs are wiring points, not implementations.

## Frontend (`frontend/src/`)

**Contract.** A React 19 + Vite + Tailwind app. `useAppStore` (Zustand) holds
projects and chats; pages are `Home`, `Chat`, `Usage`, `Settings`. The output
panel renders a run's artifacts and trace.

**Non-obvious constraints.**

- Inline-code styling must be scoped to `:not(pre) > code`. Applied to every
  `code`, it hits the `code` inside a fenced block too, layering a light chip
  over the dark `pre` and making code blocks unreadable. The shared
  `MarkdownBody` component fixes this once for chat, report, and methodology.
- Figure numbering in the panel must match the backend manifest: charts and
  tables in creation order. The report's "Figure N" citations refer to that
  order, so the frontend cannot renumber.
- The run stream is consumed over SSE in `useRunStream`; the panel opens on run
  completion and reads artifacts and trace over REST.

---

Sections: [Index](../) · [1 Why](../1-why/) · [2 Product](../2-product/) ·
**3 Architecture** · [4 Decisions](../4-decisions/) · [5 Roadmap](../5-roadmap/) ·
[6 Art of the possible](../6-art-of-the-possible/)

In this section: [Architecture](README.md) · [High-level design](high-level-design.md) ·
**Low-level design** · [Blueprints](blueprints.md) ·
[Integration patterns](integration-patterns.md)
