# What goes wrong

Real incidents from this project's own run history, grouped into the three
clusters the [section landing page](README.md) names. Each was found by looking
at the running system (the SQLite database at `backend/data/app.db` holds every
run, artifact, and event), not by a unit test. The unit tests came after, to
keep each one fixed.

The probe throughout is a query against the live database:

```bash
cd backend
./.venv/Scripts/python.exe -c "import sqlite3; c=sqlite3.connect('data/app.db'); ..."
```

---

## Cluster 1: it cannot see prior state, so it guesses

**Incident.** A user asked to forecast UK unemployment for the next two years.
The run completed. It produced a report and a data table and zero charts. The
Charts tab was empty for a question that was entirely about a time series.

**Probe.** Listing the chart builder's tool calls for that run showed the same
call failing eight times with a different guess each time:

```
build_chart {"kind":"fan","series_key":"uk_unemployment_rate",...} -> KeyError: 'uk_unemployment_rate'
build_chart {"kind":"fan","series_key":"unemployment_rate",...}    -> KeyError: 'unemployment_rate'
build_chart {"kind":"fan","series_key":"UNRATE",...}               -> KeyError: 'UNRATE'
build_chart {"kind":"fan","series_key":"LRHUTTTTGBM156S",...}      -> KeyError: 'LRHUTTTTGBM156S'
build_chart {"kind":"fan","series_key":"MGSX",...}                 -> KeyError: 'MGSX'
...
node_finished  {"output": "KeyError: 'MGSX'"}
```

The series had been fetched and stored under the key `fred:AURUKM`. The chart
builder never saw that key, so it guessed, and every guess was a bare
`KeyError` that told it nothing.

**The tell.** In the same run, the modeler hit the same class of mistake and
recovered on its next call, because `run_model` fails differently:

```
run_model {"series_key":"unemployment_rate_uk",...}
  -> KeyError: "No fetched series under key 'unemployment_rate_uk'.
     Available series_keys: ['fred:AURUKM', 'fred:GBRCPIALLMINMEI', ...].
     Call fetch_series first."
run_model {"series_key":"fred:AURUKM",...}  -> ok
```

Same model, same run, same kind of error. One error named the valid keys and the
agent recovered in one step. The other did not and the agent burned its whole
eight-iteration budget. The difference was entirely in the error text.

**Remedy.** Two mechanisms, both in
[`agents/tools/charts.py`](../../backend/app/agents/tools/charts.py) and
[`agents/engine/executor.py`](../../backend/app/agents/engine/executor.py):

1. `build_chart` now fails like `run_model`: the error names the available
   series keys and result indices, and points at the chart kinds that need no
   model when none has run.
2. `run_state_block()` injects the live run state (fetched series keys, model
   result indices, existing figures) into every node's prompt, so an agent does
   not have to guess in the first place.

Verified end to end after the fix: the same class of question now fetches real
series and produces a full chart set. Pinned by `tests/test_chart_recovery.py`
and `tests/test_run_wiring.py`.

---

## Cluster 2: it invents the response instead of doing the work

**Incident.** A user asked, "How has UK Sterling and Indian INR exchange rate
changed over the last 20 years?" The reply was fluent and useless: a paragraph
saying it could not display charts in a chat interface, followed by a block of
matplotlib to run yourself, followed by an essay on GBP/INR history from the
model's own memory. No data was fetched. No run was created.

**Probe.** The messages for that chat showed the giveaway:

```
assistant | run_id=None | I cannot generate or display actual image files ...
user      | run_id=None | Generate graphically.
assistant | run_id=None | I can't embed an actual image, but I can give you code ...
user      | run_id=None | How has UK Sterling and Indian INR exchange rate ...
```

Every message had `run_id=None` and every LLM call was tagged
`agent_role="assistant"`. The question never reached an agent. It was
classified as smalltalk and answered by a plain, tool-less language model, which
correctly reported that it, personally, cannot draw charts.

It was also self-trapping. The intent classifier only routed follow-ups to a run
if a prior run existed. No run existed, so "Generate graphically" was also
smalltalk, and so on. The user could not escape the chat-only branch by asking
more directly.

**Remedy.** In
[`agents/pipeline.py`](../../backend/app/agents/pipeline.py), the intent gate now
starts a run for an explicit chart or data request and for a retrospective
question ("how has X changed", "compare X since 2000"), even mid-conversation. A
new `history` plan kind (in
[`agents/engine/planner.py`](../../backend/app/agents/engine/planner.py)) fetches
and charts the real series without inventing a forecast the user did not ask
for. Verified against the exact reported question: the run now fetches `EXINUS`
and `DEXUSUK` from FRED and produces seven charts and a data table. Pinned by
`tests/test_intent_routing.py`.

---

## Cluster 3: a source returns filler instead of nothing

**Incident.** After the routing fix, the GBP/INR question started a run but still
produced no charts. This time the chart error, now informative, said why:

```
build_chart {...} -> KeyError: "No fetched series under key 'PA.NUS.FCRF'.
   Available series_keys: ['<none fetched yet>']. ..."
```

Nothing had been fetched. The data fetcher had made eight `search_series` calls
and never once called `fetch_series`.

**Probe.** The searches showed why it never committed to a series:

```
search_series {"query":"GBP INR exchange rate","source":"worldbank"}
  -> results: [ {"series_id":"FR.INR.RINR","title":"Real interest rate (%)"},
                {"series_id":"NY.GDP.MKTP.KD.ZG","title":"GDP growth (annual %)"}, ... ]
```

A search for a GBP/INR exchange rate returned "Real interest rate" and "GDP
growth". Five catalog-backed connectors (World Bank, Alpha Vantage, EIA, FAOSTAT,
Treasury) answered an empty match by returning the head of their catalog. To the
agent, filler is indistinguishable from a hit, so it kept searching for something
better and never fetched anything.

**Remedy.** In the five connectors, a search with no match now returns an empty
list. `search_series` (in
[`agents/tools/data_tool.py`](../../backend/app/agents/tools/data_tool.py))
appends a note when results are empty, telling the agent to try different
keywords or fetch a known id directly rather than re-searching. The data fetcher
role was also told to fetch, not to search more than twice, and a node with two
iterations left is warned to stop exploring and act. Pinned by
`tests/test_search_honesty.py`.

An existing test had to change too: `test_all_new_connectors_have_curated_search`
had asserted that Treasury search returns hits for the word "production", which
it only ever did because of the filler. The test had been pinning the bug.

---

## The rules these add up to

1. **A tool error is the agent's only window onto what it did wrong. It must
   name the valid options.** A bare exception is a dead end for a language
   model. Compare `run_model` (recovered in one step) against the old
   `build_chart` (guessed eight times).

2. **An agent must not have to infer state it could be told.** The fix was not
   smarter guessing. It was making the run state legible: series keys, result
   indices, and figures, in every prompt.

3. **A tool must distinguish "no result" from "a result".** Returning plausible
   filler for an empty match is worse than returning nothing, because the caller
   cannot tell the two apart and acts on the filler.

4. **Correctness of the code is not sufficient. The system must be observable to
   its own agents.** Every chart builder here was correct and every unit test
   passed while the Charts tab sat empty. The failure was epistemic: the agent
   could not see the one fact it needed.

---

Sections: [Index](../) · **1 Why** · [2 Product](../2-product/) ·
[3 Architecture](../3-architecture/) · [4 Decisions](../4-decisions/) ·
[5 Roadmap](../5-roadmap/) · [6 Art of the possible](../6-art-of-the-possible/)

In this section: [Why](README.md) · **What goes wrong**
