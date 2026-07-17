"""Provider chain with fallback, token ledger, and telemetry."""
import logging

from app import models
from app.events import record_event
from app.llm.base import LLMAdapter, LLMResponse, LLMUnavailable

logger = logging.getLogger(__name__)

# USD per million tokens (input, output). Prefix-matched, longest prefix wins.
# Local/free providers cost 0; unknown models estimate at 0.
PRICES: dict[tuple[str, str], tuple[float, float]] = {
    ("anthropic", "claude-fable-5"): (10.0, 50.0),
    ("anthropic", "claude-opus"): (5.0, 25.0),
    ("anthropic", "claude-sonnet"): (3.0, 15.0),
    ("anthropic", "claude-haiku"): (1.0, 5.0),
    ("openai", "gpt-4o-mini"): (0.15, 0.6),
    ("openai", "gpt-4o"): (2.5, 10.0),
    ("openai", "gpt-4.1"): (2.0, 8.0),
    ("openai", "gpt-5"): (1.25, 10.0),
    ("gemini", "gemini-2.5-pro"): (1.25, 10.0),
    ("gemini", "gemini-2.5-flash"): (0.3, 2.5),
}


def estimate_cost(provider: str, model: str, input_tokens: int, output_tokens: int) -> float:
    best: tuple[float, float] | None = None
    best_len = -1
    for (prov, prefix), rates in PRICES.items():
        if prov == provider and model.startswith(prefix) and len(prefix) > best_len:
            best, best_len = rates, len(prefix)
    if best is None:
        return 0.0
    return (input_tokens * best[0] + output_tokens * best[1]) / 1_000_000


class LLMRegistry:
    """Walks a (provider, model) chain, records usage, falls back on failure."""

    def __init__(
        self,
        session_factory,
        adapters: dict[str, LLMAdapter],
        chain: list[tuple[str, str]],
    ):
        self.session_factory = session_factory
        self.adapters = adapters
        self.chain = chain

    def complete(
        self,
        system: str,
        messages: list[dict],
        *,
        project_id: str | None = None,
        run_id: str | None = None,
        agent_role: str = "",
        json_mode: bool = False,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
    ) -> LLMResponse:
        errors: list[str] = []
        for provider, model in self.chain:
            adapter = self.adapters.get(provider)
            if adapter is None:
                errors.append(f"{provider}: not configured")
                continue
            try:
                resp = adapter.complete(system, messages, model=model, json_mode=json_mode)
            except Exception as exc:
                errors.append(f"{provider}/{model}: {exc}")
                logger.warning("LLM provider %s failed: %s", provider, exc)
                with self.session_factory() as s:
                    record_event(
                        s, actor="system", event_type="llm_error",
                        project_id=project_id, run_id=run_id,
                        trace_id=trace_id, parent_span_id=parent_span_id,
                        payload={"provider": provider, "model": model, "error": str(exc)},
                    )
                    s.commit()
                continue

            cost = estimate_cost(resp.provider, resp.model, resp.input_tokens, resp.output_tokens)
            with self.session_factory() as s:
                s.add(
                    models.TokenUsage(
                        project_id=project_id, run_id=run_id,
                        provider=resp.provider, model=resp.model, agent_role=agent_role,
                        input_tokens=resp.input_tokens, output_tokens=resp.output_tokens,
                        est_cost_usd=cost,
                    )
                )
                record_event(
                    s, actor="system", event_type="llm_call",
                    project_id=project_id, run_id=run_id,
                    trace_id=trace_id, parent_span_id=parent_span_id,
                    payload={
                        "provider": resp.provider, "model": resp.model,
                        "agent_role": agent_role,
                        "input_tokens": resp.input_tokens,
                        "output_tokens": resp.output_tokens,
                        "est_cost_usd": cost,
                    },
                )
                s.commit()
            return resp

        raise LLMUnavailable(
            "All configured LLM providers failed: " + "; ".join(errors or ["no providers"])
        )
