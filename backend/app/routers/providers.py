import json

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app import models
from app.deps import get_db
from app.events import record_event
from app.llm.builder import (
    DEFAULT_MODELS,
    DEFAULT_ORDER,
    build_registry,
    load_provider_settings,
    provider_key_present,
)

router = APIRouter(prefix="/api/settings/providers", tags=["providers"])


class ProviderSettingsUpdate(BaseModel):
    order: list[str] | None = None
    models: dict[str, str] | None = None
    enabled: dict[str, bool] | None = None


@router.get("")
def get_providers(request: Request, db=Depends(get_db)):
    cfg = load_provider_settings(request.app.state.session_factory)
    return {
        "order": cfg["order"],
        "providers": [
            {
                "name": name,
                "configured": provider_key_present(name),
                "model": cfg["models"].get(name, DEFAULT_MODELS.get(name, "")),
                "enabled": cfg["enabled"].get(name, True),
            }
            for name in DEFAULT_ORDER
        ],
    }


@router.put("")
def update_providers(body: ProviderSettingsUpdate, request: Request, db=Depends(get_db)):
    row = db.get(models.AppSetting, "providers")
    stored = json.loads(row.value_json) if row else {}
    for field in ("order", "models", "enabled"):
        value = getattr(body, field)
        if value is not None:
            stored[field] = value
    if row is None:
        db.add(models.AppSetting(key="providers", value_json=json.dumps(stored)))
    else:
        row.value_json = json.dumps(stored)
    record_event(db, actor="user", event_type="provider_settings_updated", payload=stored)
    db.commit()
    request.app.state.llm_registry = build_registry(request.app.state.session_factory)
    return {"status": "ok"}


class ProviderTest(BaseModel):
    provider: str


@router.post("/test")
def test_provider(body: ProviderTest, request: Request):
    from app.llm.builder import _make_adapter

    cfg = load_provider_settings(request.app.state.session_factory)
    if not provider_key_present(body.provider):
        raise HTTPException(status_code=400, detail=f"{body.provider}: no API key configured")
    try:
        adapter = _make_adapter(body.provider)
        resp = adapter.complete(
            "You are a health check. Reply with the single word: ok",
            [{"role": "user", "content": "ping"}],
            model=cfg["models"].get(body.provider, ""),
        )
        return {"status": "ok", "model": resp.model, "reply": resp.text[:100]}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}
