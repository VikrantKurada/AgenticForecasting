"""Export artifacts to files at a user-chosen location (defaults to the Desktop)."""
import csv
import io
import json
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app import models
from app.deps import get_db
from app.events import record_event

router = APIRouter(prefix="/api", tags=["files"])

CHART_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{title}</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script></head>
<body style="margin:0;font-family:system-ui"><div id="chart" style="height:96vh"></div>
<script>Plotly.newPlot("chart", {figure});</script></body></html>
"""


def _safe_name(title: str) -> str:
    return re.sub(r"[^\w\- ]+", "", title).strip().replace(" ", "_") or "artifact"


@router.get("/fs/default-dir")
def default_dir():
    desktop = Path.home() / "Desktop"
    return {"path": str(desktop if desktop.exists() else Path.home())}


class SaveRequest(BaseModel):
    directory: str
    filename: str | None = None


@router.post("/artifacts/{artifact_id}/save")
def save_artifact(artifact_id: str, body: SaveRequest, db=Depends(get_db)):
    artifact = db.get(models.Artifact, artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    directory = Path(body.directory).expanduser()
    if not directory.is_dir():
        raise HTTPException(status_code=400, detail=f"Directory does not exist: {directory}")

    payload = json.loads(artifact.payload_json)
    stem = _safe_name(body.filename or artifact.title)

    if artifact.kind in ("report", "methodology"):
        path = directory / f"{stem}.md"
        content = payload.get("markdown") or payload.get("text") or json.dumps(payload, indent=2)
        path.write_text(content, encoding="utf-8")
    elif artifact.kind == "table":
        path = directory / f"{stem}.csv"
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(payload.get("columns", []))
        writer.writerows(payload.get("rows", []))
        path.write_text(buffer.getvalue(), encoding="utf-8")
    elif artifact.kind == "chart":
        path = directory / f"{stem}.html"
        figure = json.dumps({"data": payload.get("data", []), "layout": payload.get("layout", {})})
        path.write_text(
            CHART_HTML.replace("{title}", artifact.title).replace("{figure}", figure),
            encoding="utf-8",
        )
    else:
        path = directory / f"{stem}.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    record_event(
        db, actor="user", event_type="artifact_saved",
        project_id=artifact.project_id, run_id=artifact.run_id,
        payload={"artifact_id": artifact.id, "path": str(path)},
    )
    db.commit()
    return {"status": "saved", "path": str(path)}
