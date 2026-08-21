# Reversals

What was undone, and what was designed and deliberately not built. A decision log
with no reversals is a log nobody was honest in.

<a id="d11"></a>
## D11. Connectors returned catalog filler on no match (reversed)

**Context.** Five catalog-backed connectors (World Bank, Alpha Vantage, EIA,
FAOSTAT, Treasury) answered a search that matched nothing by returning the head
of their catalog. The intent was to always give the agent something to work
with.

**What it cost.** The opposite of the intent. An agent cannot tell filler from a
real hit, so a search for "GBP/INR" that returned "GDP growth (annual %)" led the
fetcher to keep searching for something better and never fetch anything. A run
produced no data and no charts. See
[what-goes-wrong.md](../1-why/what-goes-wrong.md#cluster-3-a-source-returns-filler-instead-of-nothing).

**Reversal.** A search with no match now returns an empty list, and
`search_series` appends a note telling the agent to try different keywords or
fetch a known id. An existing test had to be corrected too: it had asserted
Treasury search returns hits for "production", which it only did because of the
filler. The test had been pinning the bug.

**The lesson.** "Always return something" is the wrong default when the caller
acts on what it gets. Honest absence beats plausible filler.

<a id="d12"></a>
## D12. A provider-agnostic native tool API (designed, not built)

**Context.** The natural way to let agents call tools is each provider's native
function-calling API, with typed schemas and structured responses. It was
considered and not built.

**Why not.** Native APIs differ across the five providers, and none works
offline. Building on them would mean five code paths, five failure modes, and no
demo mode. The JSON text protocol (see
[the central decision](the-central-decision.md#d2)) was chosen instead, and it
is what makes the deterministic demo provider possible at all.

**What would change the call.** If the system were ever single-provider, the
native API's better structured output would win, and this reversal would reverse.
It is not single-provider, so it stands.

<a id="d13"></a>
## D13. Keyword intent classification, not an LLM (deferred)

**Context.** `classify_intent` decides whether a message starts an agent run,
answers as a follow-up, or is smalltalk. This gate is load-bearing: a data
question that misses it falls into tool-less chat and gets told the system cannot
draw charts.

**Current choice.** Keyword matching. A message with a chart or data phrasing, a
forecasting verb, or a retrospective phrasing starts a run.

**What it costs.** Keyword matching will miss unusual phrasings. The mitigation
is that the keyword sets are deliberately broad, so the gate errs toward starting
a run rather than trapping a question in chat. Over-triggering a run is cheaper
than the trap it replaced.

**Why deferred, not decided.** An LLM classifier would handle the ambiguous
cases, at the cost of a model call on every message and a new failure mode. It is
a [roadmap](../5-roadmap/) item, not a rejected option. If missed-phrasing
reports recur, the fix belongs in `classify_intent`, and then in a classifier.

---

Sections: [Index](../) · [1 Why](../1-why/) · [2 Product](../2-product/) ·
[3 Architecture](../3-architecture/) · **4 Decisions** · [5 Roadmap](../5-roadmap/) ·
[6 Art of the possible](../6-art-of-the-possible/)

In this section: [Decisions](README.md) · [The central decision](the-central-decision.md) ·
[Mechanisms](mechanisms.md) · [Platform](platform.md) · **Reversals**
