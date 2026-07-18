from fastapi import APIRouter, Depends, HTTPException

from app import models, schemas
from app.deps import get_db
from app.events import record_event

router = APIRouter(prefix="/api", tags=["chats"])


def _chat_or_404(db, chat_id: str) -> models.Chat:
    chat = db.get(models.Chat, chat_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found")
    return chat


@router.post("/projects/{project_id}/chats", status_code=201, response_model=schemas.ChatOut)
def create_chat(project_id: str, body: schemas.ChatCreate, db=Depends(get_db)):
    if db.get(models.Project, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    chat = models.Chat(project_id=project_id, title=body.title)
    db.add(chat)
    db.flush()
    record_event(
        db, actor="user", event_type="chat_created",
        project_id=project_id, payload={"chat_id": chat.id, "title": chat.title},
    )
    db.commit()
    return chat


@router.get("/projects/{project_id}/chats", response_model=list[schemas.ChatOut])
def list_chats(project_id: str, db=Depends(get_db)):
    return (
        db.query(models.Chat)
        .filter_by(project_id=project_id)
        .order_by(models.Chat.updated_at.desc())
        .all()
    )


@router.get("/chats/{chat_id}", response_model=schemas.ChatOut)
def get_chat(chat_id: str, db=Depends(get_db)):
    return _chat_or_404(db, chat_id)


@router.patch("/chats/{chat_id}", response_model=schemas.ChatOut)
def rename_chat(chat_id: str, body: schemas.ChatCreate, db=Depends(get_db)):
    chat = _chat_or_404(db, chat_id)
    chat.title = body.title.strip() or chat.title
    record_event(
        db, actor="user", event_type="chat_renamed",
        project_id=chat.project_id, payload={"chat_id": chat.id, "title": chat.title},
    )
    db.commit()
    return chat


@router.delete("/chats/{chat_id}", status_code=204)
def delete_chat(chat_id: str, db=Depends(get_db)):
    chat = _chat_or_404(db, chat_id)
    record_event(
        db, actor="user", event_type="chat_deleted",
        project_id=chat.project_id, payload={"chat_id": chat.id},
    )
    db.delete(chat)
    db.commit()


@router.get("/chats/{chat_id}/messages", response_model=list[schemas.MessageOut])
def list_messages(chat_id: str, db=Depends(get_db)):
    _chat_or_404(db, chat_id)
    return (
        db.query(models.Message)
        .filter_by(chat_id=chat_id)
        .order_by(models.Message.created_at.asc())
        .all()
    )
