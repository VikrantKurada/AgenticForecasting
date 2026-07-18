"""Typed helpers over the active memory backend, used by the agent engine."""
import json

from app import models
from app.memory.base import MemoryBackend, MemoryItem


class MemoryService:
    def __init__(self, backend: MemoryBackend, session_factory):
        self.backend = backend
        self.session_factory = session_factory

    # -- episodic ----------------------------------------------------------
    def remember_episode(
        self, *, project_id: str, question: str, plan: dict,
        outcome: str, metrics: dict | None = None, run_id: str | None = None,
    ) -> str:
        content = json.dumps(
            {
                "question": question, "plan": plan, "outcome": outcome,
                "metrics": metrics or {}, "run_id": run_id,
            },
            default=str,
        )
        return self.backend.add("episodic", content, project_id=project_id)

    def recent_episodes(self, project_id: str, limit: int = 5) -> list[MemoryItem]:
        return self.backend.get_recent("episodic", project_id=project_id, limit=limit)

    # -- procedural --------------------------------------------------------
    def remember_procedure(self, kind: str, dag: dict, *, project_id: str | None = None) -> str:
        return self.backend.add(
            "procedural", json.dumps(dag, default=str), key=kind, project_id=project_id
        )

    def procedures_for(self, kind: str, project_id: str | None = None) -> list[MemoryItem]:
        items = self.backend.get_recent("procedural", project_id=project_id, limit=50)
        return [i for i in items if i.key == kind][:3]

    # -- semantic ----------------------------------------------------------
    def add_fact(self, content: str, *, project_id: str | None = None) -> str:
        return self.backend.add("semantic", content, project_id=project_id)

    def semantic_facts(self, query: str, project_id: str | None = None, limit: int = 5):
        return self.backend.search(query, mem_type="semantic", project_id=project_id, limit=limit)

    # -- short-term (per-chat rolling window over the messages table) ------
    def short_term(self, chat_id: str, limit: int = 12) -> list[dict]:
        with self.session_factory() as s:
            rows = (
                s.query(models.Message)
                .filter_by(chat_id=chat_id)
                .order_by(models.Message.created_at.desc())
                .limit(limit)
                .all()
            )
        return [{"role": r.role, "content": r.content} for r in reversed(rows)]
