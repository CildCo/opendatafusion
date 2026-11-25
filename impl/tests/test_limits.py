import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.assets.service import create_asset
from odf.db import Base
from odf.models import Datasource, Job, Project, QueryRun
from odf.services.crypto import encrypt_secret
from odf.services.limits import (RateLimited, check_query_rate,
                                 job_datasource, job_slot_ok, limits_of)


def _env():
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Project(id=1, code="p", name="P", status=1))
    s.add(Datasource(id=1, project_id=1, name="local", kind="sqlite",
                     dsn_encrypted=encrypt_secret("sqlite://"),
                     limit_json={"max_queries_per_min": 2,
                                 "max_running_jobs": 1}))
    s.commit()
    return s


def _model(s, name="m"):
    return create_asset(
        s, 1, "model", name,
        {"datasource_id": 1, "sql": "select 1", "materialization": "view",
         "schema": "main", "unique_key": [], "layer": "staging",
         "description": "", "tests": [], "columns": []}, "admin")


def test_limits_are_normalized():
    s = _env()
    ds = s.get(Datasource, 1)
    ds.limit_json = {"max_queries_per_min": "3", "max_running_jobs": -1}
    assert limits_of(ds) == {"max_queries_per_min": 3,
                             "max_running_jobs": 0}


def test_query_rate_limit():
    s = _env()
    ds = s.get(Datasource, 1)
    check_query_rate(s, ds)
    s.add(QueryRun(project_id=1, datasource_id=1, actor="a",
                   source="workbench", status="ok", sql_hash="h",
                   sql_preview="p", sql_text="p"))
    s.add(QueryRun(project_id=1, datasource_id=1, actor="a",
                   source="workbench", status="ok", sql_hash="h",
                   sql_preview="p", sql_text="p"))
    s.commit()
    with pytest.raises(RateLimited):
        check_query_rate(s, ds)


def test_job_slot_counts_same_datasource():
    s = _env()
    asset = _model(s)
    running = Job(project_id=1, asset_id=asset.id, asset_type="model",
                  status="running", payload_json={})
    s.add(running)
    s.commit()
    assert job_slot_ok(s, 1) is False
    assert job_slot_ok(s, 1, exclude_job_id=running.id) is True
    assert job_datasource(s, running) == 1


def test_lakehouse_job_datasource():
    from odf.models import LakehouseMaintenance
    s = _env()
    row = LakehouseMaintenance(project_id=1, datasource_id=1,
                               schema_name="s", table_name="t",
                               cron="0 * * * *", created_by="admin")
    s.add(row)
    s.flush()
    job = Job(project_id=1, asset_type="lakehouse_maintenance",
              status="running", payload_json={"schedule_id": row.id})
    s.add(job)
    s.commit()
    assert job_datasource(s, job) == 1


def test_unlimited_datasource_always_allows():
    s = _env()
    ds = s.get(Datasource, 1)
    ds.limit_json = {}
    s.commit()
    for _ in range(5):
        check_query_rate(s, ds)
    assert job_slot_ok(s, 1) is True
