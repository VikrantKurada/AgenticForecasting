"""OpenAI-compatible adapter. Covers OpenAI, NVIDIA NIM, and Ollama via base_url."""
from app.llm.base import LLMResponse


class OpenAICompatAdapter:
    def __init__(self, provider: str, api_key: str, base_url: str | None = None):
        from openai import OpenAI

        self.provider = provider
        self.client = OpenAI(api_key=api_key or "not-needed", base_url=base_url)

    def complete(self, system, messages, model, json_mode=False):
        kwargs = {}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        full_messages = [{"role": "system", "content": system}, *messages]
        try:
            response = self.client.chat.completions.create(
                model=model, messages=full_messages, **kwargs
            )
        except Exception:
            if not json_mode:
                raise
            # Some compatible endpoints reject response_format; retry without it.
            response = self.client.chat.completions.create(model=model, messages=full_messages)
        usage = response.usage
        return LLMResponse(
            text=response.choices[0].message.content or "",
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
            model=model,
            provider=self.provider,
        )
