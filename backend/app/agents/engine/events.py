"""Run event emission: every event lands in the events table and on the live SSE bus."""
import json
import queue
import threading

from app import models

SENTINEL = {"type": "__end__"}


class RunEventBus:
    """In-memory fanout of live run events to SSE subscribers."""

    def __init__(self):
        self._lock = threading.Lock()
        self._subscribers: dict[str, list[queue.Queue]] = {}

    def subscribe(self, run_id: str) -> queue.Queue:
        q: queue.Queue = queue.Queue()
        with self._lock:
            self._subscribers.setdefault(run_id, []).append(q)
        return q

    def unsubscribe(self, run_id: str, q: queue.Queue) -> None:
        with self._lock:
            if run_id in self._subscribers and q in self._subscribers[run_id]:
                self._subscribers[run_id].remove(q)

    def publish(self, run_id: str, event: dict) -> None:
        with self._lock:
            queues = list(self._subscribers.get(run_id, []))
        for q in queues:
            q.put(event)

    def close(self, run_id: str) -> None:
        self.publish(run_id, SENTINEL)
        with self._lock:
            self._subscribers.pop(run_id, None)


def emit(
    session_factory, bus: RunEventBus, *,
    run_id: str, project_id: str | None, actor: str, event_type: str,
    trace_id: str | None = None, span_id: str | None = None,
    parent_span_id: str | None = None, payload: dict | None = None,
) -> str:
    span_id = span_id or models.new_id()
    row = models.Event(
        project_id=project_id, run_id=run_id,
        trace_id=trace_id or run_id, span_id=span_id, parent_span_id=parent_span_id,
        actor=actor, event_type=event_type,
        payload_json=json.dumps(payload or {}, default=str),
    )
    with session_factory() as s:
        s.add(row)
        s.commit()
        event_dict = {
            "id": row.id, "type": event_type, "actor": actor,
            "span_id": span_id, "parent_span_id": parent_span_id,
            "payload": payload or {}, "ts": row.ts,
        }
    bus.publish(run_id, event_dict)
    return span_id
