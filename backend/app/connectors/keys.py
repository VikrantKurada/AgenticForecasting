"""Datasource API key resolution: DB-stored keys first, then env (.env) fallback."""
import json
import os

from app import models
from app.config import settings

SETTING_KEY = "datasource_keys"

# Sources whose env fallback comes from typed Settings fields
_ENV_SETTINGS_FIELDS = {"fred": "fred_api_key", "bls": "bls_api_key"}


def load_stored_keys(session_factory) -> dict[str, str]:
    with session_factory() as s:
        row = s.get(models.AppSetting, SETTING_KEY)
        return json.loads(row.value_json) if row else {}


def save_stored_keys(session, keys: dict[str, str]) -> dict[str, str]:
    row = session.get(models.AppSetting, SETTING_KEY)
    stored = json.loads(row.value_json) if row else {}
    for name, value in keys.items():
        value = (value or "").strip()
        if value:
            stored[name] = value
        else:
            stored.pop(name, None)
    payload = json.dumps(stored)
    if row is None:
        session.add(models.AppSetting(key=SETTING_KEY, value_json=payload))
    else:
        row.value_json = payload
    return stored


def get_datasource_key(session_factory, name: str) -> str:
    stored = load_stored_keys(session_factory)
    if stored.get(name):
        return stored[name]
    field = _ENV_SETTINGS_FIELDS.get(name)
    if field:
        return getattr(settings, field, "") or ""
    return os.environ.get(f"{name.upper()}_API_KEY", "")


def mask(value: str) -> str:
    if not value:
        return ""
    tail = value[-4:] if len(value) > 4 else value
    return "••••" + tail
