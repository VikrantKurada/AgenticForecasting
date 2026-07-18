import json

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app import models
from app.deps import get_db
from app.events import record_event
from app.memory.integrations import (
    ACTIVATABLE,
    INTEGRATION_CATALOG,
    build_memory_backend,
    load_integration_settings,
)

router = APIRouter(prefix="/api/settings/integrations", tags=["integrations"])


class IntegrationUpdate(BaseModel):
    active: str | None = None
    configs: dict | None = None


@router.get("")
def get_integrations(request: Request):
    cfg = load_integration_settings(request.app.state.session_factory)
    return {"active": cfg["active"], "configs": cfg["configs"], "integrations": INTEGRATION_CATALOG}


@router.put("")
def update_integrations(body: IntegrationUpdate, request: Request, db=Depends(get_db)):
    known = {i["name"] for i in INTEGRATION_CATALOG}
    if body.active is not None and body.active not in known:
        raise HTTPException(status_code=400, detail=f"Unknown integration '{body.active}'")
    if body.active is not None and body.active not in ACTIVATABLE:
        raise HTTPException(
            status_code=400,
            detail=f"'{body.active}' can store connection config but its adapter "
            "is not yet implemented. Activatable: builtin, mem0, zep.",
        )
    row = db.get(models.AppSetting, "memory_integration")
    stored = json.loads(row.value_json) if row else {}
    if body.active is not None:
        stored["active"] = body.active
    if body.configs is not None:
        stored.setdefault("configs", {}).update(body.configs)
    if row is None:
        db.add(models.AppSetting(key="memory_integration", value_json=json.dumps(stored)))
    else:
        row.value_json = json.dumps(stored)
    record_event(
        db, actor="user", event_type="memory_integration_updated",
        payload={"active": stored.get("active")},
    )
    db.commit()
    request.app.state.memory_backend = build_memory_backend(request.app.state.session_factory)
    return {"status": "ok", "active": stored.get("active", "builtin")}


@router.post("/test")
def test_integration(request: Request):
    backend = build_memory_backend(request.app.state.session_factory)
    try:
        backend.search("connectivity test", limit=1)
        return {"status": "ok", "backend": backend.name}
    except Exception as exc:
        return {"status": "error", "backend": backend.name, "detail": str(exc)}
