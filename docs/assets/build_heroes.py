"""Generate every section hero for the docs, light and dark, from one definition.

Run from anywhere; writes the SVG pairs beside this file:

    python build_heroes.py

Then look at each PNG. SVG text does not wrap or elide, so an over-long line is
silently gone off the right edge. The `limit=` character counts and every
`height` below were arrived at by rendering and looking, which is the only
check that means anything. Recompute them when the text changes.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from diagram_kit import (
    MONO,
    Theme,
    arrow_right,
    band_heading,
    chip,
    line,
    open_svg,
    paragraph,
    rect,
    text_el,
    write_pair,
)

W = 1280
MARGIN = 44


# --- 1. README capability map -------------------------------------------------


def build_readme(t: Theme) -> str:
    """One wide map: a question enters, five agents act, an output panel leaves."""
    stages = [
        ("Question", "a chat message", t.series[0]),
        ("Planner", "LLM composes a DAG", t.series[6]),
        ("Agents", "scout, fetch, model,\nvalidate, chart, explain", t.series[2]),
        ("Tools", "12 typed functions\ndo the real work", t.series[1]),
        ("Output panel", "charts, data, report,\nmethod, steps, trace", t.series[3]),
    ]
    top = 132
    card_h = 118
    height = top + card_h + 150

    p = open_svg(W, height, t, title="Agentic Forecasting",
                 label="A question flows through a planned team of agents into an output panel")
    p.append(text_el(MARGIN, 54, "Agentic Forecasting", fill=t.text, size=27, weight="700"))
    p.append(text_el(
        MARGIN, 80,
        "A local, chat-driven macroeconomic forecasting platform. Models choose; typed tools compute.",
        fill=t.muted, size=14))

    n = len(stages)
    gap = 30
    card_w = (W - 2 * MARGIN - gap * (n - 1)) / n
    for i, (title, sub, accent) in enumerate(stages):
        x = MARGIN + i * (card_w + gap)
        p.append(rect(x, top, card_w, card_h, fill=t.card, stroke=t.border))
        p.append(rect(x, top, 3, card_h, fill=accent, r=1.5))
        p.append(text_el(x + 15, top + 28, title, fill=t.text, size=15, weight="600"))
        for j, ln in enumerate(sub.split("\n")):
            p.append(text_el(x + 15, top + 52 + j * 16, ln, fill=t.muted, size=11.5))
        if i < n - 1:
            p.append(arrow_right(x + card_w + 6, top + card_h / 2, gap - 12,
                                 stroke=t.faint, width=1.6))

    band_y = top + card_h + 52
    p += band_heading(t, MARGIN, band_y, "every step is a trace event", t.series[7])
    p += paragraph(
        t, MARGIN, band_y + 26,
        "The planner builds the workflow per question. Each agent is a language model with a "
        "restricted toolbelt, choosing its own actions and self-correcting from tool errors. "
        "When no provider is reachable, a deterministic demo run still produces a real forecast.",
        limit=150, size=13, leading=20)
    p.append("</svg>")
    return "\n".join(p) + "\n"


# --- 2. why: failure -> mechanism ---------------------------------------------


@dataclass(frozen=True)
class Row:
    failure: str
    detail: str
    mechanism: str
    evidence: str
    proof: str


WHY_ROWS = (
    Row(
        failure="Charts never reached the Charts tab",
        detail=("The chart builder guessed eight series keys in a row and gave up. It could "
                "not see which key the fetcher had stored."),
        mechanism="Errors name the valid options",
        evidence=("build_chart now reports the available series keys and result indices, and "
                  "every node's prompt carries the live run state."),
        proof="agents/tools/charts.py"),
    Row(
        failure="A data question never started a run",
        detail=("\"How has GBP/INR changed?\" matched no forecasting verb, fell through to "
                "tool-less chat, and was told it could not draw charts."),
        mechanism="The intent gate routes data questions",
        evidence=("Retrospective and explicit chart requests now start an agent run, and a new "
                  "history plan fetches and charts without inventing a forecast."),
        proof="agents/pipeline.py"),
    Row(
        failure="Search invented plausible results",
        detail=("A search for \"GBP/INR\" answered \"GDP growth (annual %)\". Five connectors "
                "returned catalog filler when nothing matched."),
        mechanism="No match returns nothing",
        evidence=("Connectors return an empty list on no match, and search_series says so, so "
                  "an agent stops re-searching and fetches a known id."),
        proof="connectors/worldbank.py"),
)


def build_why(t: Theme) -> str:
    row_h = 122
    gap = 16
    top = 118
    height = top + len(WHY_ROWS) * (row_h + gap) + 74

    p = open_svg(W, height, t, title="Why this exists",
                 label="Three ways this went wrong, and the mechanism that closed each")
    p.append(text_el(MARGIN, 54, "Why this exists", fill=t.text, size=27, weight="700"))
    p.append(text_el(MARGIN, 80, "Three failures found by watching the running system, and what closed each.",
                     fill=t.muted, size=14))

    left_w = 440
    right_x = MARGIN + left_w + 92
    right_w = W - MARGIN - right_x

    p += band_heading(t, MARGIN, top - 14, "the failure", t.series[7])
    p += band_heading(t, right_x, top - 14, "the mechanism", t.series[2])

    for i, row in enumerate(WHY_ROWS):
        y = top + i * (row_h + gap)
        p.append(rect(MARGIN, y, left_w, row_h, fill=t.card, stroke=t.border))
        p.append(rect(MARGIN, y, 3, row_h, fill=t.series[7], r=1.5))
        p.append(text_el(MARGIN + 16, y + 27, row.failure, fill=t.text, size=14.5, weight="600"))
        p += paragraph(t, MARGIN + 16, y + 50, row.detail, limit=56)
        p.append(arrow_right(MARGIN + left_w + 26, y + row_h / 2, 40, stroke=t.faint, width=1.6))
        p.append(rect(right_x, y, right_w, row_h, fill=t.card, stroke=t.border))
        p.append(rect(right_x, y, 3, row_h, fill=t.series[2], r=1.5))
        p.append(text_el(right_x + 16, y + 27, row.mechanism, fill=t.text, size=14.5, weight="600"))
        p.append(text_el(right_x + right_w - 16, y + 27, row.proof, fill=t.faint, size=11,
                         family=MONO, anchor="end"))
        p += paragraph(t, right_x + 16, y + 50, row.evidence, limit=72)

    p.append(line(MARGIN, height - 46, W - MARGIN, height - 46, stroke=t.border, width=1))
    p.append(text_el(MARGIN, height - 26,
                     "None is a prompt asking the model to behave. Each is code with a test that fails when it stops working.",
                     fill=t.faint, size=12.5))
    p.append("</svg>")
    return "\n".join(p) + "\n"


# --- 3. product surface -------------------------------------------------------


def build_product(t: Theme) -> str:
    tabs = [
        ("Charts", "fan, panel, backtest,\ndecomposition, heatmap"),
        ("Data", "raw observations,\nsaveable as CSV"),
        ("Report", "narrative with figures\ncited inline"),
        ("Method", "the run's real data,\nmodels, and backtest"),
        ("Steps", "the DAG, editable,\nrerunnable"),
        ("Trace", "every tool call\nand argument"),
    ]
    top = 150
    card_h = 96
    rows = 2
    cols = 3
    gap = 20
    card_w = (W - 2 * MARGIN - gap * (cols - 1)) / cols
    height = top + rows * (card_h + gap) + 40

    p = open_svg(W, height, t, title="The product surface",
                 label="A chat on the left, an output panel of six tabs on the right")
    p.append(text_el(MARGIN, 54, "One chat, one output panel", fill=t.text, size=27, weight="700"))
    p.append(text_el(MARGIN, 80,
                     "Ask a question in a project chat. The run streams live, then lands in six tabs.",
                     fill=t.muted, size=14))
    p += band_heading(t, MARGIN, top - 18, "the output panel", t.series[3])

    for i, (title, sub) in enumerate(tabs):
        r, c = divmod(i, cols)
        x = MARGIN + c * (card_w + gap)
        y = top + r * (card_h + gap)
        accent = t.series[i % len(t.series)]
        p.append(rect(x, y, card_w, card_h, fill=t.card, stroke=t.border))
        p.append(rect(x, y, 3, card_h, fill=accent, r=1.5))
        p.append(text_el(x + 16, y + 28, title, fill=t.text, size=15, weight="600"))
        for j, ln in enumerate(sub.split("\n")):
            p.append(text_el(x + 16, y + 52 + j * 17, ln, fill=t.muted, size=12))
    p.append("</svg>")
    return "\n".join(p) + "\n"


# --- 4. architecture: layers --------------------------------------------------


def build_architecture(t: Theme) -> str:
    layers = [
        ("Frontend", "React + Vite + Plotly. Chat, live run stream, resizable output panel.", t.series[0]),
        ("API", "FastAPI, 40 endpoints across 10 routers. SSE for live runs.", t.series[6]),
        ("Engine", "Planner builds a DAG. Executor runs it, streaming every step.", t.series[2]),
        ("Tools", "12 typed functions: search, fetch, run_model, build_chart, memory.", t.series[1]),
        ("Providers", "Connectors, forecasting, LLM chain, memory. Each swappable behind a seam.", t.series[3]),
    ]
    top = 120
    row_h = 62
    gap = 14
    height = top + len(layers) * (row_h + gap) + 40

    p = open_svg(W, height, t, title="Architecture",
                 label="Five layers from the browser down to data sources and models")
    p.append(text_el(MARGIN, 54, "Five layers, one rule per seam", fill=t.text, size=27, weight="700"))
    p.append(text_el(MARGIN, 80,
                     "Each layer talks only to the one below it, through an interface it does not own.",
                     fill=t.muted, size=14))

    for i, (title, sub, accent) in enumerate(layers):
        y = top + i * (row_h + gap)
        p.append(rect(MARGIN, y, W - 2 * MARGIN, row_h, fill=t.card, stroke=t.border))
        p.append(rect(MARGIN, y, 3, row_h, fill=accent, r=1.5))
        p.append(text_el(MARGIN + 18, y + row_h / 2 + 5, title, fill=t.text, size=16, weight="700"))
        p.append(text_el(MARGIN + 200, y + row_h / 2 + 5, sub, fill=t.muted, size=13))
    p.append("</svg>")
    return "\n".join(p) + "\n"


# --- 5. decisions: the central choice -----------------------------------------


def build_decisions(t: Theme) -> str:
    top = 128
    card_h = 150
    gap = 24
    cols = 3
    card_w = (W - 2 * MARGIN - gap * (cols - 1)) / cols
    height = top + card_h + 60

    options = [
        ("A", "The model writes the numbers", t.series[7],
         ["Ask an LLM for a beta; it", "returns a plausible figure", "without touching data.",
          "", "Rejected: it invents", "statistics."], False),
        ("B", "Native tool-use APIs", t.series[3],
         ["Let each provider's own", "function-calling drive the", "loop.",
          "", "Rejected: five providers,", "five behaviours."], False),
        ("C", "JSON text protocol + typed tools", t.series[2],
         ["The model emits one JSON", "action. A typed function", "does the arithmetic.",
          "", "Chosen: every provider", "behaves identically."], True),
    ]

    p = open_svg(W, height, t, title="The central decision",
                 label="Three ways the model could touch numbers; the third was chosen")
    p.append(text_el(MARGIN, 54, "How does the model touch numbers?", fill=t.text, size=27, weight="700"))
    p.append(text_el(MARGIN, 80,
                     "The decision the whole system turns on. The model selects; it never computes.",
                     fill=t.muted, size=14))

    for i, (tag, title, accent, lines, chosen) in enumerate(options):
        x = MARGIN + i * (card_w + gap)
        border = accent if chosen else t.border
        p.append(rect(x, top, card_w, card_h, fill=t.card, stroke=border))
        p.append(rect(x, top, 3, card_h, fill=accent, r=1.5))
        p.append(text_el(x + 16, top + 30, tag, fill=accent, size=17, weight="800"))
        p.append(text_el(x + 44, top + 30, title, fill=t.text, size=14.5, weight="600"))
        if chosen:
            p.append(text_el(x + card_w - 16, top + 30, "chosen", fill=accent, size=12,
                             weight="700", anchor="end"))
        for j, ln in enumerate(lines):
            p.append(text_el(x + 16, top + 58 + j * 15.5, ln, fill=t.muted, size=12))
    p.append("</svg>")
    return "\n".join(p) + "\n"


# --- 6. roadmap horizons ------------------------------------------------------


def build_roadmap(t: Theme) -> str:
    horizons = [
        ("Now", "shipped", t.series[2],
         ["Per-question agent DAGs", "11 live data connectors", "8 models, 9 chart kinds",
          "Editable, rerunnable steps"]),
        ("Medium", "next", t.series[3],
         ["More connectors from the", "45-source catalog", "Cross-run comparison",
          "Scheduled re-runs"]),
        ("Long", "bets", t.series[6],
         ["A fair-value model layer", "Scenario analysis", "Multi-country panels",
          "Confidence-scored routing"]),
    ]
    top = 128
    card_h = 168
    gap = 24
    cols = 3
    card_w = (W - 2 * MARGIN - gap * (cols - 1)) / cols
    height = top + card_h + 50

    p = open_svg(W, height, t, title="Roadmap",
                 label="Three horizons: what is shipped, what is next, what is a bet")
    p.append(text_el(MARGIN, 54, "Three horizons", fill=t.text, size=27, weight="700"))
    p.append(text_el(MARGIN, 80,
                     "The rule: a later version of this product, not a different product.",
                     fill=t.muted, size=14))

    for i, (title, badge, accent, items) in enumerate(horizons):
        x = MARGIN + i * (card_w + gap)
        p.append(rect(x, top, card_w, card_h, fill=t.card, stroke=t.border))
        p.append(rect(x, top, 3, card_h, fill=accent, r=1.5))
        p.append(text_el(x + 16, top + 30, title, fill=t.text, size=16, weight="700"))
        p.append(text_el(x + card_w - 16, top + 30, badge, fill=accent, size=12,
                         weight="700", anchor="end"))
        for j, item in enumerate(items):
            p.append(text_el(x + 16, top + 60 + j * 24, "- " + item, fill=t.muted, size=12.5))
        if i < cols - 1:
            p.append(arrow_right(x + card_w + 4, top + card_h / 2, gap - 8, stroke=t.faint, width=1.6))
    p.append("</svg>")
    return "\n".join(p) + "\n"


# --- 7. capability ladder -----------------------------------------------------


def build_ladder(t: Theme) -> str:
    rungs = [
        ("Typed tools that compute", "The floor. A function, not a token, does the arithmetic."),
        ("Errors that teach", "A failed call names the valid options, so the agent recovers."),
        ("Live run state in every prompt", "No agent has to guess what a prior step produced."),
        ("A replayable, editable DAG", "The workflow is data, so a person can rerun or change it."),
        ("Scenarios and fair-value models", "Because the tool layer is typed, new tools slot in."),
    ]
    top = 116
    rung_h = 60
    gap = 12
    height = top + len(rungs) * (rung_h + gap) + 36

    p = open_svg(W, height, t, title="The art of the possible",
                 label="A ladder where each rung is reachable only because of the one below")
    p.append(text_el(MARGIN, 54, "Each rung stands on the one below", fill=t.text, size=27, weight="700"))
    p.append(text_el(MARGIN, 80,
                     "Every claim names what makes it possible, and the answer already exists.",
                     fill=t.muted, size=14))

    n = len(rungs)
    for i, (title, sub) in enumerate(rungs):
        # draw from the bottom up so the base rung sits lowest
        y = top + (n - 1 - i) * (rung_h + gap)
        accent = t.series[i % len(t.series)]
        indent = i * 40
        p.append(rect(MARGIN + indent, y, W - 2 * MARGIN - indent, rung_h, fill=t.card, stroke=t.border))
        p.append(rect(MARGIN + indent, y, 3, rung_h, fill=accent, r=1.5))
        p.append(text_el(MARGIN + indent + 16, y + 25, title, fill=t.text, size=14.5, weight="600"))
        p.append(text_el(MARGIN + indent + 16, y + 45, sub, fill=t.muted, size=12))
    p.append("</svg>")
    return "\n".join(p) + "\n"


HEROES = {
    "hero-readme": build_readme,
    "hero-why": build_why,
    "hero-product": build_product,
    "hero-architecture": build_architecture,
    "hero-decisions": build_decisions,
    "hero-roadmap": build_roadmap,
    "hero-ladder": build_ladder,
}


def main() -> None:
    here = Path(__file__).resolve().parent
    for stem, build in HEROES.items():
        for path in write_pair(here, stem, build):
            print(f"wrote {path.name}")


if __name__ == "__main__":
    main()
