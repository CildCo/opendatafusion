import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from odf.assets.service import create_asset, publish_asset
from odf.db import Base
from odf.models import Datasource, Job, PipelineNodeRun
from odf.pipeline.runner import PipelineRunError, execute_pipeline
from odf.services.crypto import encrypt_secret


@pytest.fixture()
def s(tmp_path):
    url = "sqlite:///" + str(tmp_path / "runner.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table t (id int, v text)"))
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    with sessionmaker(bind=e)() as sess:
        sess.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                            dsn_encrypted=encrypt_secret(url)))
        sess.commit()
        yield sess


def test_runner_executes_dag(s, monkeypatch):
    class FakeSource:
        def read(self, cursor, limit):
            return [{"id": 1, "v": "a"}, {"id": 2, "v": "b"}], '["2","2"]'

    wrote = {}

    class FakeSink:
        def write(self, rows):
            wrote["rows"] = rows
            return len(rows)

    monkeypatch.setattr("odf.pipeline.nodes.source.source_for",
                        lambda ds, dag: FakeSource())
    monkeypatch.setattr("odf.pipeline.nodes.sink.sink_for",
                        lambda ds, dag: FakeSink())

    content = {"nodes": [
        {"id": "src", "type": "source",
         "config": {"datasource_id": 1, "table": "t", "pk": "id"}},
        {"id": "f", "type": "filter",
         "config": {"conditions": [{"column": "id", "op": ">", "value": 1}]}},
        {"id": "sink", "type": "sink",
         "config": {"datasource_id": 1, "table": "t", "pk": ["id"]}}],
        "edges": [{"from": "src", "to": "f"}, {"from": "f", "to": "sink"}],
        "settings": {"batch": 10}}
    a = create_asset(s, 1, "pipeline", "p", content, "admin")
    publish_asset(s, a.id, "admin")
    job = Job(asset_id=a.id, asset_type="pipeline", status="running")
    s.add(job)
    s.commit()
    s.refresh(job)

    result = execute_pipeline(s, a.id, job.id)
    assert result["node_stats"]["f"]["rows"] == 1
    assert len(wrote["rows"]) == 1
    assert s.query(PipelineNodeRun).filter_by(job_id=job.id).count() == 3


def _content(datasource_id=1):
    return {"nodes": [
        {"id": "src", "type": "source",
         "config": {"datasource_id": datasource_id, "table": "t",
                    "pk": "id", "cursor_column": "id"}},
        {"id": "sink", "type": "sink",
         "config": {"datasource_id": datasource_id, "table": "t",
                    "pk": ["id"], "mode": "upsert"}}],
        "edges": [{"from": "src", "to": "sink"}],
        "settings": {"batch": 10}}


def test_runner_persists_cursor_after_success(s, monkeypatch):
    seen = []

    class FakeSource:
        def read(self, cursor, limit):
            seen.append(cursor)
            return [{"id": 2}], '["2","2"]'

    class FakeSink:
        def write(self, rows):
            return len(rows)

    monkeypatch.setattr("odf.pipeline.nodes.source.source_for",
                        lambda ds, dag: FakeSource())
    monkeypatch.setattr("odf.pipeline.nodes.sink.sink_for",
                        lambda ds, dag: FakeSink())

    a = create_asset(s, 1, "pipeline", "p", _content(), "admin")
    publish_asset(s, a.id, "admin")
    execute_pipeline(s, a.id)
    s.refresh(a)
    assert a.cursor_json["src"] == '["2","2"]'

    execute_pipeline(s, a.id)
    assert seen == [None, '["2","2"]']


def test_runner_keeps_cursor_when_sink_fails(s, monkeypatch):
    class FakeSource:
        def read(self, cursor, limit):
            return [{"id": 2}], '["2","2"]'

    class BoomSink:
        def write(self, rows):
            raise RuntimeError("target down")

    monkeypatch.setattr("odf.pipeline.nodes.source.source_for",
                        lambda ds, dag: FakeSource())
    monkeypatch.setattr("odf.pipeline.nodes.sink.sink_for",
                        lambda ds, dag: BoomSink())

    a = create_asset(s, 1, "pipeline", "p", _content(), "admin")
    publish_asset(s, a.id, "admin")
    with pytest.raises(PipelineRunError):
        execute_pipeline(s, a.id)
    s.refresh(a)
    assert not a.cursor_json


def test_publish_rejects_cross_project_datasource(s):
    s.add(Datasource(id=2, project_id=2, name="other", kind="sqlite",
                     dsn_encrypted="x"))
    s.commit()
    a = create_asset(s, 1, "pipeline", "p", _content(2), "admin")
    with pytest.raises(ValueError):
        publish_asset(s, a.id, "admin")


def test_runner_inputs_follow_ports():
    from odf.pipeline.schema import input_edges
    content = {"nodes": [
        {"id": "a", "type": "source", "config": {}},
        {"id": "b", "type": "source", "config": {}},
        {"id": "j", "type": "join", "config": {}},
        {"id": "o", "type": "sink", "config": {}}],
        "edges": [{"from": "b", "to": "j", "to_port": "right"},
                  {"from": "a", "to": "j", "to_port": "left"},
                  {"from": "j", "to": "o"}]}
    assert [e["from"] for e in input_edges(content, "j")] == ["a", "b"]
