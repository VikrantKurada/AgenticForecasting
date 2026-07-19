"""User-uploaded data files (CSV/Excel/TSV/JSON) exposed as a data source.

Series IDs: "<file_id>:<column>". Agents discover them via search_series and the
attachment note injected into each run's question.
"""
import json
from pathlib import Path

import pandas as pd

from app import models
from app.connectors.base import ConnectorError, SeriesData, SeriesMeta

READERS = {
    ".csv": lambda p: pd.read_csv(p),
    ".tsv": lambda p: pd.read_csv(p, sep="\t"),
    ".txt": lambda p: pd.read_csv(p, sep=None, engine="python"),
    ".xlsx": lambda p: pd.read_excel(p),
    ".xls": lambda p: pd.read_excel(p),
    ".json": lambda p: pd.read_json(p),
}

SUPPORTED_EXTENSIONS = sorted(READERS)


def read_dataframe(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    reader = READERS.get(path.suffix.lower())
    if reader is None:
        raise ConnectorError(
            f"Unsupported file type '{path.suffix}'. Supported: {SUPPORTED_EXTENSIONS}"
        )
    return reader(path)


def _is_year_column(series: pd.Series) -> bool:
    if not pd.api.types.is_numeric_dtype(series):
        return False
    values = series.dropna()
    return len(values) > 0 and values.between(1800, 2200).all() and (values % 1 == 0).all()


def analyze_dataframe(df: pd.DataFrame) -> dict:
    date_column = None
    for column in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[column]):
            date_column = str(column)
            break
        if _is_year_column(df[column]):
            date_column = str(column)
            break
        if not pd.api.types.is_numeric_dtype(df[column]):
            parsed = pd.to_datetime(df[column], errors="coerce", format="mixed")
            if parsed.notna().mean() >= 0.8:
                date_column = str(column)
                break
    numeric_columns = [
        str(c) for c in df.select_dtypes("number").columns if str(c) != date_column
    ]
    return {
        "date_column": date_column,
        "numeric_columns": numeric_columns,
        "all_columns": [str(c) for c in df.columns],
    }


def _date_strings(df: pd.DataFrame, date_column: str | None) -> list[str]:
    if date_column is None or date_column not in df.columns:
        return [str(i + 1) for i in range(len(df))]
    column = df[date_column]
    if _is_year_column(column):
        return [str(int(v)) if pd.notna(v) else "" for v in column]
    if pd.api.types.is_datetime64_any_dtype(column):
        parsed = column
    else:
        parsed = pd.to_datetime(column, errors="coerce", format="mixed")
    return [d.strftime("%Y-%m-%d") if pd.notna(d) else "" for d in parsed]


class UploadsConnector:
    source = "uploads"

    def __init__(self, session_factory):
        self.session_factory = session_factory

    def _files(self) -> list[models.UploadedFile]:
        with self.session_factory() as s:
            return s.query(models.UploadedFile).order_by(
                models.UploadedFile.created_at.desc()
            ).all()

    def search(self, query: str, limit: int = 10) -> list[SeriesMeta]:
        words = query.lower().split()
        results = []
        for file in self._files():
            columns = json.loads(file.columns_json or "{}")
            for column in columns.get("numeric_columns", []):
                title = f"{file.filename} — {column} (uploaded)"
                if not words or any(w in title.lower() for w in words):
                    results.append(
                        SeriesMeta(
                            source=self.source,
                            series_id=f"{file.id}:{column}",
                            title=title,
                        )
                    )
        return results[:limit]

    def fetch(self, series_id: str, **params) -> SeriesData:
        if ":" not in series_id:
            raise ConnectorError(
                f"Uploads series id must be '<file_id>:<column>', got '{series_id}'"
            )
        file_id, column = series_id.split(":", 1)
        with self.session_factory() as s:
            file = s.get(models.UploadedFile, file_id)
        if file is None:
            raise ConnectorError(f"No uploaded file with id '{file_id}'")
        df = read_dataframe(file.stored_path)
        if column not in df.columns:
            raise ConnectorError(
                f"Column '{column}' not in {file.filename}. Columns: {list(df.columns)}"
            )
        columns = json.loads(file.columns_json or "{}")
        dates = _date_strings(df, columns.get("date_column"))
        observations = [
            (date, float(value) if pd.notna(value) else None)
            for date, value in zip(dates, df[column])
            if date
        ]
        return SeriesData(
            meta=SeriesMeta(
                source=self.source, series_id=series_id,
                title=f"{file.filename} — {column}",
            ),
            observations=observations,
        )
