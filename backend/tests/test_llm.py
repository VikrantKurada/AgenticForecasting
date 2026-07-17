import pytest

from app import models
from app.db import init_db, make_engine, make_session_factory
from app.llm.base import LLMUnavailable
from app.llm.fake import FakeLLM
from app.llm.registry import LLMRegistry, estimate_cost


@pytest.fixture
def factory(tmp_path):
    engine = make_engine(f"sqlite:///{(tmp_path / 'llm.db').as_posix()}")
    init_db(engine)
    return make_session_factory(engine)


def test_fake_llm_returns_scripted_responses_in_order():
    fake = FakeLLM(["first", "second"])
    r1 = fake.complete("sys", [{"role": "user", "content": "hi"}], model="fake-1")
    assert r1.text == "first"
    assert r1.provider == "fake"
    assert r1.input_tokens > 0
    r2 = fake.complete("sys", [], model="fake-1")
    assert r2.text == "second"


def test_registry_records_token_usage_row(factory):
    reg = LLMRegistry(factory, adapters={"fake": FakeLLM(["hello"])}, chain=[("fake", "fake-1")])
    resp = reg.complete(
        "sys", [{"role": "user", "content": "q"}],
        project_id="p1", run_id="r1", agent_role="planner",
    )
    assert resp.text == "hello"
    with factory() as s:
        row = s.query(models.TokenUsage).one()
        assert row.provider == "fake"
        assert row.agent_role == "planner"
        assert row.project_id == "p1"
        assert row.run_id == "r1"
        assert row.output_tokens > 0


class BoomAdapter:
    provider = "boom"

    def complete(self, system, messages, model, json_mode=False):
        raise RuntimeError("provider down")


def test_registry_falls_back_to_next_provider(factory):
    reg = LLMRegistry(
        factory,
        adapters={"boom": BoomAdapter(), "fake": FakeLLM(["saved"])},
        chain=[("boom", "x-1"), ("fake", "fake-1")],
    )
    resp = reg.complete("sys", [], project_id="p1")
    assert resp.text == "saved"
    assert resp.provider == "fake"
    with factory() as s:
        types = [e.event_type for e in s.query(models.Event).all()]
        assert "llm_error" in types
        assert "llm_call" in types


def test_registry_raises_when_all_providers_fail(factory):
    reg = LLMRegistry(factory, adapters={"boom": BoomAdapter()}, chain=[("boom", "x-1")])
    with pytest.raises(LLMUnavailable):
        reg.complete("sys", [])


def test_cost_estimates():
    assert estimate_cost("anthropic", "claude-opus-4-8", 1_000_000, 0) == pytest.approx(5.0)
    assert estimate_cost("anthropic", "claude-opus-4-8", 0, 1_000_000) == pytest.approx(25.0)
    assert estimate_cost("ollama", "llama3.2", 5000, 5000) == 0.0
    assert estimate_cost("unknown", "mystery-model", 1000, 1000) == 0.0
