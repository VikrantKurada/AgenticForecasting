import json
import queue

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app import models
from app.agents.pipeline import handle_message
from app.deps import get_db

router = APIRouter(prefix="/api", tags=["chat"])


class MessageIn(BaseModel):
    content: str
    preferences: dict | None = None


def _state(request: Request) -> dict:
    app = request.app
    from app.memory.service import MemoryService

    return {
        "session_factory": app.state.session_factory,
        "llm_registry": app.state.llm_registry,
        "connectors": app.state.connectors,
        "memory_service": MemoryService(app.state.memory_backend, app.state.session_factory),
        "run_bus": app.state.run_bus,
    }


@router.post("/chats/{chat_id}/messages")
def post_message(chat_id: str, body: MessageIn, request: Request):
    try:
        return handle_message(
            _state(request), chat_id, body.content,
            inline=getattr(request.app.state, "run_inline", False),
            preferences=body.preferences,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Chat not found")


@router.get("/runs/{run_id}")
def get_run(run_id: str, db=Depends(get_db)):
    run = db.get(models.Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return {
        "id": run.id, "chat_id": run.chat_id, "project_id": run.project_id,
        "question": run.question, "status": run.status,
        "plan": json.loads(run.plan_json) if run.plan_json else None,
        "error": run.error, "started_at": run.started_at, "finished_at": run.finished_at,
    }


@router.get("/runs/{run_id}/artifacts")
def get_run_artifacts(run_id: str, db=Depends(get_db)):
    artifacts = (
        db.query(models.Artifact)
        .filter_by(run_id=run_id)
        .order_by(models.Artifact.created_at.asc())
        .all()
    )
    return [
        {"id": a.id, "kind": a.kind, "title": a.title,
         "payload": json.loads(a.payload_json), "created_at": a.created_at}
        for a in artifacts
    ]


TERMINAL = {"completed", "failed"}


@router.get("/runs/{run_id}/stream")
def stream_run(run_id: str, request: Request):
    session_factory = request.app.state.session_factory
    bus = request.app.state.run_bus
    with session_factory() as s:
        if s.get(models.Run, run_id) is None:
            raise HTTPException(status_code=404, detail="Run not found")

    def generate():
        subscription = bus.subscribe(run_id)
        seen: set[str] = set()
        try:
            with session_factory() as s:
                run = s.get(models.Run, run_id)
                status = run.status
                rows = (
                    s.query(models.Event)
                    .filter_by(run_id=run_id)
                    .order_by(models.Event.ts.asc())
                    .all()
                )
            for row in rows:
                seen.add(row.id)
                yield {
                    "event": "run_event",
                    "data": json.dumps({
                        "id": row.id, "type": row.event_type, "actor": row.actor,
                        "span_id": row.span_id, "parent_span_id": row.parent_span_id,
                        "payload": json.loads(row.payload_json), "ts": row.ts,
                    }),
                }
            if status in TERMINAL:
                yield {"event": "end", "data": "{}"}
                return
            while True:
                try:
                    event = subscription.get(timeout=3)
                except queue.Empty:
                    with session_factory() as s:
                        run = s.get(models.Run, run_id)
                    if run.status in TERMINAL:
                        break
                    yield {"event": "ping", "data": "{}"}
                    continue
                if event.get("type") == "__end__":
                    break
                if event.get("id") in seen:
                    continue
                yield {"event": "run_event", "data": json.dumps(event, default=str)}
            yield {"event": "end", "data": "{}"}
        finally:
            bus.unsubscribe(run_id, subscription)

    return EventSourceResponse(generate())
