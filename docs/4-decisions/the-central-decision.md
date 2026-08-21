# The central decision

<a id="d1"></a>
## D1. Models select, typed tools compute

**Context.** A language model asked for a statistic returns a plausible number
whether or not it computed one, and the output carries no marker separating the
two. Prompting cannot fix this, because the instruction and the failure share
the same medium. This is the whole problem; see [Why](../1-why/).

**Options.**

- Let the model compute and instruct it to be careful. Rejected: the failure and
  the instruction are the same kind of text, so the instruction cannot bind the
  failure.
- Let the model compute and check its arithmetic afterward. Rejected: you would
  need a second computation to check the first, at which point the first is
  redundant.
- Let the model only select, and have typed functions compute. Chosen.

**Decision.** An agent acts only by naming a tool and its arguments. A typed
Python function fetches the series, fits the model, or draws the chart. There is
no path from a model's text to a reported number that skips a function.

The cost: the model cannot do anything the tools do not expose. A capability the
system lacks is a tool nobody wrote yet, not a prompt away. This is a real
limit, and it is the right one, because the alternative is the invented number.

**Evidence.** The failures in
[what-goes-wrong.md](../1-why/what-goes-wrong.md) are all instances of the model
reaching past the tools: guessing a series key, inventing a chart, describing
data it never fetched. Each was closed by making the tool the only path, and
each is now pinned by a test.

<a id="d2"></a>
## D2. Tools are a JSON text protocol, not native tool APIs

**Context.** Given that agents call tools, how is a call expressed? Every major
provider now has a native function-calling API, with typed schemas and
structured responses. The obvious choice is to use them.

**Options.**

- Use each provider's native tool-use API. Rejected: five providers, five
  behaviours, five failure modes, and no way to run offline.
- Define one JSON text protocol: the model emits a single JSON object naming an
  action, and a tolerant parser reads it. Chosen.

**Decision.** A tool call is a JSON object in the model's text output:
`{"action": "tool", "tool": "...", "args": {...}}`. The parser
(`parse_action`) tolerates fences, prose, and the field-name variants different
models emit. Every provider, including a deterministic demo, drives the identical
loop.

The cost: the protocol is looser than a typed API. A model can emit malformed
JSON or an unknown field name. The parser absorbs the common variants, and a
node that repeats the same failing action three times aborts, but this tolerance
is code that a native API would not need. That is the price of provider parity.

**Evidence.** The demo provider (`llm/demo.py`) drives a full run to real charts
with no LLM at all, which is only possible because the protocol is plain text a
fixed function can produce. The tolerant parser is exercised by
`tests/test_engine.py`, which feeds it the JSON shapes different providers
produce. Anticipating the obvious objection: yes, native APIs give better
structured output, and if this were single-provider, they would win. It is not,
so parity and offline capability win instead.

---

Sections: [Index](../) · [1 Why](../1-why/) · [2 Product](../2-product/) ·
[3 Architecture](../3-architecture/) · **4 Decisions** · [5 Roadmap](../5-roadmap/) ·
[6 Art of the possible](../6-art-of-the-possible/)

In this section: [Decisions](README.md) · **The central decision** ·
[Mechanisms](mechanisms.md) · [Platform](platform.md) · [Reversals](reversals.md)
