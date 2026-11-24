import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.db import Base
from odf.models import Datasource
from odf.services.crypto import encrypt_secret
from odf.services.query_log import (get_run, list_runs, normalize_statement,
                                     record, summary)


def _env(tmp_path):
    url = "sqlite:///" + str(tmp_path / "q.db")
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Datasource(id=1, project_id=1, name="warehouse", kind="sqlite",
                     dsn_encrypted=encrypt_secret(url)))
    s.add(Datasource(id=2, project_id=1, name="lake", kind="trino",
                     dsn_encrypted=encrypt_secret("trino://x")))
    s.commit()
    return s


def test_record_and_list_runs(tmp_path):
    s = _env(tmp_path)
    record(s, 1, 1, "alice", "workbench", 120, 10,
           sql="select * from orders")
    record(s, 1, 2, "bob", "model", 900, 3, "query timeout",
           sql="select * from huge")
    runs = list_runs(s, 1)
    assert runs["total"] == 2
    first = runs["items"][0]
    assert first["actor"] == "bob"
    assert first["status"] == "error"
    assert first["source"] == "model"
    assert first["datasource_name"] == "lake"
    assert first["sql_preview"].startswith("select")
    assert first["error"] == "query timeout"


def test_list_filters(tmp_path):
    s = _env(tmp_path)
    record(s, 1, 1, "alice", "workbench", 120, 10, sql="select 1")
    record(s, 1, 2, "bob", "model", 900, 3, "boom", sql="select 2")
    assert list_runs(s, 1, datasource_id=1)["total"] == 1
    assert list_runs(s, 1, status="error")["total"] == 1
    assert list_runs(s, 1, source="model")["total"] == 1
    assert list_runs(s, 1, source="workbench")["items"][0]["status"] == "ok"


def test_summary_percentiles_and_slowest(tmp_path):
    s = _env(tmp_path)
    for ms in (10, 20, 30, 40, 1000):
        record(s, 1, 1, "alice", "workbench", ms, 1, sql="select 1")
    record(s, 1, 1, "alice", "workbench", 50, 0, "failed", sql="select 2")
    out = summary(s, 1)
    assert out["total"] == 6
    assert out["ok"] == 5
    assert out["errors"] == 1
    assert out["p50_ms"] == 30
    assert out["p95_ms"] == 1000
    assert out["slowest"][0]["ms"] == 1000
    sources = {row["source"]: row for row in out["by_source"]}
    assert sources["workbench"]["count"] == 6
    assert sources["workbench"]["errors"] == 1


def test_preview_is_bounded_and_hashed(tmp_path):
    s = _env(tmp_path)
    sql = "select * from orders where note = '" + "x" * 500 + "'"
    run = record(s, 1, 1, "alice", "workbench", 5, 1, sql=sql)
    assert len(run.sql_preview) == 200
    assert len(run.sql_hash) == 64
    assert "x" * 300 not in run.sql_preview
    detail = get_run(s, 1, run.id)
    assert detail["sql"] == sql


def test_run_detail_is_project_scoped(tmp_path):
    s = _env(tmp_path)
    run = record(s, 1, 1, "alice", "workbench", 5, 1, sql="select 1")
    with pytest.raises(ValueError):
        get_run(s, 2, run.id)


def test_unknown_datasource_is_kept_as_null(tmp_path):
    s = _env(tmp_path)
    walk = record(s, 1, None, "alice", "federated", 5, 1, sql="select 1")
    assert walk.datasource_id is None
    assert list_runs(s, 1)["items"][0]["datasource_name"] is None


def test_statement_normalization_replaces_literals():
    left = normalize_statement("SELECT * FROM orders WHERE id = 42 "
                               "AND note = 'x'")
    right = normalize_statement("select *   from orders where id = 7 "
                                "and note = 'y'")
    assert left == right
    assert "42" not in left and "'x'" not in left


def test_summary_groups_by_actor_and_template(tmp_path):
    s = _env(tmp_path)
    record(s, 1, 1, "alice", "workbench", 10, 1,
           sql="select * from orders where id = 1")
    record(s, 1, 1, "alice", "workbench", 30, 1,
           sql="select * from orders where id = 2")
    record(s, 1, 1, "bob", "workbench", 100, 0, "boom",
           sql="select * from orders where id = 3")
    out = summary(s, 1)
    actors = {row["actor"]: row for row in out["by_actor"]}
    assert actors["alice"]["count"] == 2
    assert actors["bob"]["errors"] == 1
    templates = out["templates"]
    assert templates[0]["count"] == 3
    assert templates[0]["variants"] == 3
    assert templates[0]["avg_ms"] == 47
