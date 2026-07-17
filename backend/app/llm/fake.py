"""Scripted fake adapter for tests and offline demo mode."""
from app.llm.base import LLMResponse


class FakeLLM:
    provider = "fake"

    def __init__(self, responses: list[str] | None = None):
        self.responses = list(responses or [])
        self.calls: list[dict] = []

    def complete(self, system, messages, model="fake-1", json_mode=False):
        self.calls.append(
            {"system": system, "messages": messages, "model": model, "json_mode": json_mode}
        )
        text = self.responses.pop(0) if self.responses else "ok"
        prompt_chars = len(system) + sum(len(str(m.get("content", ""))) for m in messages)
        return LLMResponse(
            text=text,
            input_tokens=max(1, prompt_chars // 4),
            output_tokens=max(1, len(text) // 4),
            model=model,
            provider=self.provider,
        )
