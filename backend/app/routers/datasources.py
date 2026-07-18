from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.connectors.catalog import SOURCE_BY_NAME
from app.connectors.keys import load_stored_keys, mask, save_stored_keys
from app.connectors.registry import build_connectors, datasource_catalog
from app.deps import get_db
from app.events import record_event

router = APIRouter(prefix="/api", tags=["datasources"])


@router.get("/datasources")
def list_datasources(request: Request):
    return datasource_catalog(request.app.state.session_factory)


@router.get("/settings/datasource-keys")
def get_keys(request: Request):
    stored = load_stored_keys(request.app.state.session_factory)
    return {
        name: {"present": name in stored, "masked": mask(stored.get(name, ""))}
        for name in SOURCE_BY_NAME
    }


class KeysUpdate(BaseModel):
    keys: dict[str, str]


@router.put("/settings/datasource-keys")
def put_keys(body: KeysUpdate, request: Request, db=Depends(get_db)):
    known = {name: value for name, value in body.keys.items() if name in SOURCE_BY_NAME}
    save_stored_keys(db, known)
    record_event(
        db, actor="user", event_type="datasource_keys_updated",
        payload={"sources": sorted(known)},
    )
    db.commit()
    request.app.state.connectors = build_connectors(request.app.state.session_factory)
    return {"status": "ok"}
