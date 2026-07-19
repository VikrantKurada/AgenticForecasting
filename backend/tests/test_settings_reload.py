from app.config import reload_settings, settings
from app.llm.builder import provider_key_present


def test_reload_settings_picks_up_env_change(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test-abc123")
    reload_settings()
    assert settings.nvidia_api_key == "nvapi-test-abc123"
    assert provider_key_present("nvidia") is True


def test_reload_settings_clears_removed_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g-123")
    reload_settings()
    assert settings.gemini_api_key == "g-123"
    monkeypatch.delenv("GEMINI_API_KEY")
    reload_settings()
    # falls back to whatever backend/.env holds (empty in CI, never "g-123")
    assert settings.gemini_api_key != "g-123"
