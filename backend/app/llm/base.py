from dataclasses import dataclass
from typing import Protocol


@dataclass
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    model: str
    provider: str


class LLMUnavailable(Exception):
    """Raised when every configured provider in the chain failed."""


class LLMAdapter(Protocol):
    provider: str

    def complete(
        self,
        system: str,
        messages: list[dict],
        model: str,
        json_mode: bool = False,
    ) -> LLMResponse: ...
