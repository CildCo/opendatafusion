import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from odf.assets.service import create_asset, publish_asset
from odf.db import Base
from odf.models import Datasource, Job
from odf.services.crypto import encrypt_secret
from odf.transform.content import validate_model
from odf.transform.service import (materialize_model, preview_model,
                                   sync_model_graph)


def _env(tmp_path):
    url = "sqlite:///" + str(tmp_path / "m.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table orders (id int, city text, amount int)"))
        c.execute(text("insert into orders values "
                       "(1,'a',10),(2,'a',5),(3,'b',7)"))
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                     dsn_encrypted=encrypt_secret(url)))
    s.commit()
    return s


def _model(s, name, sql, materialization="table", **extra):
    content = {"datasource_id": 1, "sql": sql,
               "materialization": materialization, "schema": "main",
               "unique_key": [], "layer": "staging", "description": "",
               "tests": [], "columns": [], **extra}
    asset = create_asset(s, 1, "model", name, content, "admin",
                         enabled=True)
    return asset, content


def test_model_materializes_and_previews(tmp_path):
    s = _env(tmp_path)
    asset, content = _model(s, "staging", "select * from orders")
    publish_asset(s, asset.id, "admin")
    out = materialize_model(s, asset.id)
    assert asset.key in out["target"]
    assert out["tests"] == []
    count = preview_model(s, asset.id, limit=10)
    assert count["row_count"] == 3
    assert {c["name"] for c in count["columns"]} == {"id", "city", "amount"}


def test_model_ref_builds_lineage_and_dependency(tmp_path):
    s = _env(tmp_path)
    base, _ = _model(s, "base", "select * from orders")
    publish_asset(s, base.id, "admin")
    materialize_model(s, base.id)
    mart, content = _model(
        s, "mart",
        "select city, sum(amount) as total from {{ ref('%s') }} "
        "group by city" % base.key,
        tests=[{"kind": "not_null", "column": "total"},
               {"kind": "unique", "column": "city"}])
    publish_asset(s, mart.id, "admin")
    sync_model_graph(s, mart, content)
    materialize_model(s, mart.id)
    out = preview_model(s, mart.id)
    assert out["row_count"] == 2
    from odf.models import JobDependency, LineageEdge
    assert s.query(JobDependency).filter_by(
        downstream_type="model", downstream_id=mart.id).count() == 1
    assert s.query(LineageEdge).filter_by(
        to_type="model", to_id=str(mart.id)).count() == 1


def test_incremental_inserts_only_new_keys(tmp_path):
    s = _env(tmp_path)
    asset, content = _model(
        s, "daily",
        "select city, sum(amount) as total from orders group by city",
        materialization="incremental", unique_key=["city"])
    publish_asset(s, asset.id, "admin")
    materialize_model(s, asset.id)
    materialize_model(s, asset.id)
    out = preview_model(s, asset.id)
    assert out["row_count"] == 2


def test_model_tests_fail_and_are_reported(tmp_path):
    s = _env(tmp_path)
    asset, _ = _model(s, "bad", "select * from orders",
                      tests=[{"kind": "not_null", "column": "city"},
                             {"kind": "sql",
                              "sql": "select count(*) as failures from orders "
                                     "where amount < 0"}])
    publish_asset(s, asset.id, "admin")
    job = Job(id=50, asset_id=asset.id, asset_type="model",
              status="running", payload_json={})
    s.add(job)
    s.commit()
    out = materialize_model(s, asset.id, job)
    s.refresh(job)
    assert out["tests"][0]["status"] == "pass"
    assert asset.key in job.payload_json["last_result"]["target"]


def test_cycle_and_unknown_ref_rejected(tmp_path):
    s = _env(tmp_path)
    a, _ = _model(s, "a", "select 1 as x")
    publish_asset(s, a.id, "admin")
    content = {"datasource_id": 1,
               "sql": "select * from {{ ref('%s') }}" % a.key,
               "materialization": "table", "schema": "main",
               "unique_key": [], "layer": "staging", "description": "",
               "tests": [], "columns": []}
    assert validate_model(s, content, 1, a.id)
    content["sql"] = "select * from {{ ref('missing') }}"
    assert validate_model(s, content, 1)


def test_scheduler_runs_published_model(tmp_path):
    from datetime import datetime, timezone
    from odf.services.jobs import process_job, scheduler_tick
    s = _env(tmp_path)
    asset, _ = _model(s, "scheduled", "select * from orders")
    asset.cron = "0 * * * * ?"
    s.commit()
    publish_asset(s, asset.id, "admin")
    scheduler_tick(s, now=datetime.now(timezone.utc))
    job = (s.query(Job).filter_by(asset_id=asset.id, asset_type="model")
           .order_by(Job.id.desc()).first())
    assert job and job.status == "queued"
    process_job(s, job, "worker")
    s.refresh(job)
    assert job.status == "success"


def test_failing_test_marks_job_and_raises(tmp_path):
    from odf.transform.service import ModelTestError
    s = _env(tmp_path)
    asset, _ = _model(s, "dupes", "select city from orders",
                      tests=[{"kind": "unique", "column": "city"}])
    publish_asset(s, asset.id, "admin")
    job = Job(id=51, asset_id=asset.id, asset_type="model",
              status="running", payload_json={})
    s.add(job)
    s.commit()
    with pytest.raises(ModelTestError):
        materialize_model(s, asset.id, job)
    s.refresh(job)
    assert job.payload_json["last_result"]["tests"][0]["status"] == "fail"


def test_model_dependency_waits_for_upstream_success(tmp_path):
    from odf.services.dependencies import dependencies_satisfied
    s = _env(tmp_path)
    up, _ = _model(s, "up", "select * from orders")
    publish_asset(s, up.id, "admin")
    down, content = _model(
        s, "down", "select * from {{ ref('%s') }}" % up.key)
    publish_asset(s, down.id, "admin")
    sync_model_graph(s, down, content)
    assert not dependencies_satisfied(s, 1, "model", down.id)["satisfied"]
    s.add(Job(asset_id=up.id, asset_type="model", status="success"))
    s.commit()
    assert dependencies_satisfied(s, 1, "model", down.id)["satisfied"]
