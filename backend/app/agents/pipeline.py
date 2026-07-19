"""Chat pipeline: routes a user message to a forecasting run, a follow-up answer, or chat."""
import json
import logging
import threading

from pydantic import ValidationError

from app import models
from app.agents.engine.executor import execute_run
from app.agents.engine.planner import validate_plan
from app.events import record_event

logger = logging.getLogger(__name__)

FORECAST_WORDS = (
    "forecast", "nowcast", "predict", "projection", "outlook", "will ",
    "probability", "risk of", "default", "trajectory", "yield", "estimate",
    "next quarter", "next year", "where is", "heading", "spillover", "impact of",
)
FOLLOWUP_WORDS = (
    "why", "how did", "how was", "explain", "what model", "which model",
    "methodology", "what data", "caveat", "confidence", "accurate",
)


def classify_intent(content: str, has_prior_run: bool) -> str:
    lowered = content.lower()
    if has_prior_run and any(w in lowered for w in FOLLOWUP_WORDS):
        return "followup"
    if any(w in lowered for w in FORECAST_WORDS):
        return "forecast_request"
    if has_prior_run:
        return "followup"
    return "smalltalk"


def _latest_run(session_factory, chat_id: str):
    with session_factory() as s:
        return (
            s.query(models.Run)
            .filter_by(chat_id=chat_id)
            .order_by(models.Run.started_at.desc())
            .first()
        )


def _persist_message(session_factory, chat_id: str, role: str, content: str, run_id=None):
    with session_factory() as s:
        msg = models.Message(chat_id=chat_id, role=role, content=content, run_id=run_id)
        s.add(msg)
        s.commit()
        return {"id": msg.id, "chat_id": chat_id, "role": role, "content": content,
                "run_id": run_id, "created_at": msg.created_at}


def _run_and_persist_answer(state, run_id: str, chat_id: str, preset_plan: dict | None = None):
    outcome = execute_run(
        run_id,
        session_factory=state["session_factory"], llm=state["llm_registry"],
        connectors=state["connectors"], memory=state["memory_service"],
        bus=state["run_bus"], preset_plan=preset_plan,
    )
    if outcome["status"] == "completed":
        content = outcome.get("summary") or "The forecast run completed. See the output panel."
    else:
        content = (
            f"The forecast run failed: {outcome.get('error', 'unknown error')}\n\n"
            "Check provider settings and data source keys, then try again."
        )
    return _persist_message(state["session_factory"], chat_id, "assistant", content, run_id=run_id)


def _answer_followup(state, chat_id: str, content: str) -> str:
    session_factory = state["session_factory"]
    run = _latest_run(session_factory, chat_id)
    context_parts = []
    if run is not None:
        context_parts.append(f"Question of the last run: {run.question}\nStatus: {run.status}")
        if run.plan_json:
            context_parts.append(f"Workflow plan that was executed:\n{run.plan_json[:3000]}")
        with session_factory() as s:
            events = (
                s.query(models.Event)
                .filter_by(run_id=run.id, event_type="tool_call")
                .order_by(models.Event.ts.asc())
                .limit(20)
                .all()
            )
            for e in events:
                payload = json.loads(e.payload_json)
                context_parts.append(f"- {e.actor} called {payload.get('tool')}")
            last_answer = (
                s.query(models.Message)
                .filter_by(chat_id=chat_id, role="assistant")
                .order_by(models.Message.created_at.desc())
                .first()
            )
            if last_answer:
                context_parts.append(f"Previous answer given to the user:\n{last_answer.content[:3000]}")
    memory = state["memory_service"]
    facts = memory.semantic_facts(content, limit=3)
    if facts:
        context_parts.append("Relevant memory:\n" + "\n".join(f.content for f in facts))

    system = (
        "You are the explainer of an agentic economic forecasting system. Answer the "
        "user's question about the forecast that was just produced, grounded strictly "
        "in the run trace below. Be precise about data, models, and caveats."
    )
    prompt = "\n\n".join(context_parts) + f"\n\nUser question: {content}"
    resp = state["llm_registry"].complete(
        system, [{"role": "user", "content": prompt}],
        project_id=run.project_id if run else None,
        run_id=run.id if run else None, agent_role="explainer",
    )
    return resp.text


def rerun(state, run_id: str, *, plan: dict | None = None, inline: bool = False) -> dict:
    """Re-execute a past run's workflow as a new run in the same chat.

    `plan` lets the user edit the orchestrator DAG (node instructions, roles,
    dependencies) before replaying it; omitted, the original plan is reused.
    """
    session_factory = state["session_factory"]
    with session_factory() as s:
        source = s.get(models.Run, run_id)
        if source is None:
            raise KeyError("Run not found")
        chat_id, project_id, question = source.chat_id, source.project_id, source.question
        preset_plan = plan if plan is not None else (
            json.loads(source.plan_json) if source.plan_json else None
        )
        if preset_plan is None:
            raise ValueError("Original run has no plan to rerun")
        # Reject a bad edit up front rather than starting a run doomed to fail.
        try:
            validate_plan(preset_plan)
        except (ValidationError, ValueError) as exc:
            raise ValueError(f"Invalid workflow plan: {exc}")
        new_run = models.Run(chat_id=chat_id, project_id=project_id, question=question)
        s.add(new_run)
        s.flush()
        new_run_id = new_run.id
        record_event(
            s, actor="user", event_type="run_rerun",
            project_id=project_id,
            payload={"source_run_id": run_id, "run_id": new_run_id,
                     "edited": plan is not None},
        )
        s.commit()

    if inline:
        assistant = _run_and_persist_answer(state, new_run_id, chat_id, preset_plan)
        return {"run_id": new_run_id, "source_run_id": run_id, "assistant_message": assistant}
    threading.Thread(
        target=_run_and_persist_answer,
        args=(state, new_run_id, chat_id, preset_plan), daemon=True,
    ).start()
    return {"run_id": new_run_id, "source_run_id": run_id}


