from app.llm.base import LLMResponse


class GeminiAdapter:
    provider = "gemini"

    def __init__(self, api_key: str):
        from google import genai

        self.client = genai.Client(api_key=api_key)

    def complete(self, system, messages, model="gemini-2.5-flash", json_mode=False):
        from google.genai import types

        contents = []
        for m in messages:
            role = "model" if m["role"] == "assistant" else "user"
            contents.append(types.Content(role=role, parts=[types.Part(text=str(m["content"]))]))
        config = types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json" if json_mode else None,
        )
        response = self.client.models.generate_content(
            model=model, contents=contents, config=config
        )
        usage = response.usage_metadata
        return LLMResponse(
            text=response.text or "",
            input_tokens=getattr(usage, "prompt_token_count", 0) or 0,
            output_tokens=getattr(usage, "candidates_token_count", 0) or 0,
            model=model,
            provider=self.provider,
        )
