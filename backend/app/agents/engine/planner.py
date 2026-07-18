"""Planner: turns a forecasting question into a run-specific workflow DAG."""
import json
import re
from graphlib import CycleError, TopologicalSorter

from pydantic import BaseModel, ValidationError

from app.agents.engine.roles import ROLES

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def parse_action(text: str) -> dict | None:
    """Extract the first JSON object from an LLM reply (tolerates fences/prose)."""
    text = text.strip()
    for candidate in (text, *(m.group(0) for m in [_JSON_BLOCK.search(text)] if m)):
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue
    return None


KIND_KEYWORDS = {
    "nowcast": ["nowcast", "current quarter", "real-time", "real time gdp", "inflation now"],
    "default_risk": ["default", "sovereign risk", "credit rating", "downgrade", "debt crisis"],
    "yield_curve": ["yield", "interest rate", "treasury", "bond", "curve", "policy rate"],
    "geopolitical": ["geopolitic", "supply chain", "sanction", "conflict", "war", "trade route",
                     "shipping", "disruption", "fdi"],
}


def classify_kind(question: str) -> str:
    q = question.lower()
    for kind, words in KIND_KEYWORDS.items():
        if any(w in q for w in words):
            return kind
    return "generic"


class NodeModel(BaseModel):
    id: str
    role: str
    instructions: str
    depends_on: list[str] = []


class PlanModel(BaseModel):
    kind: str
    nodes: list[NodeModel]


def validate_plan(raw: dict) -> dict:
    plan = PlanModel(**raw)
    if not plan.nodes:
        raise ValueError("Plan has no nodes")
    ids = [n.id for n in plan.nodes]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate node ids")
    for node in plan.nodes:
        if node.role not in ROLES:
            raise ValueError(f"Unknown role '{node.role}'. Known: {sorted(ROLES)}")
        for dep in node.depends_on:
            if dep not in ids:
                raise ValueError(f"Node '{node.id}' depends on unknown node '{dep}'")
    graph = {n.id: set(n.depends_on) for n in plan.nodes}
    try:
        list(TopologicalSorter(graph).static_order())
    except CycleError:
        raise ValueError("Plan DAG contains a cycle")
    return plan.model_dump()


def _template(kind: str, question: str) -> dict:
    fetch_note = {
        "nowcast": "monthly high-frequency indicators plus the quarterly target series",
        "default_risk": "debt/GDP, external debt, reserves, growth and fiscal series for the country",
        "yield_curve": "government bond yields across maturities plus the policy rate",
        "geopolitical": "trade, FDI, shipping-sensitive and commodity series for the affected economies",
        "generic": "the most relevant series for the question",
    }[kind]
    model_note = {
        "nowcast": "bridge_nowcast with monthly indicators (or arima if only one series)",
        "default_risk": "arima/var on fiscal trajectories; discuss default-risk drivers explicitly",
        "yield_curve": "fit_yield_curve on the latest curve plus arima on key tenors",
        "geopolitical": "var across trade/FDI series to trace spillovers",
        "generic": "the best-fitting of arima/ets/var per list_models",
    }[kind]
    nodes = [
        {"id": "scout", "role": "data_scout", "depends_on": [],
         "instructions": f"Question: {question}\nIdentify {fetch_note}. Name exact sources and series ids."},
        {"id": "fetch", "role": "data_fetcher", "depends_on": ["scout"],
         "instructions": "Fetch every series the scout recommended. Report stored series_keys."},
        {"id": "model", "role": "modeler", "depends_on": ["fetch"],
         "instructions": f"Use {model_note}. Also run a second complementary model "
                         "(ensemble or montecarlo) for comparison. Report forecasts "
                         "with result_index values."},
        {"id": "validate", "role": "validator", "depends_on": ["model"],
         "instructions": "Assess the model choices and backtests. Flag weak spots."},
        {"id": "charts", "role": "chart_builder", "depends_on": ["model"],
         "instructions": "Build the full chart set: fan chart, model comparison, "
                         "backtest, decomposition, distribution of changes, indicator "
                         "panel/heatmap if several series exist, and a data table."},
        {"id": "explain", "role": "explainer", "depends_on": ["validate", "charts"],
         "instructions": f"Write the final report answering: {question}"},
    ]
    return {"kind": kind, "nodes": nodes, "metadata": {"source": "template"}}


PLANNER_SYSTEM = """You are the planning agent of an economic forecasting system.
Design a workflow DAG of specialist agents to answer the user's forecasting question.

Available roles:
{roles}

Respond with JSON only:
{{"kind": "<nowcast|default_risk|yield_curve|geopolitical|generic>",
  "nodes": [{{"id": "<short id>", "role": "<role>", "instructions": "<specific instructions>",
             "depends_on": ["<ids>"]}}]}}

Rules: 3-7 nodes; the DAG must be acyclic; every plan ends with an explainer node;
include a chart_builder node; instructions must be concrete (name indicators, sources,
models, horizons where possible)."""


def make_plan(llm, question: str, memory, project_id: str | None) -> dict:
    kind_guess = classify_kind(question)
    roles_desc = "\n".join(f"- {r.name}: {r.description}" for r in ROLES.values())
    context_bits = []
    for proc in memory.procedures_for(kind_guess, project_id=project_id):
        context_bits.append(f"A previous successful plan for this kind of question:\n{proc.content[:1500]}")
    for episode in memory.recent_episodes(project_id, limit=2) if project_id else []:
        context_bits.append(f"Recent episode: {episode.content[:500]}")
    prompt = f"Question: {question}\nLikely kind: {kind_guess}\n" + "\n\n".join(context_bits)

    system = PLANNER_SYSTEM.format(roles=roles_desc)
    messages = [{"role": "user", "content": prompt}]
    for _attempt in range(2):
        try:
            resp = llm.complete(
                system, messages, project_id=project_id, agent_role="planner", json_mode=True
            )
        except Exception:
            break
        raw = parse_action(resp.text)
        if raw is None:
            messages.append({"role": "assistant", "content": resp.text})
            messages.append({"role": "user", "content": "That was not valid JSON. Respond with the JSON plan only."})
            continue
        try:
            plan = validate_plan(raw)
            plan["metadata"] = {"source": "llm"}
            return plan
        except (ValidationError, ValueError) as exc:
            messages.append({"role": "assistant", "content": resp.text})
            messages.append({"role": "user", "content": f"Invalid plan ({exc}). Fix it and respond with JSON only."})
    return _template(kind_guess, question)
