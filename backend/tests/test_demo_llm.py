import pytest

from app import models
from app.agents.engine.events import RunEventBus
from app.agents.engine.executor import execute_run
from app.db import init_db, make_engine, make_session_factory
from app.llm.demo import DemoLLM
from app.llm.registry import LLMRegistry
from app.memory.service import MemoryService
from app.memory.sqlite_backend import SQLiteMemoryBackend
from tests.test_tools import FakeConnector


@pytest.fixture
def env(tmp_path):
    engine = make_engine(f"sqlite:///{(tmp_path / 'demo.db').as_posix()}")
    init_db(engine)
    factory = make_session_factory(engine)
    with factory() as s:
        project = models.Project(name="P")
        s.add(project)
        s.flush()
        chat = models.Chat(project_id=project.id, title="c")
        s.add(chat)
        s.flush()
        run = models.Run(
            chat_id=chat.id, project_id=project.id,
            question="Nowcast US GDP growth", status="planning",
        )
        s.add(run)
        s.commit()
        ids = {"run": run.id}
    return factory, ids


def test_demo_llm_completes_a_full_run_with_artifacts(env):
    factory, ids = env
    llm = LLMRegistry(factory, adapters={"demo": DemoLLM()}, chain=[("demo", "demo-1")])
    memory = MemoryService(SQLiteMemoryBackend(factory), factory)

    outcome = execute_run(
        ids["run"], session_factory=factory, llm=llm,
        connectors={"worldbank": FakeConnector()}, memory=memory, bus=RunEventBus(),
    )

    assert outcome["status"] == "completed"
    assert "demo" in outcome["summary"].lower()
    with factory() as s:
        artifacts = s.query(models.Artifact).filter_by(run_id=ids["run"]).all()
        kinds = {a.kind for a in artifacts}
        assert "chart" in kinds
        assert "report" in kinds
        charts = [a for a in artifacts if a.kind == "chart"]
        assert len(charts) >= 4  # fan, model_compare, backtest, decomposition, distribution
