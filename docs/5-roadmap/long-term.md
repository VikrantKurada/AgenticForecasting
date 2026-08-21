# Long term

These are bets, not plans. Each states a confidence, what it requires, and what
would tell us the bet is wrong. A bet you cannot lose is not a bet; it is a
slogan.

## A fair-value model layer

**The bet.** A forecast is more defensible when it is anchored to a fair-value
model: a stated relationship (rate differentials, oil, risk, terms of trade) that
the current level can be measured against. The GBP/INR run itself offered to
build one; the platform should be able to.

**Confidence: medium.** The modeling is standard and the tool seam already
exists. The risk is not the model; it is whether a fair-value estimate stays
traceable when it combines several series.

**Requires.** Cross-run comparison (to evaluate a fair-value model against
outcomes) and a typed fair-value tool the model calls, never a fair value the
model estimates directly. The moment the model estimates the fair value, this
stops being this product.

**Wrong if.** A fair-value tool cannot be built without the model doing
arithmetic the tool layer does not expose, or if the fair-value estimate cannot
be traced back to its inputs. Either would mean the abstraction leaks the
computation back to the model, and the bet is lost.

## Scenario analysis

**The bet.** The useful question is often conditional: "if oil is 100 and the Fed
cuts 100bps, where does this go". A scenario is a set of input overrides fed
through the same tools, producing a forecast per scenario with the same
traceability.

**Confidence: medium-low.** Conditioning a forecast on hypotheticals is a natural
extension of running a model, but the honest-uncertainty story gets harder: a
scenario's confidence band should widen to reflect that the scenario is
stipulated, not observed, and getting that right is not trivial.

**Requires.** The fair-value layer (a scenario is an override of a fair-value
input) and cross-run comparison (a scenario set is several runs compared).

**Wrong if.** The scenario forecasts cannot carry honest uncertainty, so they
read as more certain than they are. That would reproduce the original failure,
the confident number, in a new place.

## Multi-country panels

**The bet.** Many questions are comparative across countries. A panel model over
several countries' series is a standard method and a natural fit for the VAR and
nowcasting tools already present.

**Confidence: high.** This is mostly wiring more connectors and generalising the
existing multivariate tools. It is the safest bet here.

**Requires.** More of the catalog wired (the medium-term connector work), because
a panel needs the same series across many countries.

**Wrong if.** The connectors' coverage is too uneven across countries to build a
balanced panel, so the panel is dominated by whichever countries happen to have
data. That is a data problem, not a design one, but it would still sink the
feature.

## Confidence-scored routing

**The bet.** With an LLM intent classifier in place, the system can score its own
confidence in a routing decision and, when low, ask the user rather than guess.
A gate that knows when it is unsure is better than one that always commits.

**Confidence: low.** Calibrated self-confidence from a language model is an open
problem. The classifier can produce a score; whether the score means what it
says is the bet.

**Requires.** The LLM intent classifier from the [medium term](medium-term.md).

**Wrong if.** The confidence score does not correlate with actual correctness, so
the system asks when it is sure and commits when it is not. If it cannot be
calibrated, it is worse than the keyword gate it replaces, and we keep the
keyword gate.

---

Sections: [Index](../) · [1 Why](../1-why/) · [2 Product](../2-product/) ·
[3 Architecture](../3-architecture/) · [4 Decisions](../4-decisions/) ·
**5 Roadmap** · [6 Art of the possible](../6-art-of-the-possible/)

In this section: [Roadmap](README.md) · [Medium term](medium-term.md) · **Long term**
