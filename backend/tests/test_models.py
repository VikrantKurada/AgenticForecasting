from app import models
from app.db import init_db, make_engine, make_session_factory


def make_session(tmp_path):
    engine = make_engine(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    init_db(engine)
    return make_session_factory(engine)


def test_all_tables_roundtrip(tmp_path):
    Session = make_session(tmp_path)
    with Session() as s:
        p = models.Project(name="US Macro", description="US GDP work")
        s.add(p)
        s.flush()
        c = models.Chat(project_id=p.id, title="Q3 nowcast")
        s.add(c)
        s.flush()
        r = models.Run(chat_id=c.id, project_id=p.id, question="Nowcast US GDP", status="planning")
        s.add(r)
        s.flush()
        s.add_all(
            [
                models.Message(chat_id=c.id, role="user", content="hello", run_id=r.id),
                models.Artifact(run_id=r.id, project_id=p.id, kind="chart", title="Fan chart", payload_json="{}"),
                models.Event(
                    project_id=p.id, run_id=r.id, trace_id="tr1", span_id="sp1",
                    parent_span_id=None, actor="agent:modeler", event_type="node_started", payload_json="{}",
                ),
                models.TokenUsage(
                    project_id=p.id, run_id=r.id, provider="fake", model="fake-1",
                    agent_role="planner", input_tokens=10, output_tokens=20, est_cost_usd=0.001,
                ),
                models.MemoryItem(project_id=p.id, mem_type="semantic", content="GDPC1 is real US GDP"),
                models.SeriesCache(source="fred", series_key="GDPC1", params_hash="abc", payload_json="{}"),
                models.ResourceSample(project_id=p.id, run_id=r.id, cpu_percent=12.5, mem_percent=40.0),
                models.AppSetting(key="providers", value_json="{}"),
            ]
        )
        s.commit()

    with Session() as s:
        assert s.query(models.Project).count() == 1
        proj = s.query(models.Project).one()
        assert len(proj.id) == 32  # uuid4 hex
        assert proj.created_at is not None
        assert s.query(models.Chat).one().project_id == proj.id
        assert s.query(models.Message).one().role == "user"
        assert s.query(models.Run).one().status == "planning"
        assert s.query(models.Artifact).one().kind == "chart"
        assert s.query(models.Event).one().actor == "agent:modeler"
        assert s.query(models.TokenUsage).one().output_tokens == 20
        assert s.query(models.MemoryItem).one().mem_type == "semantic"
        assert s.query(models.SeriesCache).one().series_key == "GDPC1"
        assert s.query(models.ResourceSample).one().cpu_percent == 12.5
        assert s.query(models.AppSetting).get is not None


def test_deleting_project_cascades(tmp_path):
    Session = make_session(tmp_path)
    with Session() as s:
        p = models.Project(name="Temp")
        s.add(p)
        s.flush()
        c = models.Chat(project_id=p.id, title="t")
        s.add(c)
        s.flush()
        s.add(models.Message(chat_id=c.id, role="user", content="x"))
        s.commit()
        pid = p.id

    with Session() as s:
        s.delete(s.get(models.Project, pid))
        s.commit()

    with Session() as s:
        assert s.query(models.Chat).count() == 0
        assert s.query(models.Message).count() == 0
