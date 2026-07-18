import json

import pytest

from app import models
from app.db import init_db, make_engine, make_session_factory
from app.memory.service import MemoryService
from app.memory.sqlite_backend import SQLiteMemoryBackend


@pytest.fixture
def factory(tmp_path):
    engine = make_engine(f"sqlite:///{(tmp_path / 'mem.db').as_posix()}")
    init_db(engine)
    return make_session_factory(engine)


@pytest.fixture
def backend(factory):
    return SQLiteMemoryBackend(factory)


def test_add_and_get_recent_filters_by_type_and_project(backend):
    backend.add("semantic", "GDPC1 is real US GDP, quarterly, from FRED", project_id="p1")
    backend.add("episodic", "Ran a nowcast for Q3", project_id="p1")
    backend.add("semantic", "HICP is euro area inflation", project_id="p2")

    items = backend.get_recent("semantic", project_id="p1")
    assert len(items) == 1
    assert "GDPC1" in items[0].content


def test_get_recent_returns_newest_first(backend):
    for i in range(5):
        backend.add("episodic", f"episode {i}", project_id="p1")
    items = backend.get_recent("episodic", project_id="p1", limit=3)
    assert len(items) == 3
    assert items[0].content == "episode 4"


def test_semantic_search_ranks_relevant_content_first(backend):
    backend.add("semantic", "The FRED series GDPC1 measures real gross domestic product")
    backend.add("semantic", "Ollama runs large language models locally")
    backend.add("semantic", "HICP measures consumer price inflation in the euro area")

    hits = backend.search("inflation consumer prices euro")
    assert hits
    assert "HICP" in hits[0].content


def test_delete_removes_item(backend):
    item_id = backend.add("procedural", "workflow template", key="nowcast")
    backend.delete(item_id)
    assert backend.get_recent("procedural") == []


def test_memory_persists_across_backend_instances(factory):
    SQLiteMemoryBackend(factory).add("semantic", "persistent fact", project_id="p1")
    fresh = SQLiteMemoryBackend(factory)
    assert fresh.get_recent("semantic", project_id="p1")[0].content == "persistent fact"


def test_service_remember_episode_and_procedure(factory):
    service = MemoryService(SQLiteMemoryBackend(factory), factory)
    service.remember_episode(
        project_id="p1", question="Nowcast US GDP",
        plan={"kind": "nowcast"}, outcome="completed", metrics={"rmse": 0.4},
    )
    episodes = service.backend.get_recent("episodic", project_id="p1")
    assert len(episodes) == 1
    payload = json.loads(episodes[0].content)
    assert payload["question"] == "Nowcast US GDP"

    service.remember_procedure("nowcast", {"nodes": []}, project_id="p1")
    procedures = service.procedures_for("nowcast", project_id="p1")
    assert len(procedures) == 1


def test_service_short_term_reads_chat_messages(factory):
    with factory() as s:
        project = models.Project(name="P")
        s.add(project)
        s.flush()
        chat = models.Chat(project_id=project.id, title="c")
        s.add(chat)
        s.flush()
        for i in range(4):
            s.add(models.Message(chat_id=chat.id, role="user", content=f"msg {i}"))
        s.commit()
        chat_id = chat.id

    service = MemoryService(SQLiteMemoryBackend(factory), factory)
    window = service.short_term(chat_id, limit=2)
    assert [m["content"] for m in window] == ["msg 2", "msg 3"]
