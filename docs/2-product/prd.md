# Product requirements

## Summary

A local, chat-driven forecasting platform where a team of agents answers a
macroeconomic question by fetching real data, running standard models, and
explaining the result, such that every number is traceable to a tool call. The
audience is a technical user who wants a forecast they can audit, not a chatbot
answer they have to trust.

## The problem, and what makes it hard

The problem is stated in full in [Why](../1-why/): a language model produces
numbers that look correct whether or not it computed them, and prompting cannot
fix it because the instruction and the failure share a medium.

What makes it hard, specifically:

- **The failure is intermittent.** A system that is right most of the time is
  harder to trust than one that is wrong all the time, because the spot check
  passes.
- **The agent's only feedback is text.** An agent recovers from a mistake only
  if the error tells it what a valid input would have been. This shapes every
  tool's failure path, not just its success path.
- **Real data sources are inconsistent.** Different id formats, different search
  quality, different coverage. World Bank ids are `COUNTRY:INDICATOR`; FRED ids
  are opaque codes. A tool layer has to normalise this without hiding it.

## Goals

| Goal | Why |
|---|---|
| Every reported number traces to a tool result | The core value; an untraceable forecast is a guess |
| Standard models, honestly backtested | A method that cannot beat a naive baseline carries no signal, and the user should see that |
| Works offline with no keys | The value is the traceable pipeline; it should be inspectable with nothing installed |
| Every step is a recorded event | Auditing a run after the fact requires the trace to exist |
| The workflow is inspectable and replayable | A user who disagrees with a step should be able to edit and rerun it |

## Non-goals

| Non-goal | Why |
|---|---|
| Beating dedicated forecasting research | The value is traceability and breadth, not a novel model |
| Real-time or intraday data | The domain is macro series that update daily at most |
| Investment advice | Legally and ethically out of scope; forecasts are estimates |
| Multi-user accounts and auth | Local single-user tool; no server deployment yet |
| A provider-agnostic native tool API | Deliberately rejected; see [Decisions](../4-decisions/) |

## Users

**The analyst.** Primary job: get a defensible forecast for a specific series
and be able to show the working. Cares most about the Method and Trace tabs.

**The engineer.** Primary job: extend the system with a new connector, model, or
chart, without breaking the traceability guarantee. Cares most about the tool
layer and the seams in [Architecture](../3-architecture/).

**The evaluator.** Primary job: decide whether to trust the thing at all.
Reaches for the failure cases first, which is why [journeys.md](journeys.md)
includes a refusal.

## Functional requirements

<a id="fr-intent"></a>
### Intent and routing

| ID | Requirement | Acceptance (what verifies it) |
|---|---|---|
| FR-1 | An explicit chart or data request starts an agent run | `tests/test_intent_routing.py` asserts `forecast_request` for chart/data phrasings |
| FR-2 | A retrospective question ("how has X changed") starts a run and does not forecast | `test_retrospective_questions_classify_as_history`, `test_history_template_skips_modeling_and_still_charts` |
| FR-3 | A follow-up about a prior run is answered without a new run | `tests/test_chat_pipeline.py` |
| FR-4 | With no reachable provider, a run still completes | `tests/test_demo_llm.py` runs a full workflow on the demo provider |

### Planning and execution

| ID | Requirement | Acceptance |
|---|---|---|
| FR-5 | A question is turned into a valid acyclic DAG of agent nodes | `tests/test_engine.py` validates plan structure and rejects cycles |
| FR-6 | An invalid LLM plan falls back to a built-in template | `tests/test_engine.py` |
| FR-7 | Nodes run in topological order; independent nodes may run concurrently | `tests/test_engine.py`, executor uses a thread pool |
| FR-8 | A node that repeats the same failing call three times aborts | `MAX_IDENTICAL_ERRORS` in the executor |

### Tools and data

