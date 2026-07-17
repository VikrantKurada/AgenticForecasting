from app.llm.base import LLMResponse

JSON_SUFFIX = "\n\nRespond with valid JSON only. No code fences, no prose outside the JSON."


class AnthropicAdapter:
    provider = "anthropic"

    def __init__(self, api_key: str):
        import anthropic

        self.client = anthropic.Anthropic(api_key=api_key)

    def complete(self, system, messages, model="claude-opus-4-8", json_mode=False):
        if json_mode:
            system = system + JSON_SUFFIX
        response = self.client.messages.create(
            model=model,
            max_tokens=8192,
            system=system,
            messages=messages,
        )
        text = "".join(block.text for block in response.content if block.type == "text")
        return LLMResponse(
            text=text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model=model,
            provider=self.provider,
        )
