# Platform

The infrastructure choices, including one that is not optional on Windows.

<a id="d7"></a>
## D7. SQLite for everything

**Context.** The system needs to store projects, chats, runs, artifacts, events,
token usage, resource samples, memory, a data cache, and settings. That is a lot
of tables for a local tool.

**Options.**

- A client-server database (Postgres). Rejected: it adds an install step and a
  process to run, for a single-user local tool.
- Separate stores per concern (a cache in Redis, events in a log). Rejected:
  more moving parts, no benefit at this scale.
- One SQLite file. Chosen.

**Decision.** One `app.db` holds all 12 tables. It is the durable copy of events,
the data cache, and the settings store, and it needs no server.

The cost: SQLite's single-writer model limits concurrency, and a real
multi-user deployment would outgrow it. That deployment does not exist yet, and
adding auth is its precondition anyway, so the limit is not binding now.

**Evidence.** The whole test suite runs against SQLite with no external service.

<a id="d8"></a>
## D8. SSE for live runs, not WebSockets

**Context.** A run streams progress to the browser as it executes. The browser
needs a live channel.

**Options.**

- WebSockets. Rejected: bidirectional, and the flow here is one-way from server
  to browser, so the extra machinery is unused.
- Server-Sent Events. Chosen.

**Decision.** `GET /api/runs/{id}/stream` is an SSE endpoint. It replays the
recorded events, then streams new ones off the in-memory bus, ending with an
`end` event. SSE reconnects itself and needs no special server support.

The cost: SSE is server-to-client only, so any client-to-server action during a
run is a separate REST call. That matches the design, where the only such action
is starting the run.

**Evidence.** `routers/chat.py` implements the replay-then-live stream; the
frontend consumes it in `useRunStream`.

<a id="d9"></a>
## D9. Import concrete statsmodels modules

**Context.** On Windows with App Control enabled, importing `statsmodels.tsa.api`
pulls in a DLL (`regime_switching\_kim_smoother`) the OS blocks, and the process
dies at import. The convenient import is the one that breaks the app.

**Options.**

- Import from `statsmodels.tsa.api` as the docs suggest. Rejected: it kills the
  process on the target platform.
- Import concrete modules only. Chosen.

**Decision.** The forecasting code imports concrete modules
(`statsmodels.tsa.forecasting.theta`, `statsmodels.tsa.vector_ar.var_model`, and
so on) and never the `tsa.api` aggregator.

The cost: the imports are more verbose, and a contributor who adds the
convenient import will not see it fail on a machine without App Control. This is
the trap, so it is documented in
[low-level-design.md](../3-architecture/low-level-design.md#forecasting).

**Evidence.** The constraint was found by the process dying at import on the
author's Windows machine, and it is why every forecasting import is concrete.

<a id="d10"></a>
## D10. TF-IDF for semantic recall, computed locally

**Context.** Semantic memory retrieves facts relevant to a query. The obvious
implementation is embeddings.

**Options.**

- Call an embedding API and store vectors. Rejected: it adds a network
  dependency, a per-call cost, and it breaks the offline guarantee.
- TF-IDF cosine similarity over stored facts, computed locally with
  scikit-learn. Chosen.

**Decision.** `SQLiteMemoryBackend.search` vectorises the stored facts plus the
query with TF-IDF and ranks by cosine similarity. No network, no token cost.

The cost: recall is lexical, not semantic in the embedding sense. A fact phrased
differently from the query may not surface. Acceptable, because the alternative
breaks the offline guarantee, and recall is a convenience, not a guarantee.

**Evidence.** `tests/test_memory.py` runs recall entirely offline.

---

Sections: [Index](../) · [1 Why](../1-why/) · [2 Product](../2-product/) ·
[3 Architecture](../3-architecture/) · **4 Decisions** · [5 Roadmap](../5-roadmap/) ·
[6 Art of the possible](../6-art-of-the-possible/)

In this section: [Decisions](README.md) · [The central decision](the-central-decision.md) ·
[Mechanisms](mechanisms.md) · **Platform** · [Reversals](reversals.md)
