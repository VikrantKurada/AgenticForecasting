"""Telemetry event recording. Every user action and agent decision lands in the events table."""
import json

from app import models


def record_event(
    session,
    *,
    actor: str,
    event_type: str,
    project_id: str | None = None,
    run_id: str | None = None,
    trace_id: str | None = None,
    span_id: str | None = None,
    parent_span_id: str | None = None,
    payload: dict | None = None,
) -> models.Event:
    ev = models.Event(
        project_id=project_id,
        run_id=run_id,
        trace_id=trace_id or models.new_id(),
        span_id=span_id or models.new_id(),
        parent_span_id=parent_span_id,
        actor=actor,
        event_type=event_type,
        payload_json=json.dumps(payload or {}, default=str),
    )
    session.add(ev)
    return ev
