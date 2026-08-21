# Mechanisms

The small decisions that make an agent recover instead of fail. Most were made
after watching a real failure in [what-goes-wrong.md](../1-why/what-goes-wrong.md),
which is why each has an incident behind it.

<a id="d3"></a>
## D3. Tool errors name the valid options

**Context.** A chart builder guessed eight series keys in a row and gave up,
because the tool error was a bare `KeyError` naming the key it had guessed, not
the keys that existed.

**Options.**

- Leave the error bare and expect the model to guess better. Rejected by the
  evidence: it guessed eight times.
- Make every tool error name the valid options. Chosen.

**Decision.** A tool that fails on a lookup names what would have worked:
`build_chart` and `run_model` list the available series keys and result indices;
connectors name the id format. The error text is part of the tool's contract.

The cost: error construction is more code, and the error text has to be kept
truthful as the tool changes. Cheap next to the failure it prevents.

**Evidence.** In the same run, `run_model` recovered in one step from the same
class of mistake because its error already named the keys, while `build_chart`
did not. Same model, same run, opposite outcome, differing only in the error
text. Pinned by `tests/test_chart_recovery.py`.

<a id="d4"></a>
## D4. Live run state is injected into every prompt

**Context.** An agent could not see which series key a prior node had stored, so
it guessed. The information existed; it just was not in the prompt.

**Options.**

- Rely on dependency outputs being passed between nodes. Rejected: the outputs
  are prose, and the exact key can be lost in the summary.
- Inject a structured run-state block into every node's prompt. Chosen.

**Decision.** `run_state_block(ctx)` lists the fetched series keys, model result
indices, and figures so far, and it is prepended to every node's assignment.

The cost: a few hundred tokens per node, every node. Worth it, because the
alternative is guessing.

**Evidence.** `tests/test_run_wiring.py` asserts the chart node's prompt contains
the exact series key and result index the fetcher and modeler produced.

<a id="d5"></a>
## D5. An invalid LLM plan falls back to a template

**Context.** A planner LLM can produce invalid JSON or an impossible DAG. A run
should degrade, not die.

**Options.**

- Fail the run on an invalid plan. Rejected: a transient formatting slip should
  not lose the whole question.
- Retry once, then fall back to a hand-written template for the question kind.
  Chosen.

**Decision.** `make_plan` validates the LLM plan, retries once with the
validation error, then instantiates a built-in template. The demo provider
deliberately returns invalid JSON so the template path is the normal demo path.

The cost: the template is generic and may be less tailored than a good LLM plan.
Acceptable, because it always runs.

**Evidence.** `tests/test_engine.py` exercises both the valid-plan and
fallback-to-template paths.

<a id="d6"></a>
## D6. A figure index is appended to every report

**Context.** The explainer is asked to cite figures inline, but it is a language
model, and it sometimes did not. A report that describes charts without pointing
at them breaks the traceability the product exists for.

**Options.**

- Trust the model to cite figures. Rejected: it is the same medium problem as
  everywhere else.
- Append a deterministic figure index to every report, regardless of what the
  model wrote. Chosen.

**Decision.** After the explainer finishes, the executor appends a numbered
figure list built from the actual artifacts, and the Report tab renders the
figures inline beneath the prose. The model is still asked to cite inline, and
usually does, but the index does not depend on it.

The cost: a little redundancy when the model already cited well. Harmless.

**Evidence.** `tests/test_run_wiring.py` asserts the report ends with a figure
index referencing every chart and table, and that the machine-readable manifest
travels with the report.

---

Sections: [Index](../) · [1 Why](../1-why/) · [2 Product](../2-product/) ·
[3 Architecture](../3-architecture/) · **4 Decisions** · [5 Roadmap](../5-roadmap/) ·
[6 Art of the possible](../6-art-of-the-possible/)

In this section: [Decisions](README.md) · [The central decision](the-central-decision.md) ·
**Mechanisms** · [Platform](platform.md) · [Reversals](reversals.md)
