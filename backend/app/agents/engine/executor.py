"""DAG executor: runs the planned agent workflow, streaming every step as trace events."""
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from graphlib import TopologicalSorter

from app import models
from app.agents.engine.events import RunEventBus, emit
from app.agents.engine.planner import make_plan, parse_action, validate_plan
from app.agents.engine.roles import PROTOCOL, ROLES
from app.agents.engine.sampler import ResourceSampler
from app.agents.tools import ToolContext, build_toolbelt, execute_tool

logger = logging.getLogger(__name__)

MAX_TOOL_RESULT_CHARS = 6000


def _tool_docs(belt, allowed: list[str]) -> str:
    lines = []
    for name in allowed:
        spec = belt.get(name)
        if spec is None:
            continue
        props = spec.input_schema.get("properties", {})
        args = ", ".join(
            f"{k}{'' if k in spec.input_schema.get('required', []) else '?'}" for k in props
        )
        lines.append(f"- {name}({args}): {spec.description}")
    return "\n".join(lines)


MAX_IDENTICAL_ERRORS = 3


def run_state_block(ctx) -> str:
    """Describe the run's live state: fetched series, model results, artifacts.

    Without this a downstream node has to *guess* the series_key the fetcher
    stored, which is how chart building used to fail silently.
    """
    lines: list[str] = []
    if ctx.data_store:
        lines.append("Series already fetched — use these exact series_key values:")
        for key, data in ctx.data_store.items():
            obs = data.observations
            span = f"{obs[0][0]} to {obs[-1][0]}" if obs else "empty"
            lines.append(f"  - {key!r} — {data.meta.title} ({len(obs)} obs, {span})")
    else:
        lines.append("No series have been fetched yet.")
    if ctx.results:
        lines.append("Model results — use these exact result_index values:")
        for i, result in enumerate(ctx.results):
            name = getattr(result, "model_name", "yield_curve_fit")
            lines.append(f"  - result_index {i} = {name}")
    else:
        lines.append("No model results yet.")
    if ctx.artifacts:
        lines.append("Artifacts already created:")
        for i, artifact in enumerate(ctx.artifacts):
            lines.append(f"  - Figure {i + 1}: [{artifact['kind']}] {artifact['title']}")
    return "Current run state:\n" + "\n".join(lines)


def figure_manifest(artifacts: list[dict]) -> list[dict]:
    """Number the run's visual artifacts so report and panel agree on 'Figure N'."""
    figures = []
    for artifact in artifacts:
        if artifact["kind"] in ("chart", "table"):
            figures.append(
                {"number": len(figures) + 1, "kind": artifact["kind"],
                 "title": artifact["title"]}
            )
    return figures


def figure_index(artifacts: list[dict]) -> str:
    """A figure list appended to every report, so charts are always referenced.

    The explainer is asked to cite figures inline, but it is an LLM — this
    guarantees the report always points at the charts that were produced.
    """
    figures = figure_manifest(artifacts)
    if not figures:
        return ""
    lines = ["", "", "---", "", "## Figures", ""]
    for figure in figures:
        label = "Data table" if figure["kind"] == "table" else "Chart"
        lines.append(f"- **Figure {figure['number']}** — {figure['title']} ({label})")
    lines += [
        "",
        "_Figures are rendered under this report and in the Charts and Data tabs._",
    ]
    return "\n".join(lines)


def _run_node(
    node: dict, *, belt, ctx: ToolContext, llm, dep_outputs: dict,
    session_factory, bus, run_id, project_id, node_span, max_iterations,
    question: str = "",
):
    role = ROLES[node["role"]]
    system = (
        f"{role.system_prompt}\n\nAvailable tools:\n{_tool_docs(belt, role.tools)}\n\n{PROTOCOL}"
    )
    dep_context = "\n\n".join(
        f"Output from '{dep}':\n{dep_outputs[dep]}" for dep in node.get("depends_on", []) if dep in dep_outputs
    )
    # Every node sees the overall task: attachment notes and user preferences
    # live in the question, and agents must not lose them.
    user = (
        (f"Overall task:\n{question}\n\n" if question else "")
        + f"Your assignment: {node['instructions']}"
        + (f"\n\n{dep_context}" if dep_context else "")
        + f"\n\n{run_state_block(ctx)}"
    )
    messages = [{"role": "user", "content": user}]
    last_error_signature = None
    identical_errors = 0

    for iteration in range(max_iterations):
        resp = llm.complete(
            system, messages, project_id=project_id, run_id=run_id,
            agent_role=role.name, json_mode=True,
            trace_id=run_id, parent_span_id=node_span,
        )
        action = parse_action(resp.text)
        if action is None:
            messages.append({"role": "assistant", "content": resp.text})
            messages.append(
                {"role": "user", "content": "Respond with a single JSON object per the protocol."}
            )
            continue
        if action.get("action") == "finish":
            return str(action.get("output", ""))

        tool_name = action.get("tool", "")
        tool_args = action.get("args") or {}
        if tool_name not in role.tools:
            result = {"error": f"Tool '{tool_name}' not allowed for role {role.name}. Allowed: {role.tools}"}
        else:
            result = execute_tool(belt, tool_name, tool_args, ctx)
        emit(
            session_factory, bus, run_id=run_id, project_id=project_id,
            actor=f"agent:{role.name}", event_type="tool_call",
            parent_span_id=node_span,
            payload={
                "tool": tool_name, "args": tool_args,
                "ok": "error" not in result,
                "result_summary": json.dumps(result, default=str)[:800],
            },
        )
        if "error" in result:
            signature = (tool_name, json.dumps(tool_args, sort_keys=True, default=str),
                         str(result.get("error"))[:200])
            if signature == last_error_signature:
                identical_errors += 1
            else:
                last_error_signature = signature
                identical_errors = 1
            if identical_errors >= MAX_IDENTICAL_ERRORS:
                return (
                    f"Stopped after repeating the same failing call {identical_errors} "
                    f"times: {tool_name} -> {result.get('error')}"
                )
        else:
            last_error_signature = None
            identical_errors = 0
        messages.append({"role": "assistant", "content": resp.text})
        messages.append(
            {"role": "user", "content": json.dumps(result, default=str)[:MAX_TOOL_RESULT_CHARS]}
        )
    return messages[-1]["content"][:2000] if messages else ""


