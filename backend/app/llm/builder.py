"""Builds the LLM registry from env keys + persisted provider settings."""
import json

from app import models
from app.config import settings
from app.llm.fake import FakeLLM
from app.llm.registry import LLMRegistry

DEFAULT_MODELS = {
    "anthropic": "claude-opus-4-8",
    "openai": "gpt-4o",
    "gemini": "gemini-2.5-flash",
    "nvidia": "meta/llama-3.3-70b-instruct",
    "ollama": "llama3.2",
}
DEFAULT_ORDER = ["anthropic", "openai", "gemini", "nvidia", "ollama"]
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"


def provider_key_present(name: str) -> bool:
    return {
        "anthropic": bool(settings.anthropic_api_key),
        "openai": bool(settings.openai_api_key),
        "gemini": bool(settings.gemini_api_key),
        "nvidia": bool(settings.nvidia_api_key),
        "ollama": True,  # local; reachability checked at call time
        "fake": True,
    }.get(name, False)


def load_provider_settings(session_factory) -> dict:
    with session_factory() as s:
        row = s.get(models.AppSetting, "providers")
        stored = json.loads(row.value_json) if row else {}
    order = [p for p in stored.get("order", DEFAULT_ORDER) if p in DEFAULT_ORDER or p == "fake"]
    models_map = {**DEFAULT_MODELS, **stored.get("models", {})}
    enabled = stored.get("enabled", {})
    return {"order": order or DEFAULT_ORDER, "models": models_map, "enabled": enabled}


def _make_adapter(name: str):
    if name == "fake":
        return FakeLLM()
    if name == "anthropic":
        from app.llm.anthropic_adapter import AnthropicAdapter

        return AnthropicAdapter(settings.anthropic_api_key)
    if name == "gemini":
        from app.llm.gemini_adapter import GeminiAdapter

        return GeminiAdapter(settings.gemini_api_key)
    from app.llm.openai_adapter import OpenAICompatAdapter

    if name == "openai":
        return OpenAICompatAdapter("openai", settings.openai_api_key)
    if name == "nvidia":
        return OpenAICompatAdapter("nvidia", settings.nvidia_api_key, NVIDIA_BASE_URL)
    if name == "ollama":
        return OpenAICompatAdapter("ollama", "", settings.ollama_base_url)
    raise ValueError(f"Unknown provider: {name}")


def build_registry(session_factory) -> LLMRegistry:
    cfg = load_provider_settings(session_factory)
    adapters: dict = {}
    chain: list[tuple[str, str]] = []
    for name in cfg["order"]:
        if not provider_key_present(name):
            continue
        if cfg["enabled"].get(name, True) is False:
            continue
        try:
            adapters[name] = _make_adapter(name)
        except Exception:
            continue
        chain.append((name, cfg["models"][name] if name != "fake" else "fake-1"))
    # Deterministic last resort so the app always produces a (clearly labeled)
    # demo forecast even when no provider is reachable.
    from app.llm.demo import DemoLLM

    adapters["demo"] = DemoLLM()
    chain.append(("demo", "demo-1"))
    return LLMRegistry(session_factory, adapters=adapters, chain=chain)
