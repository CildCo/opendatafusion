from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from odf.appstudio.service import app_data
from odf.assets.service import create_asset, publish_asset
from odf.db import Base
from odf.models import Datasource
from odf.services.crypto import encrypt_secret

DATASET = {"mode": "visual", "query": {
    "datasource_id": 1, "table": "t",
    "select": [{"column": "city"}, {"column": "amount"}],
    "filters": [{"column": "city", "op": "=", "param": "city"}],
    "limit": 100},
    "params": [{"name": "city", "type": "string"}], "sql": None,
    "auth": None}


def _env(tmp_path):
    url = "sqlite:///" + str(tmp_path / "a.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table t (city text, amount int)"))
        c.execute(text("insert into t values ('a',10),('a',5),('b',7)"))
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                     dsn_encrypted=encrypt_secret(url)))
    s.commit()
    return s


def test_app_page_data_with_params(tmp_path):
    s = _env(tmp_path)
    ds = create_asset(s, 1, "dataset", "D", DATASET, "admin", enabled=False)
    publish_asset(s, ds.id, "admin")
    content = {"start_page": "p1", "pages": [{
        "id": "p1", "title": "P",
        "params": [{"name": "city", "type": "string", "default": "a"}],
        "components": [
            {"id": "t", "type": "text", "text": "hello"},
            {"id": "d", "type": "table", "dataset_id": ds.id,
             "limit": 50}]}]}
    a = create_asset(s, 1, "app", "A", content, "admin", enabled=False)
    out = app_data(s, a.id, params={"city": "a"})
    assert out["components"]["d"]["rows"] == [{"city": "a", "amount": 10},
                                              {"city": "a", "amount": 5}]
    assert out["components"]["t"]["text"] == "hello"
    assert out["params"]["city"] == "a"


def test_component_error_is_isolated(tmp_path):
    s = _env(tmp_path)
    content = {"start_page": "p1", "pages": [{
        "id": "p1", "title": "P", "params": [], "components": [
            {"id": "bad", "type": "table", "dataset_id": 999},
            {"id": "ok", "type": "text", "text": "ok"}]}]}
    a = create_asset(s, 1, "app", "A", content, "admin", enabled=False)
    out = app_data(s, a.id)
    assert out["components"]["bad"]["error"]
    assert out["components"]["ok"]["text"] == "ok"


def test_missing_required_page_param_rejects(tmp_path):
    s = _env(tmp_path)
    ds = create_asset(s, 1, "dataset", "D", DATASET, "admin", enabled=False)
    publish_asset(s, ds.id, "admin")
    content = {"start_page": "p1", "pages": [{
        "id": "p1", "title": "P",
        "params": [{"name": "city", "type": "string", "required": True}],
        "components": [{"id": "d", "type": "table",
                        "dataset_id": ds.id}]}]}
    a = create_asset(s, 1, "app", "A", content, "admin", enabled=False)
    try:
        app_data(s, a.id)
    except ValueError as e:
        assert "city" in str(e)
    else:
        raise AssertionError("expected missing param error")


def test_metric_component(tmp_path):
    s = _env(tmp_path)
    plain = {**DATASET, "query": {**DATASET["query"], "filters": []},
             "params": []}
    ds = create_asset(s, 1, "dataset", "D", plain, "admin", enabled=False)
    publish_asset(s, ds.id, "admin")
    mc = {"dataset_id": ds.id,
          "measure": {"agg": "sum", "column": "amount", "as": "total"},
          "dimensions": [], "filters": [],
          "format": {"type": "number"}}
    m = create_asset(s, 1, "metric", "M", mc, "admin", enabled=False)
    publish_asset(s, m.id, "admin")
    content = {"start_page": "p1", "pages": [{
        "id": "p1", "title": "P", "params": [], "components": [
            {"id": "m", "type": "metric", "metric_id": m.id,
             "value_column": "total"}]}]}
    a = create_asset(s, 1, "app", "A", content, "admin", enabled=False)
    out = app_data(s, a.id)
    assert out["components"]["m"]["rows"][0]["total"] == 22


def test_blank_optional_filter_returns_all_rows(tmp_path):
    s = _env(tmp_path)
    ds = create_asset(s, 1, "dataset", "D", DATASET, "admin", enabled=False)
    publish_asset(s, ds.id, "admin")
    content = {"start_page": "p1", "pages": [{
        "id": "p1", "title": "P",
        "params": [{"name": "city", "type": "string", "default": ""}],
        "components": [{"id": "d", "type": "table",
                        "dataset_id": ds.id}]}]}
    a = create_asset(s, 1, "app", "A", content, "admin", enabled=False)
    out = app_data(s, a.id)
    assert out["components"]["d"]["row_count"] == 3
    assert out["components"]["d"]["error"] is None


def test_malformed_component_is_rejected(tmp_path):
    s = _env(tmp_path)
    ds = create_asset(s, 1, "dataset", "D", DATASET, "admin", enabled=False)
    publish_asset(s, ds.id, "admin")
    content = {"start_page": "p1", "pages": [{
        "id": "p1", "title": "P", "params": [], "components": [
            {"id": "bad", "type": "table", "dataset_id": ds.id,
             "columns": 5},
            {"id": "ok", "type": "text", "text": "ok"}]}]}
    a = create_asset(s, 1, "app", "A", content, "admin", enabled=False)
    try:
        app_data(s, a.id)
    except ValueError as e:
        assert "columns" in str(e)
    else:
        raise AssertionError("expected structural rejection")


def test_form_is_not_executed_as_a_metric(tmp_path):
    s = _env(tmp_path)
    ds = create_asset(s, 1, "dataset", "D", DATASET, "admin", enabled=False)
    publish_asset(s, ds.id, "admin")
    content = {"start_page": "p1", "pages": [{
        "id": "p1", "title": "P", "params": [], "components": [
            {"id": "f", "type": "form", "dataset_id": ds.id,
             "mode": "insert", "fields": [
                 {"column": "city", "widget": "input"}]},
            {"id": "ok", "type": "text", "text": "ok"}]}]}
    a = create_asset(s, 1, "app", "A", content, "admin", enabled=False)
    out = app_data(s, a.id)
    assert "f" not in out["components"]
    assert out["components"]["ok"]["text"] == "ok"
