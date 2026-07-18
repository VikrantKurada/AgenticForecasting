"""SQLite response cache wrapping any connector. TTL 24h."""
import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from app import models
from app.connectors.base import SeriesData, SeriesMeta

TTL = timedelta(hours=24)


def _params_hash(params: dict) -> str:
    return hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()[:32]


class CachedConnector:
    def __init__(self, inner, session_factory):
        self.inner = inner
        self.source = inner.source
        self.session_factory = session_factory

    def search(self, query: str, limit: int = 10):
        return self.inner.search(query, limit)

    def fetch(self, series_id: str, **params) -> SeriesData:
        phash = _params_hash(params)
        now = datetime.now(timezone.utc)
        with self.session_factory() as s:
            row = (
                s.query(models.SeriesCache)
                .filter_by(source=self.source, series_key=series_id, params_hash=phash)
                .one_or_none()
            )
            if row is not None:
                fetched = datetime.fromisoformat(row.fetched_at)
                if now - fetched < TTL:
                    payload = json.loads(row.payload_json)
                    return SeriesData(
                        meta=SeriesMeta(**payload["meta"]),
                        observations=[tuple(o) for o in payload["observations"]],
                    )

        data = self.inner.fetch(series_id, **params)
        payload_json = json.dumps(
            {"meta": asdict(data.meta), "observations": data.observations}
        )
        with self.session_factory() as s:
            row = (
                s.query(models.SeriesCache)
                .filter_by(source=self.source, series_key=series_id, params_hash=phash)
                .one_or_none()
            )
            if row is None:
                s.add(
                    models.SeriesCache(
                        source=self.source, series_key=series_id,
                        params_hash=phash, payload_json=payload_json,
                    )
                )
            else:
                row.payload_json = payload_json
                row.fetched_at = models.utcnow()
            s.commit()
        return data
