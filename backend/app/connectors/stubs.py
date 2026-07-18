from app.connectors.base import ConnectorError, SeriesData, SeriesMeta


class StubConnector:
    """Registered source whose implementation is planned but not yet built."""

    def __init__(self, source: str, message: str):
        self.source = source
        self.message = message

    def search(self, query: str, limit: int = 10) -> list[SeriesMeta]:
        return []

    def fetch(self, series_id: str, **params) -> SeriesData:
        raise ConnectorError(self.message)
