import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from odf.assets.service import create_asset, publish_asset
from odf.db import Base
from odf.models import Datasource, Job, PipelineNodeRun
from odf.pipeline.runner import execute_pipeline
from odf.services.crypto import encrypt_secret


def test_skip_policy_continues_and_records_failure(tmp_path):
    url = "sqlite:///" + str(tmp_path / "e.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table src (id int)"))
        c.execute(text("create table dst (id int primary key)"))
        c.execute(text("insert into src values (1),(2)"))
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                     dsn_encrypted=encrypt_secret(url)))
    s.commit()
    content = {"nodes": [
        {"id": "s", "type": "source",
         "config": {"datasource_id": 1, "table": "src", "pk": "id"}},
        {"id": "f", "type": "filter", "on_error": "skip",
         "config": {"conditions": [{"column": "nope", "op": "=",
                                    "value": 1}]}},
        {"id": "o", "type": "sink",
         "config": {"datasource_id": 1, "table": "dst", "pk": ["id"]}}],
        "edges": [{"from": "s", "to": "f"}, {"from": "f", "to": "o"}]}
    a = create_asset(s, 1, "pipeline", "p", content, "admin")
    publish_asset(s, a.id, "admin")
    job = Job(asset_id=a.id, asset_type="pipeline", status="running")
    s.add(job)
    s.commit()
    out = execute_pipeline(s, a.id, job.id)
    assert out["node_stats"]["f"]["status"] == "failed"
    assert out["node_stats"]["o"]["status"] == "success"
    assert s.query(PipelineNodeRun).filter_by(
        job_id=job.id, node_id="f", status="failed").count() == 1


def test_skipped_sink_does_not_advance_cursor(tmp_path):
    from odf.pipeline.runner import execute_pipeline
    url = "sqlite:///" + str(tmp_path / "c.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table src (id int)"))
        c.execute(text("create table dst (id int primary key, "
                       "required text not null)"))
        c.execute(text("insert into src values (1),(2)"))
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                     dsn_encrypted=encrypt_secret(url)))
    s.commit()
    content = {"nodes": [
        {"id": "s", "type": "source",
         "config": {"datasource_id": 1, "table": "src", "pk": "id",
                    "cursor_column": "id"}},
        {"id": "o", "type": "sink", "on_error": "skip",
         "config": {"datasource_id": 1, "table": "dst", "pk": ["id"]}}],
        "edges": [{"from": "s", "to": "o"}]}
    a = create_asset(s, 1, "pipeline", "p", content, "admin")
    publish_asset(s, a.id, "admin")
    execute_pipeline(s, a.id)
    s.refresh(a)
    assert not a.cursor_json
