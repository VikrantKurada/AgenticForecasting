import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app import models
from app.deps import get_db
from app.events import record_event

router = APIRouter(prefix="/api/settings/mcp", tags=["mcp"])


class MCPServerConfig(BaseModel):
    url: str
    note: str = ""


class MCPSettings(BaseModel):
    servers: dict[str, MCPServerConfig]


@router.get("")
def get_mcp_settings(db=Depends(get_db)):
    row = db.get(models.AppSetting, "mcp_servers")
    return {"servers": json.loads(row.value_json) if row else {}}


@router.put("")
def put_mcp_settings(body: MCPSettings, db=Depends(get_db)):
    value = json.dumps({name: cfg.model_dump() for name, cfg in body.servers.items()})
    row = db.get(models.AppSetting, "mcp_servers")
    if row is None:
        db.add(models.AppSetting(key="mcp_servers", value_json=value))
    else:
        row.value_json = value
    record_event(
        db, actor="user", event_type="mcp_servers_updated",
        payload={"servers": sorted(body.servers)},
    )
    db.commit()
    return {"status": "ok"}
