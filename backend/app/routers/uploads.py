"""Attach CSV/Excel/TSV/JSON data files to chats and projects."""
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from app import models
from app.config import DATA_DIR
from app.connectors.uploads import SUPPORTED_EXTENSIONS, analyze_dataframe, read_dataframe
from app.deps import get_db
from app.events import record_event

router = APIRouter(prefix="/api", tags=["uploads"])

UPLOAD_DIR = DATA_DIR / "uploads"
MAX_BYTES = 25 * 1024 * 1024


def _file_out(file: models.UploadedFile) -> dict:
    return {
        "id": file.id,
        "project_id": file.project_id,
        "chat_id": file.chat_id,
        "scope": "chat" if file.chat_id else "project",
        "filename": file.filename,
        "columns": json.loads(file.columns_json or "{}"),
        "n_rows": file.n_rows,
        "created_at": file.created_at,
    }


def _store_upload(db, upload: UploadFile, *, project_id: str, chat_id: str | None) -> dict:
    suffix = Path(upload.filename or "upload").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Supported: {SUPPORTED_EXTENSIONS}",
        )
    content = upload.file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=400, detail="File too large (25 MB limit)")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    row = models.UploadedFile(
        project_id=project_id, chat_id=chat_id,
        filename=upload.filename or f"upload{suffix}", stored_path="",
    )
    stored_path = UPLOAD_DIR / f"{row.id}{suffix}"
    stored_path.write_bytes(content)
    row.stored_path = str(stored_path)

    try:
        df = read_dataframe(stored_path)
        columns = analyze_dataframe(df)
    except HTTPException:
        raise
    except Exception as exc:
        stored_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Could not parse file: {exc}")
    if not columns["numeric_columns"]:
        stored_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400, detail="No numeric columns found — nothing to forecast with."
        )

    row.columns_json = json.dumps(columns)
    row.n_rows = len(df)
    db.add(row)
    record_event(
        db, actor="user", event_type="file_uploaded", project_id=project_id,
        payload={"file_id": row.id, "filename": row.filename,
                 "chat_id": chat_id, "n_rows": row.n_rows},
    )
    db.commit()
    return _file_out(row)


@router.post("/chats/{chat_id}/files")
def upload_chat_file(chat_id: str, file: UploadFile, db=Depends(get_db)):
    chat = db.get(models.Chat, chat_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found")
    return _store_upload(db, file, project_id=chat.project_id, chat_id=chat_id)


@router.post("/projects/{project_id}/files")
def upload_project_file(project_id: str, file: UploadFile, db=Depends(get_db)):
    if db.get(models.Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return _store_upload(db, file, project_id=project_id, chat_id=None)


@router.get("/chats/{chat_id}/files")
def list_chat_files(chat_id: str, db=Depends(get_db)):
    chat = db.get(models.Chat, chat_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found")
    rows = (
        db.query(models.UploadedFile)
        .filter(
            (models.UploadedFile.chat_id == chat_id)
            | ((models.UploadedFile.project_id == chat.project_id)
               & (models.UploadedFile.chat_id.is_(None)))
        )
        .order_by(models.UploadedFile.created_at.asc())
        .all()
    )
    return [_file_out(r) for r in rows]


@router.get("/projects/{project_id}/files")
def list_project_files(project_id: str, db=Depends(get_db)):
    rows = (
        db.query(models.UploadedFile)
        .filter_by(project_id=project_id)
        .order_by(models.UploadedFile.created_at.asc())
        .all()
    )
    return [_file_out(r) for r in rows]


@router.delete("/files/{file_id}", status_code=204)
def delete_file(file_id: str, db=Depends(get_db)):
    row = db.get(models.UploadedFile, file_id)
    if row is None:
        raise HTTPException(status_code=404, detail="File not found")
    Path(row.stored_path).unlink(missing_ok=True)
    record_event(
        db, actor="user", event_type="file_deleted", project_id=row.project_id,
        payload={"file_id": row.id, "filename": row.filename},
    )
    db.delete(row)
    db.commit()
