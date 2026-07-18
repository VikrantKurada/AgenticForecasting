import time
from dataclasses import dataclass, field
from typing import Protocol

import httpx


class ConnectorError(Exception):
    """A data source call failed after retries. Surfaces as a trace event upstream."""


@dataclass
class SeriesMeta:
    source: str
    series_id: str
    title: str
    frequency: str = ""
    units: str = ""
    extra: dict = field(default_factory=dict)


@dataclass
class SeriesData:
    meta: SeriesMeta
    observations: list[tuple]  # [(date_str, value_or_None), ...] ascending by date


class Connector(Protocol):
    source: str

    def search(self, query: str, limit: int = 10) -> list[SeriesMeta]: ...
    def fetch(self, series_id: str, **params) -> SeriesData: ...


def request_json(client: httpx.Client, url: str, params: dict, retries: int = 3, backoff: float = 0.5):
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            resp = client.get(url, params=params, timeout=30)
            if resp.status_code >= 500:
                last_error = ConnectorError(f"{url} returned {resp.status_code}")
            elif resp.status_code >= 400:
                raise ConnectorError(f"{url} returned {resp.status_code}: {resp.text[:200]}")
            else:
                return resp.json()
        except ConnectorError:
            raise
        except Exception as exc:
            last_error = exc
        time.sleep(backoff * (2**attempt))
    raise ConnectorError(f"Request failed after {retries} attempts: {last_error}")
