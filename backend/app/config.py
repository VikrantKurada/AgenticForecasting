"""Application configuration. Secrets live in backend/.env (gitignored), never in the DB."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = f"sqlite:///{(DATA_DIR / 'app.db').as_posix()}"

    # LLM provider keys (optional; presence enables the provider)
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""
    nvidia_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434/v1"

    # Data source keys
    fred_api_key: str = ""
    bls_api_key: str = ""

    # Memory integration keys
    mem0_api_key: str = ""
    zep_api_key: str = ""


settings = Settings()