def execute_run(
    run_id: str, *, session_factory, llm, connectors, memory, bus: RunEventBus,
    max_node_iterations: int = 8, preset_plan: dict | None = None,
) -> dict:
    """Execute a run. `preset_plan` replays an existing (or user-edited) DAG,
    skipping the planner so a rerun reproduces exactly the requested steps."""
    with session_factory() as s:
        run = s.get(models.Run, run_id)
        project_id, chat_id, question = run.project_id, run.chat_id, run.question

    def _emit(event_type, actor="system", payload=None, **kw):
        return emit(
            session_factory, bus, run_id=run_id, project_id=project_id,
            actor=actor, event_type=event_type, payload=payload, **kw,
        )

    try:
        _emit("run_started", payload={"question": question})
        if preset_plan is not None:
            plan = validate_plan(preset_plan)
            plan["metadata"] = {**preset_plan.get("metadata", {}), "source": "rerun"}
        else:
            plan = make_plan(llm, question, memory, project_id)
        with session_factory() as s:
            run = s.get(models.Run, run_id)
            run.plan_json = json.dumps(plan, default=str)
            run.status = "running"
            s.commit()
        _emit("plan_created", actor="agent:planner", payload=plan)

        belt = build_toolbelt()
        ctx = ToolContext(
            session_factory=session_factory, connectors=connectors, memory=memory,
            project_id=project_id, run_id=run_id, chat_id=chat_id,
        )
        nodes_by_id = {n["id"]: n for n in plan["nodes"]}
        sorter = TopologicalSorter({n["id"]: set(n.get("depends_on", [])) for n in plan["nodes"]})
        sorter.prepare()
        dep_outputs: dict[str, str] = {}

        with ResourceSampler(session_factory, project_id, run_id):
            with ThreadPoolExecutor(max_workers=3) as pool:
                while sorter.is_active():
                    ready = list(sorter.get_ready())
                    if not ready:
                        break

                    def run_one(node_id: str):
                        node = nodes_by_id[node_id]
                        span = _emit(
                            "node_started", actor=f"agent:{node['role']}",
                            payload={"node": node_id, "role": node["role"],
                                     "instructions": node["instructions"]},
                        )
                        output = _run_node(
                            node, belt=belt, ctx=ctx, llm=llm, dep_outputs=dep_outputs,
                            session_factory=session_factory, bus=bus, run_id=run_id,
                            project_id=project_id, node_span=span,
                            max_iterations=max_node_iterations, question=question,
                        )
                        _emit(
                            "node_finished", actor=f"agent:{node['role']}",
                            span_id=models.new_id(), parent_span_id=span,
                            payload={"node": node_id, "output": output[:2000]},
                        )
                        return node_id, output

                    for node_id, output in pool.map(run_one, ready):
                        dep_outputs[node_id] = output
                        sorter.done(node_id)

        summary = next(
            (dep_outputs[n["id"]] for n in reversed(plan["nodes"]) if n["role"] == "explainer"),
            dep_outputs.get(plan["nodes"][-1]["id"], ""),
        )
        if summary:
            ctx.artifacts.append(
                {"kind": "report", "title": f"Report — {question[:60]}",
                 "payload": {"markdown": summary + figure_index(ctx.artifacts),
                             "figures": figure_manifest(ctx.artifacts)}}
            )
        from app.agents.engine.methodology import build_methodology

        ctx.artifacts.append(
            {"kind": "methodology", "title": "Prediction methodology",
             "payload": {"markdown": build_methodology(question, plan, ctx, dep_outputs)}}
        )

        # Persist artifacts produced by the tools plus the final report
        with session_factory() as s:
            for artifact in ctx.artifacts:
                s.add(
                    models.Artifact(
                        run_id=run_id, project_id=project_id, kind=artifact["kind"],
                        title=artifact["title"],
                        payload_json=json.dumps(artifact["payload"], default=str),
                    )
                )
            run = s.get(models.Run, run_id)
            run.status = "completed"
            run.finished_at = models.utcnow()
            s.commit()
        metrics = {}
        for result in ctx.results:
            backtest = getattr(result, "backtest", None)
            if isinstance(backtest, dict) and "model_rmse" in backtest:
                metrics = {k: backtest[k] for k in ("model_rmse", "baseline_rmse") if k in backtest}
                break
        memory.remember_episode(
            project_id=project_id, question=question, plan=plan,
            outcome="completed", metrics=metrics, run_id=run_id,
        )
        memory.remember_procedure(plan["kind"], plan, project_id=project_id)
        _emit("run_completed", payload={"artifacts": len(ctx.artifacts)})
        bus.close(run_id)
        return {"status": "completed", "summary": summary, "artifacts": len(ctx.artifacts)}

    except Exception as exc:
        logger.exception("Run %s failed", run_id)
        with session_factory() as s:
            run = s.get(models.Run, run_id)
            run.status = "failed"
            run.error = str(exc)
            run.finished_at = models.utcnow()
            s.commit()
        _emit("run_failed", payload={"error": str(exc)})
        bus.close(run_id)
        return {"status": "failed", "error": str(exc)}
