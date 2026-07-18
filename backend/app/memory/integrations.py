"""Memory platform catalog and active-backend selection."""
import json
import logging

from app import models
from app.config import settings
from app.memory.sqlite_backend import SQLiteMemoryBackend

logger = logging.getLogger(__name__)

INTEGRATION_CATALOG = [
    {"name": "builtin", "label": "Built-in (SQLite)", "status": "builtin",
     "note": "Local five-type memory store. Always available."},
    {"name": "mem0", "label": "Mem0", "status": "available",
     "note": "Cloud memory layer. Set MEM0_API_KEY and activate."},
    {"name": "zep", "label": "Zep (Graphiti)", "status": "available",
     "note": "Temporal knowledge graph memory. Set ZEP_API_KEY and activate."},
    {"name": "letta", "label": "Letta (MemGPT)", "status": "configurable",
     "note": "Connect stub — store server URL and key; adapter planned."},
    {"name": "supermemory", "label": "Supermemory", "status": "configurable",
     "note": "Connect stub — adapter planned."},
    {"name": "cognee", "label": "Cognee", "status": "configurable",
     "note": "Connect stub — adapter planned."},
    {"name": "hindsight", "label": "Hindsight", "status": "configurable",
     "note": "Connect stub — adapter planned."},
    {"name": "retaindb", "label": "RetainDB", "status": "configurable",
     "note": "Connect stub — adapter planned."},
    {"name": "everos", "label": "Evermind (EverOS)", "status": "configurable",
     "note": "Connect stub — adapter planned."},
    {"name": "maximem_synap", "label": "Maximem Synap", "status": "configurable",
     "note": "Connect stub — adapter planned."},
    {"name": "supabase", "label": "Supabase", "status": "configurable",
     "note": "Optional cloud sync target. Connect stub — adapter planned."},
]

ACTIVATABLE = {"builtin", "mem0", "zep"}


def load_integration_settings(session_factory) -> dict:
    with session_factory() as s:
        row = s.get(models.AppSetting, "memory_integration")
        stored = json.loads(row.value_json) if row else {}
    return {"active": stored.get("active", "builtin"), "configs": stored.get("configs", {})}


def build_memory_backend(session_factory, active: str | None = None):
    active = active or load_integration_settings(session_factory)["active"]
    try:
        if active == "mem0":
            from app.memory.mem0_backend import Mem0Backend

            return Mem0Backend(settings.mem0_api_key)
        if active == "zep":
            from app.memory.zep_backend import ZepBackend

            return ZepBackend(settings.zep_api_key)
    except Exception as exc:
        logger.warning("Memory backend '%s' unavailable (%s); using builtin", active, exc)
    return SQLiteMemoryBackend(session_factory)
