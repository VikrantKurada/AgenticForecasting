# Medium term

The next work. Each theme states why it is next, what ships, what it depends on,
and a done condition that can fail. A roadmap item without a falsifiable done
condition is a wish.

## Wire more of the catalog

**Why now.** The catalog lists 45 sources; 11 are wired. Every unwired source is
a key field in Settings that accepts a key and then does nothing, which is a
promise the UI makes and the backend does not keep.

**What ships.** Connectors for the highest-value unwired sources (the equities
and fixed-income providers already in the catalog), each satisfying the
`Connector` protocol and registered in `connectors/registry.py`.

**Depends on.** Nothing new; the connector seam already exists. See
[integration-patterns.md](../3-architecture/integration-patterns.md#instance-data-connectors).

**Done when.** A key entered in Settings for a newly wired source lets an agent
fetch a real series from it, and the source's search returns an empty list for a
nonsense query (the honest-absence test from
[Reversals](../4-decisions/reversals.md#d11)).

**Careful about.** Each new source has its own id format and search quality. The
work is not the HTTP call; it is the id-format error message and the empty-match
behaviour, because the caller is an agent.

## Cross-run comparison

**Why now.** A chat already holds multiple runs, and the Steps tab can rerun one.
The obvious next question is "how does this run compare to the last one", and
there is no way to ask it.

**What ships.** A view that puts two runs' forecasts, backtests, and figures side
by side, keyed off the existing per-chat run list (`GET /api/chats/{id}/runs`).

**Depends on.** The run and artifact storage that already exists.

**Done when.** A user can select two completed runs in a chat and see their
headline forecasts and backtest scores in one view, with each number still
traceable to its own run's trace.

**Careful about.** Two runs may forecast different series or horizons. The
comparison has to refuse or clearly label a comparison that is not
like-for-like, rather than putting unrelated numbers next to each other.

## An LLM intent classifier

**Why now.** The keyword intent gate (see
[Reversals](../4-decisions/reversals.md#d13)) will miss unusual phrasings. It is
the load-bearing gate: a data question that misses it gets a tool-less answer.

**What ships.** A small classifier call that runs only when the keyword gate is
uncertain, deciding between run, follow-up, and smalltalk, with the keyword gate
as the fast path and the fallback.

**Depends on.** The provider chain that already exists; the classifier is just
another `complete` call.

**Done when.** A held-out set of phrasings that the keyword gate misclassifies is
routed correctly, and the classifier adds no model call to messages the keyword
gate already handles confidently.

**Careful about.** A classifier on every message adds latency and cost and a new
failure mode. It must be the uncertain-case path, not the default, or it becomes
the thing that makes every message slow.

## One-command install

**Why now.** The install is a multi-line pip command and an npm install. The
value of the project is the traceable pipeline, and the pipeline should be
reachable without assembling the environment by hand.

**What ships.** A packaged install (a script or a container) that brings up
backend and frontend with one command, plus a pinned dependency set so the pip
line in the README stops drifting.

**Depends on.** Nothing; this is a leaf. Nothing else on the roadmap needs it,
but adoption does.

**Done when.** A new user runs one command and reaches a working chat that can
complete a demo run, with no manual environment steps.

**Careful about.** The backend has a Windows-specific constraint (the
statsmodels import in [Platform](../4-decisions/platform.md#d9)). A package that
hides the environment must not hide that, or it will fail confusingly on the
next platform.

---

Sections: [Index](../) · [1 Why](../1-why/) · [2 Product](../2-product/) ·
[3 Architecture](../3-architecture/) · [4 Decisions](../4-decisions/) ·
**5 Roadmap** · [6 Art of the possible](../6-art-of-the-possible/)

In this section: [Roadmap](README.md) · **Medium term** · [Long term](long-term.md)
