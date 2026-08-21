# Journeys

Four sessions, each a full path through the product. The third is a refusal,
because a product that declines to do something, usefully, teaches more than
three successes.

## 1. The analyst nowcasts GDP

She opens a project, starts a chat, and asks: "Nowcast US GDP growth for the
current quarter." The message classifies as a forecast request, a run starts,
and its id comes back immediately. The chat shows live progress as the run
streams over SSE.

The planner produces a `nowcast` DAG: scout, fetch, model, validate, charts,
explain. She watches the scout name the series, the fetcher pull them from
FRED and World Bank, the modeler run ARIMA and a Monte Carlo bootstrap, the
chart builder produce a fan chart and a backtest comparison.

When it finishes she opens the output panel. **Report** gives the headline with
its uncertainty band and cites Figure 1 and Figure 2 inline. **Charts** shows
the fan chart. **Method** tells her the ARIMA order was chosen by AIC and that
it beat the naive baseline by a stated RMSE margin. She trusts the number
because she can see where it came from.

What she needed: a forecast with visible working. What made it possible: the
model backtests against a naive baseline, and the Method artifact is built from
the real run, not boilerplate.

## 2. The analyst asks what already happened

Different question: "How has UK Sterling and Indian INR exchange rate changed
over the last 20 years?" This is retrospective, so it classifies as a data
question and the planner builds a `history` plan: scout, fetch, charts, explain,
with no modeling step. Forecasting a question about the past would be inventing
an answer nobody asked for.

The fetcher pulls `EXINUS` (Indian rupee to USD) and `DEXUSUK` (USD to GBP) from
FRED. The chart builder produces an indicator panel, a decomposition, a
distribution of changes, a correlation heatmap, and a data table. The report
describes what the fetched data actually shows, quoting dated values, and cites
every figure. No matplotlib code, no essay from memory.

What she needed: the real series, charted, over the real period. What made it
possible: the intent gate routes retrospective questions to a run, and the
history plan skips the modeler. This is the exact case that
[used to fail](../1-why/what-goes-wrong.md#cluster-2-it-invents-the-response-instead-of-doing-the-work).

## 3. The refusal: a chart of data that was never fetched

An agent, mid-run, asks `build_chart` to draw a fan chart of a series it thinks
is called `uk_unemployment_rate`. That key does not exist. The tool refuses, and
the refusal is the useful part:

```
build_chart {"kind":"fan","series_key":"uk_unemployment_rate",...}
  -> "No fetched series under key 'uk_unemployment_rate'.
      Available series_keys: ['fred:AURUKM']. Use one of these exact keys."
```

The agent does not get a chart of nothing. It gets told which keys exist, and on
its next call it uses `fred:AURUKM` and the chart appears. If it had instead run
out of iterations, the executor would have warned it two steps earlier to stop
exploring and act.

This is the product declining to do the wrong thing and making the decline
informative. The alternative, a chart drawn against an empty or invented series,
is precisely the failure the whole design exists to prevent. What made the good
outcome possible: the tool error names the valid options, and the run state is
in the prompt.

## 4. The engineer reruns a step with an edit

An engineer disagrees with how the modeler chose its models. He opens the
**Steps** tab, which shows the run's DAG: each node, its role, what it depends
on, the tools it called, and its output. He edits the modeler node's instruction
to force a specific model, and clicks "Rerun with edits".

A new run starts from the edited plan, skipping the planner, so it reproduces
exactly the workflow he asked for. It streams live like any other run, and lands
in the same six-tab panel. The original run is untouched; the chat now has two.

What he needed: to change one step without rebuilding the question. What made it
possible: the plan is stored as data, and `rerun` replays it with the edit.

## What each needed

| Person | Needed | Made possible by |
|---|---|---|
| Analyst (nowcast) | A forecast with visible working | Backtest against baseline; Method from the real run |
| Analyst (history) | Real series charted over the real period | Intent gate routes to a run; history plan skips modeling |
| An agent (refused) | To not draw a chart of nothing | Tool errors name valid keys; run state in the prompt |
| Engineer | To rerun one edited step | The plan is stored data; `rerun` replays it |

---

Sections: [Index](../) · [1 Why](../1-why/) · **2 Product** ·
[3 Architecture](../3-architecture/) · [4 Decisions](../4-decisions/) ·
[5 Roadmap](../5-roadmap/) · [6 Art of the possible](../6-art-of-the-possible/)

In this section: [Product](README.md) · [PRD](prd.md) ·
[Capabilities](capabilities.md) · **Journeys**
