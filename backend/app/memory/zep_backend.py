"""Zep (Graphiti) cloud adapter via the graph API. Project ID maps to Zep user_id."""
import httpx

from app.memory.base import MemoryItem

BASE = "https://api.getzep.com/api/v2"


class ZepBackend:
    name = "zep"

    def __init__(self, api_key: str, client: httpx.Client | None = None):
        if not api_key:
            raise ValueError("Zep requires ZEP_API_KEY")
        self.client = client or httpx.Client(headers={"Authorization": f"Api-Key {api_key}"})

    def _user(self, project_id):
        return f"forecasting-{project_id or 'default'}"

    def add(self, mem_type, content, *, project_id=None, chat_id=None, key="", meta=None) -> str:
        resp = self.client.post(
            f"{BASE}/graph",
            json={
                "user_id": self._user(project_id), "type": "text",
                "data": f"[{mem_type}{f':{key}' if key else ''}] {content}",
            },
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        return str(payload.get("uuid", "")) if isinstance(payload, dict) else ""

    def search(self, query, mem_type=None, project_id=None, limit=5):
        resp = self.client.post(
            f"{BASE}/graph/search",
            json={"user_id": self._user(project_id), "query": query, "limit": limit},
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        edges = payload.get("edges") or payload.get("results") or []
        return [
            MemoryItem(
                id=str(e.get("uuid", "")), mem_type=mem_type or "semantic",
                content=e.get("fact") or e.get("content") or "", project_id=project_id,
            )
            for e in edges
        ][:limit]

    def get_recent(self, mem_type, project_id=None, chat_id=None, limit=20):
        # Zep's graph is search-oriented; recency listing falls back to a broad search.
        return self.search("*", mem_type=mem_type, project_id=project_id, limit=limit)

    def delete(self, item_id) -> None:
        self.client.delete(f"{BASE}/graph/edge/{item_id}", timeout=30)
