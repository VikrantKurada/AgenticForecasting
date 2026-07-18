"""Chat pipeline: routes a user message to a forecasting run, a follow-up answer, or chat."""
import json
import logging
import threading

from app import models
from app.agents.engine.executor import execute_run
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


def _run_and_persist_answer(state, run_id: str, chat_id: str):
    outcome = execute_run(
        run_id,
        session_factory=state["session_factory"], llm=state["llm_registry"],
        connectors=state["connectors"], memory=state["memory_service"],
        bus=state["run_bus"],
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


def handle_message(state, chat_id: str, content: str, *, inline: bool = False) -> dict:
    session_factory = state["session_factory"]
    with session_factory() as s:
        chat = s.get(models.Chat, chat_id)
        if chat is None:
            raise KeyError("Chat not found")
        project_id = chat.project_id

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
        with session_factory() as s:
            run = models.Run(chat_id=chat_id, project_id=project_id, question=content)
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
