"""Export artifacts (and whole chats/projects) to files at a user-chosen location."""
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


def _write_artifact(artifact: models.Artifact, directory: Path, filename: str | None = None) -> Path:
    payload = json.loads(artifact.payload_json)
    stem = _safe_name(filename or artifact.title)

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
    return path


def _require_dir(raw: str) -> Path:
    directory = Path(raw).expanduser()
    if not directory.is_dir():
        raise HTTPException(status_code=400, detail=f"Directory does not exist: {directory}")
    return directory


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
    directory = _require_dir(body.directory)
    path = _write_artifact(artifact, directory, body.filename)
    record_event(
        db, actor="user", event_type="artifact_saved",
        project_id=artifact.project_id, run_id=artifact.run_id,
        payload={"artifact_id": artifact.id, "path": str(path)},
    )
    db.commit()
    return {"status": "saved", "path": str(path)}


class ExportRequest(BaseModel):
    directory: str
    folder_name: str | None = None


def _export_chat_into(db, chat: models.Chat, base: Path) -> int:
    base.mkdir(parents=True, exist_ok=True)
    files = 0

    messages = (
        db.query(models.Message)
        .filter_by(chat_id=chat.id)
        .order_by(models.Message.created_at.asc())
        .all()
    )
    lines = [f"# {chat.title}", ""]
    for message in messages:
        speaker = "User" if message.role == "user" else "Assistant"
        lines += [f"**{speaker}** ({message.created_at[:19]}):", "", message.content, "", "---", ""]
    (base / "transcript.md").write_text("\n".join(lines), encoding="utf-8")
    files += 1

    runs = (
        db.query(models.Run)
        .filter_by(chat_id=chat.id)
        .order_by(models.Run.started_at.asc())
        .all()
    )
    for i, run in enumerate(runs, start=1):
        run_dir = base / f"run-{i}-{_safe_name(run.question[:40])}"
        run_dir.mkdir(exist_ok=True)
        artifacts = db.query(models.Artifact).filter_by(run_id=run.id).all()
        for artifact in artifacts:
            _write_artifact(artifact, run_dir)
            files += 1
        events = (
            db.query(models.Event)
            .filter_by(run_id=run.id)
            .order_by(models.Event.ts.asc())
            .all()
        )
        trace = [
            {"type": e.event_type, "actor": e.actor, "span_id": e.span_id,
             "parent_span_id": e.parent_span_id, "payload": json.loads(e.payload_json),
             "ts": e.ts}
            for e in events
        ]
        (run_dir / "trace.json").write_text(
            json.dumps({"question": run.question, "status": run.status, "events": trace},
                       indent=2),
            encoding="utf-8",
        )
        files += 1
    return files


@router.post("/chats/{chat_id}/export")
def export_chat(chat_id: str, body: ExportRequest, db=Depends(get_db)):
    chat = db.get(models.Chat, chat_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found")
    directory = _require_dir(body.directory)
    base = directory / _safe_name(body.folder_name or chat.title)
    files = _export_chat_into(db, chat, base)
    record_event(
        db, actor="user", event_type="chat_exported",
        project_id=chat.project_id, payload={"chat_id": chat.id, "path": str(base)},
    )
    db.commit()
    return {"status": "exported", "path": str(base), "files": files}


@router.post("/projects/{project_id}/export")
def export_project(project_id: str, body: ExportRequest, db=Depends(get_db)):
    project = db.get(models.Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    directory = _require_dir(body.directory)
    base = directory / _safe_name(body.folder_name or project.name)
    base.mkdir(parents=True, exist_ok=True)
    files = 0
    chats = db.query(models.Chat).filter_by(project_id=project_id).all()
    for chat in chats:
        files += _export_chat_into(db, chat, base / _safe_name(chat.title))
    record_event(
        db, actor="user", event_type="project_exported",
        project_id=project_id, payload={"path": str(base), "chats": len(chats)},
    )
    db.commit()
    return {"status": "exported", "path": str(base), "files": files}