| ID | Requirement | Acceptance |
|---|---|---|
| FR-9 | A series can be searched and fetched from 11 connectors | `tests/test_connectors*.py` |
| FR-10 | A search with no match returns an empty list | `tests/test_search_honesty.py` |
| FR-11 | A model runs and returns a forecast plus a backtest | `tests/test_forecasting_basics.py`, `tests/test_models_suite.py` |
| FR-12 | A chart of an unfetched series fails with the available keys | `tests/test_chart_recovery.py` |
| FR-13 | Fetched responses cache for 24 hours | `CachedConnector`, `tests/test_connectors.py` |

### Output and traceability

| ID | Requirement | Acceptance |
|---|---|---|
| FR-14 | Charts and tables are numbered as figures; the report cites them | `tests/test_run_wiring.py` |
| FR-15 | A Method artifact documents data, models, and backtest from the real run | `tests/test_methodology.py` |
| FR-16 | Every tool call is a recorded event with trace and span ids | `tests/test_telemetry.py`, the events table |
| FR-17 | A run's plan can be replayed, optionally with edited instructions | `tests/test_orchestrator.py` |

### Projects, chats, files

| ID | Requirement | Acceptance |
|---|---|---|
| FR-18 | Projects and chats can be created, renamed, and deleted | `tests/test_projects_api.py`, `tests/test_chat_pipeline.py` |
| FR-19 | A chat auto-names from its first question | `test_first_message_auto_names_chat` |
| FR-20 | A CSV/Excel file can be attached and used as a data source | `tests/test_uploads.py`, `tests/test_files.py` |
| FR-21 | A chat or project can be exported to a folder | `tests/test_export.py` |

## Non-functional requirements

| ID | Requirement | Note |
|---|---|---|
| NFR-1 | Runs offline | Demo provider and cached data; the whole test suite is offline |
| NFR-2 | No secret in the repo | Keys in SQLite (`app_settings`) or `.env`, both gitignored |
| NFR-3 | Live progress under one second per event | SSE bus publishes each event as it is recorded |
| NFR-4 | Connector failures are retried and surfaced, not swallowed | `request_json` retries 3 times, then raises `ConnectorError` |
| NFR-5 | Provider failures fall through the chain | `LLMRegistry.complete` walks the chain, records each error |

## Success metrics

| Metric | Where it is measured |
|---|---|
| Fraction of reported numbers traceable to a tool result | By construction; a break is a bug (FR-14, the Trace tab) |
| Models that beat the naive baseline | Backtest RMSE in each run's Method tab |
| Tokens and estimated cost per run | `token_usage` table, the Usage dashboard |
| CPU/RAM/GPU during a run | `resource_samples` table, sampled every 2 seconds |

## Release criteria

- [x] 197 backend tests pass offline
- [x] 7 frontend store tests pass
- [x] A full run works with no keys (demo provider)
- [x] A full run works with a real provider (verified against the GBP/INR case)
- [x] Charts appear for a time-series question and are cited in the report
- [ ] A packaged, one-command install (not yet; see [Roadmap](../5-roadmap/))
- [ ] A licence file (not yet)

## Risks

| Risk | Position |
|---|---|
| The intent classifier is keyword-based and will miss phrasings | Accepted for now; the fix belongs in `classify_intent`, and an LLM classifier is a roadmap item. It is better to occasionally route a chat to a run than to trap a data question in chat |
| A connector's search quality is poor | Mitigated by honest empty results plus the agent being told to fetch a known id; not fully solved |
| The demo provider's output is fixed, so demo runs all look alike | Accepted; the demo exists to prove the pipeline, not to vary |
| No auth means the local DB is readable by anything on the machine | Accepted for a local single-user tool; a real deployment would need auth first |

---

Sections: [Index](../) · [1 Why](../1-why/) · **2 Product** ·
[3 Architecture](../3-architecture/) · [4 Decisions](../4-decisions/) ·
[5 Roadmap](../5-roadmap/) · [6 Art of the possible](../6-art-of-the-possible/)

In this section: [Product](README.md) · **PRD** · [Capabilities](capabilities.md) ·
[Journeys](journeys.md)
