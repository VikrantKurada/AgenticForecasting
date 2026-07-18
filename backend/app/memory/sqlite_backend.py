"""Built-in memory backend: SQLite rows + TF-IDF semantic retrieval."""
import json

from app import models
from app.memory.base import MemoryItem


def _to_item(row: models.MemoryItem) -> MemoryItem:
    return MemoryItem(
        id=row.id, mem_type=row.mem_type, content=row.content, key=row.key,
        project_id=row.project_id, chat_id=row.chat_id,
        meta=json.loads(row.meta_json or "{}"), created_at=row.created_at,
    )


class SQLiteMemoryBackend:
    name = "builtin"

    def __init__(self, session_factory):
        self.session_factory = session_factory

    def add(self, mem_type, content, *, project_id=None, chat_id=None, key="", meta=None) -> str:
        with self.session_factory() as s:
            row = models.MemoryItem(
                mem_type=mem_type, content=content, key=key or "",
                project_id=project_id, chat_id=chat_id,
                meta_json=json.dumps(meta or {}, default=str),
            )
            s.add(row)
            s.commit()
            return row.id

    def _candidates(self, s, mem_type, project_id):
        query = s.query(models.MemoryItem)
        if mem_type:
            query = query.filter_by(mem_type=mem_type)
        if project_id:
            query = query.filter(
                (models.MemoryItem.project_id == project_id)
                | (models.MemoryItem.project_id.is_(None))
            )
        return query.all()

    def search(self, query, mem_type=None, project_id=None, limit=5):
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        with self.session_factory() as s:
            rows = self._candidates(s, mem_type, project_id)
        if not rows:
            return []
        contents = [r.content for r in rows]
        try:
            vectorizer = TfidfVectorizer(stop_words="english")
            matrix = vectorizer.fit_transform(contents + [query])
            scores = cosine_similarity(matrix[-1], matrix[:-1]).ravel()
        except ValueError:
            return []
        ranked = sorted(zip(scores, rows), key=lambda t: -t[0])
        return [_to_item(r) for score, r in ranked[:limit] if score > 0]

    def get_recent(self, mem_type, project_id=None, chat_id=None, limit=20):
        with self.session_factory() as s:
            query = s.query(models.MemoryItem).filter_by(mem_type=mem_type)
            if project_id:
                query = query.filter_by(project_id=project_id)
            if chat_id:
                query = query.filter_by(chat_id=chat_id)
            rows = query.order_by(models.MemoryItem.created_at.desc()).limit(limit).all()
        return [_to_item(r) for r in rows]

    def delete(self, item_id) -> None:
        with self.session_factory() as s:
            row = s.get(models.MemoryItem, item_id)
            if row is not None:
                s.delete(row)
                s.commit()
