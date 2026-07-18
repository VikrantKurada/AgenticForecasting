"""Pluggable memory backend interface.

Memory types:
  short_term  — per-chat rolling context (read from messages, not stored here)
  episodic    — records of past forecast runs and their outcomes
  semantic    — facts with retrieval (indicator definitions, country knowledge)
  procedural  — successful workflow DAGs reusable as templates
  long-term   — the persistence of all of the above across sessions
"""
from dataclasses import dataclass, field
from typing import Protocol

MEM_TYPES = ("short_term", "episodic", "semantic", "procedural")


@dataclass
class MemoryItem:
    id: str
    mem_type: str
    content: str
    key: str = ""
    project_id: str | None = None
    chat_id: str | None = None
    meta: dict = field(default_factory=dict)
    created_at: str = ""


class MemoryBackend(Protocol):
    name: str

    def add(
        self, mem_type: str, content: str, *,
        project_id: str | None = None, chat_id: str | None = None,
        key: str = "", meta: dict | None = None,
    ) -> str: ...

    def search(
        self, query: str, mem_type: str | None = None,
        project_id: str | None = None, limit: int = 5,
    ) -> list[MemoryItem]: ...

    def get_recent(
        self, mem_type: str, project_id: str | None = None,
        chat_id: str | None = None, limit: int = 20,
    ) -> list[MemoryItem]: ...

    def delete(self, item_id: str) -> None: ...
