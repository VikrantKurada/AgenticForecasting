"""Mem0 cloud memory adapter (api.mem0.ai). Project ID maps to Mem0 user_id."""
import httpx

from app.memory.base import MemoryItem

BASE = "https://api.mem0.ai/v1"


class Mem0Backend:
    name = "mem0"

    def __init__(self, api_key: str, client: httpx.Client | None = None):
        if not api_key:
            raise ValueError("Mem0 requires MEM0_API_KEY")
        self.client = client or httpx.Client(headers={"Authorization": f"Token {api_key}"})

    def _user(self, project_id):
        return project_id or "default"

    def add(self, mem_type, content, *, project_id=None, chat_id=None, key="", meta=None) -> str:
        resp = self.client.post(
            f"{BASE}/memories/",
            json={
                "messages": [{"role": "user", "content": content}],
                "user_id": self._user(project_id),
                "metadata": {"mem_type": mem_type, "key": key, **(meta or {})},
            },
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        first = payload[0] if isinstance(payload, list) and payload else payload
        return str(first.get("id", "")) if isinstance(first, dict) else ""

    def search(self, query, mem_type=None, project_id=None, limit=5):
        resp = self.client.post(
            f"{BASE}/memories/search/",
            json={"query": query, "user_id": self._user(project_id), "limit": limit},
            timeout=30,
        )
        resp.raise_for_status()
        results = resp.json()
        if isinstance(results, dict):
            results = results.get("results", [])
        items = []
        for r in results:
            metadata = r.get("metadata") or {}
            if mem_type and metadata.get("mem_type") not in (None, mem_type):
                continue
            items.append(
                MemoryItem(
                    id=str(r.get("id", "")), mem_type=metadata.get("mem_type", "semantic"),
                    content=r.get("memory", ""), key=metadata.get("key", ""),
                    project_id=project_id, meta=metadata,
                )
            )
        return items[:limit]

    def get_recent(self, mem_type, project_id=None, chat_id=None, limit=20):
        resp = self.client.get(
            f"{BASE}/memories/", params={"user_id": self._user(project_id)}, timeout=30
        )
        resp.raise_for_status()
        results = resp.json()
        if isinstance(results, dict):
            results = results.get("results", [])
        items = [
            MemoryItem(
                id=str(r.get("id", "")),
                mem_type=(r.get("metadata") or {}).get("mem_type", "semantic"),
                content=r.get("memory", ""), key=(r.get("metadata") or {}).get("key", ""),
                project_id=project_id, meta=r.get("metadata") or {},
            )
            for r in results
            if (r.get("metadata") or {}).get("mem_type") in (None, mem_type)
        ]
        return items[:limit]

    def delete(self, item_id) -> None:
        self.client.delete(f"{BASE}/memories/{item_id}/", timeout=30)
