"""DAG executor: runs the planned agent workflow, streaming every step as trace events."""
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from graphlib import TopologicalSorter

from app import models
from app.agents.engine.events import RunEventBus, emit
from app.agents.engine.planner import make_plan, parse_action
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


def _run_node(
    node: dict, *, belt, ctx: ToolContext, llm, dep_outputs: dict,
    session_factory, bus, run_id, project_id, node_span, max_iterations,
):
    role = ROLES[node["role"]]
    system = (
        f"{role.system_prompt}\n\nAvailable tools:\n{_tool_docs(belt, role.tools)}\n\n{PROTOCOL}"
    )
    dep_context = "\n\n".join(
        f"Output from '{dep}':\n{dep_outputs[dep]}" for dep in node.get("depends_on", []) if dep in dep_outputs
    )
    user = node["instructions"] + (f"\n\n{dep_context}" if dep_context else "")
    messages = [{"role": "user", "content": user}]

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
        messages.append({"role": "assistant", "content": resp.text})
        messages.append(
            {"role": "user", "content": json.dumps(result, default=str)[:MAX_TOOL_RESULT_CHARS]}
        )
    return messages[-1]["content"][:2000] if messages else ""


def execute_run(
    run_id: str, *, session_factory, llm, connectors, memory, bus: RunEventBus,
    max_node_iterations: int = 8,
) -> dict:
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
                            max_iterations=max_node_iterations,
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
                 "payload": {"markdown": summary}}
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
