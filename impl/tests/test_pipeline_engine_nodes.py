import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from odf.assets.service import create_asset, publish_asset
from odf.db import Base
from odf.engine import JobStatus
from odf.models import Datasource, LineageEdge, PipelineNodeRun
from odf.pipeline.runner import PipelineRunError, execute_pipeline
from odf.pipeline.schema import validate_dag
from odf.pipeline.schema_service import content_schemas
from odf.services.crypto import encrypt_secret


class FakeSpark:
    def __init__(self, status=JobStatus.SUCCEEDED, error=""):
        self.submitted = []
        self._status = status
        self._error = error

    def submit(self, spec):
        self.submitted.append(spec)
        return spec.name

    def status(self, name, namespace=None):
        return self._status

    def result(self, name, namespace=None):
        return {"state": "", "error": self._error}

    def cancel(self, name, namespace=None):
        pass


def _session(tmp_path):
    url = "sqlite:///" + str(tmp_path / "p.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table src (id int)"))
        c.execute(text("insert into src values (1)"))
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    s.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                     dsn_encrypted=encrypt_secret(url)))
    s.commit()
    return s


def _spark_node(node_id="e", **overrides):
    config = {"name": "odf-spark-%s" % node_id,
              "image": "apache/spark:3.5.1",
              "main_application_file": "local:///opt/spark/app.py",
              "source_tables": ["1:src"], "target_table": "demo.out"}
    config.update(overrides)
    return {"id": node_id, "type": "spark", "config": config}


def _content(*, with_sink=False, engine_node=None):
    nodes = [{"id": "s", "type": "source",
              "config": {"datasource_id": 1, "table": "src", "pk": "id"}},
             engine_node or _spark_node()]
    edges = [{"from": "s", "to": "e"}]
    if with_sink:
        nodes.append({"id": "o", "type": "sink",
                      "config": {"datasource_id": 1, "table": "src",
                                 "pk": ["id"]}})
        edges.append({"from": "e", "to": "o"})
    return {"nodes": nodes, "edges": edges}


def _published(session, content):
    asset = create_asset(session, 1, "pipeline", "job-pipe", content, "admin")
    publish_asset(session, asset.id, "admin")
    return asset


def _run(session, asset):
    from odf.models import Job
    job = Job(asset_id=asset.id, asset_type="pipeline", status="running")
    session.add(job)
    session.commit()
    return execute_pipeline(session, asset.id, job.id)


def test_dag_accepts_engine_node_leaf():
    assert validate_dag(_content()) == []


def test_dag_accepts_engine_only_pipeline():
    content = {"nodes": [_spark_node()], "edges": []}
    assert validate_dag(content) == []


def test_dag_rejects_engine_node_with_output():
    errors = validate_dag(_content(with_sink=True))
    assert any(e["node_id"] == "e" and "输出" in e["message"]
               for e in errors)


def test_preview_refuses_engine_node(tmp_path, monkeypatch):
    monkeypatch.setattr("odf.services.engine_jobs._spark_engine", FakeSpark)
    session = _session(tmp_path)
    asset = _published(session, _content())
    with pytest.raises(PipelineRunError, match="preview"):
        execute_pipeline(session, asset.id, preview=True)


def test_run_dispatches_and_records_node(tmp_path, monkeypatch):
    fake = FakeSpark(status=JobStatus.SUCCEEDED)
    monkeypatch.setattr("odf.services.engine_jobs._spark_engine", lambda: fake)
    session = _session(tmp_path)
    asset = _published(session, _content())

    out = _run(session, asset)

    assert out["node_stats"]["e"]["status"] == "success"
    assert len(fake.submitted) == 1
    assert fake.submitted[0].main_application_file == "local:///opt/spark/app.py"
    run = (session.query(PipelineNodeRun)
           .filter_by(asset_id=asset.id, node_id="e").one())
    assert run.status == "success"


def test_run_records_lineage(tmp_path, monkeypatch):
    monkeypatch.setattr("odf.services.engine_jobs._spark_engine",
                        lambda: FakeSpark(status=JobStatus.SUCCEEDED))
    session = _session(tmp_path)
    asset = _published(session, _content())

    _run(session, asset)

    edge = (session.query(LineageEdge)
            .filter_by(to_ref="demo.out", from_ref="1:src").one())
    assert edge.from_type == "table"
    assert edge.to_type == "table"


def test_failed_job_fails_the_node(tmp_path, monkeypatch):
    monkeypatch.setattr("odf.services.engine_jobs._spark_engine",
                        lambda: FakeSpark(status=JobStatus.FAILED,
                                          error="driver exited 1"))
    session = _session(tmp_path)
    asset = _published(session, _content())

    with pytest.raises(PipelineRunError, match="driver exited 1"):
        _run(session, asset)

    run = (session.query(PipelineNodeRun)
           .filter_by(asset_id=asset.id, node_id="e").one())
    assert run.status == "failed"


def test_nowait_marks_node_dispatched(tmp_path, monkeypatch):
    fake = FakeSpark(status=JobStatus.RUNNING)
    monkeypatch.setattr("odf.services.engine_jobs._spark_engine", lambda: fake)
    session = _session(tmp_path)
    content = _content()
    content["nodes"][1]["config"]["wait"] = False
    asset = _published(session, content)

    out = _run(session, asset)

    assert out["node_stats"]["e"]["status"] == "dispatched"
    run = (session.query(PipelineNodeRun)
           .filter_by(asset_id=asset.id, node_id="e").one())
    assert run.status == "dispatched"


def test_engine_node_schema_is_empty(tmp_path):
    session = _session(tmp_path)
    rows = content_schemas(session, _content(), 1)
    engine = [r for r in rows if r["node_id"] == "e"][0]
    assert engine["columns"] == []


def test_engine_node_requires_spark_target(tmp_path):
    from odf.pipeline.validate import validate_pipeline_content

    session = _session(tmp_path)
    content = _content()
    content["nodes"][1]["config"]["main_application_file"] = "job.py"
    errors = validate_pipeline_content(session, content, 1)
    assert any(e["node_id"] == "e" and e["field"] == "main_application_file"
               for e in errors)