AUTO_NAME_DEFAULTS = ("New chat", "")


def _preferences_suffix(preferences: dict | None) -> str:
    if not preferences:
        return ""
    parts = []
    sources = preferences.get("sources") or (
        [preferences["source"]] if preferences.get("source") else []
    )
    if sources:
        quoted = ", ".join(f"'{s}'" for s in sources)
        parts.append(f"prefer data source{'s' if len(sources) > 1 else ''} {quoted}")
    if preferences.get("horizon"):
        parts.append(f"forecast horizon: {preferences['horizon']} periods")
    if preferences.get("history_years"):
        parts.append(f"use about {preferences['history_years']} years of history")
    return f"\n\n[User preferences: {'; '.join(parts)}]" if parts else ""


def _attachments_suffix(session_factory, chat_id: str, project_id: str) -> str:
    import json as _json

    with session_factory() as s:
        files = (
            s.query(models.UploadedFile)
            .filter(
                (models.UploadedFile.chat_id == chat_id)
                | ((models.UploadedFile.project_id == project_id)
                   & (models.UploadedFile.chat_id.is_(None)))
            )
            .all()
        )
    if not files:
        return ""
    lines = []
    for file in files:
        columns = _json.loads(file.columns_json or "{}")
        series = ", ".join(
            f"'{file.id}:{c}'" for c in columns.get("numeric_columns", [])
        )
        lines.append(
            f"- {file.filename} ({file.n_rows} rows; date column: "
            f"{columns.get('date_column') or 'none'}) — fetch with source 'uploads', "
            f"series_id {series}"
        )
    return (
        "\n\n[Attached data files — treat these as first-class data sources:\n"
        + "\n".join(lines) + "\n]"
    )


def handle_message(
    state, chat_id: str, content: str, *, inline: bool = False,
    preferences: dict | None = None,
) -> dict:
    session_factory = state["session_factory"]
    with session_factory() as s:
        chat = s.get(models.Chat, chat_id)
        if chat is None:
            raise KeyError("Chat not found")
        project_id = chat.project_id
        if chat.title in AUTO_NAME_DEFAULTS:
            title = content.strip().splitlines()[0][:60]
            chat.title = title + ("…" if len(content.strip()) > 60 else "")
            record_event(
                s, actor="system", event_type="chat_auto_named",
                project_id=project_id, payload={"chat_id": chat_id, "title": chat.title},
            )
            s.commit()

    user_message = _persist_message(session_factory, chat_id, "user", content)
    with session_factory() as s:
        record_event(
            s, actor="user", event_type="message_sent",
            project_id=project_id, payload={"chat_id": chat_id, "length": len(content)},
        )
        s.commit()

    has_prior = _latest_run(session_factory, chat_id) is not None
    intent = classify_intent(content, has_prior)

    if intent == "forecast_request":
        question = content + _preferences_suffix(preferences)
        question += _attachments_suffix(session_factory, chat_id, project_id)
        with session_factory() as s:
            run = models.Run(chat_id=chat_id, project_id=project_id, question=question)
            s.add(run)
            s.commit()
            run_id = run.id
        if inline:
            assistant = _run_and_persist_answer(state, run_id, chat_id)
            return {"intent": intent, "user_message": user_message,
                    "run_id": run_id, "assistant_message": assistant}
        thread = threading.Thread(
            target=_run_and_persist_answer, args=(state, run_id, chat_id), daemon=True
        )
        thread.start()
        return {"intent": intent, "user_message": user_message, "run_id": run_id}

    if intent == "followup":
        answer = _answer_followup(state, chat_id, content)
        assistant = _persist_message(session_factory, chat_id, "assistant", answer)
        return {"intent": intent, "user_message": user_message, "assistant_message": assistant}

    resp = state["llm_registry"].complete(
        "You are a professional macroeconomic forecasting assistant. The user has not "
        "asked for a forecast yet; reply briefly and suggest what you can forecast "
        "(GDP/inflation nowcasts, sovereign default risk, yield curves, geopolitical "
        "spillovers).",
        [{"role": "user", "content": content}],
        project_id=project_id, agent_role="assistant",
    )
    assistant = _persist_message(session_factory, chat_id, "assistant", resp.text)
    return {"intent": intent, "user_message": user_message, "assistant_message": assistant}
