import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from odf.assets.service import create_asset, publish_asset
from odf.db import Base
from odf.models import Datasource
from odf.services.crypto import encrypt_secret
from odf.services.query_log import list_runs
from odf.transform.service import preview_model
from odf.workbench.service import explain_query, run_query


def _env(tmp_path):
    url = "sqlite:///" + str(tmp_path / "w.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table orders (id int, city text)"))
        c.execute(text("insert into orders values (1,'a'),(2,'b')"))
    raw.dispose()
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Datasource(id=1, project_id=1, name="local", kind="sqlite",
                     dsn_encrypted=encrypt_secret(url)))
    s.commit()
    return s


def test_workbench_query_is_recorded(tmp_path):
    s = _env(tmp_path)
    out = run_query(s, 1, 1, "select * from orders", 10, "alice",
                    role="admin")
    assert out["row_count"] == 2
    runs = list_runs(s, 1)
    assert runs["total"] == 1
    assert runs["items"][0]["source"] == "workbench"
    assert runs["items"][0]["status"] == "ok"
    assert runs["items"][0]["actor"] == "alice"
    assert runs["items"][0]["rows"] == 2


def test_failed_query_is_recorded(tmp_path):
    s = _env(tmp_path)
    with pytest.raises(ValueError):
        run_query(s, 1, 1, "select * from missing", 10, "alice",
                  role="admin")
    runs = list_runs(s, 1, status="error")
    assert runs["total"] == 1
    assert "missing" in runs["items"][0]["error"]


def test_explain_returns_plan_rows(tmp_path):
    s = _env(tmp_path)
    out = explain_query(s, 1, 1, "select * from orders", "alice")
    assert out["row_count"] >= 1
    assert out["columns"]
    assert list_runs(s, 1)["total"] == 1


def test_model_preview_is_recorded(tmp_path):
    s = _env(tmp_path)
    content = {"datasource_id": 1, "sql": "select * from orders",
               "materialization": "table", "schema": "main",
               "unique_key": [], "layer": "staging", "description": "",
               "tests": [], "columns": []}
    asset = create_asset(s, 1, "model", "m1", content, "alice")
    publish_asset(s, asset.id, "alice")
    preview_model(s, asset.id, limit=5, actor="alice")
    runs = list_runs(s, 1, source="model")
    assert runs["total"] == 1
    assert runs["items"][0]["status"] == "ok"
