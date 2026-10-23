from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from odf.appstudio.content import empty_app, validate_app
from odf.assets.service import create_asset, publish_asset
from odf.db import Base
from odf.models import Datasource
from odf.services.crypto import encrypt_secret

DATASET = {"mode": "visual", "query": {
    "datasource_id": 1, "table": "t",
    "select": [{"column": "city"}, {"column": "amount"}],
    "filters": [{"column": "city", "op": "=", "param": "city"}],
    "limit": 100},
    "params": [{"name": "city", "type": "string", "required": False}],
    "sql": None, "auth": None}


def _env(tmp_path):
    url = "sqlite:///" + str(tmp_path / "a.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table t (city text, amount int)"))
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                     dsn_encrypted=encrypt_secret(url)))
    s.commit()
    return s


def _models(s, dataset=None):
    ds = create_asset(s, 1, "dataset", "D", dataset or DATASET, "admin",
                      enabled=False)
    publish_asset(s, ds.id, "admin")
    mc = {"dataset_id": ds.id,
          "measure": {"agg": "sum", "column": "amount", "as": "value"},
          "dimensions": ["city"], "filters": [],
          "format": {"type": "number"}}
    m = create_asset(s, 1, "metric", "M", mc, "admin", enabled=False)
    publish_asset(s, m.id, "admin")
    return ds.id, m.id


def test_empty_app_is_valid(tmp_path):
    s = _env(tmp_path)
    assert validate_app(s, empty_app(), 1) == []


def test_non_object_content_is_rejected(tmp_path):
    s = _env(tmp_path)
    assert validate_app(s, {}, 1)[0]["field"] == "pages"


def test_valid_app(tmp_path):
    s = _env(tmp_path)
    dsid, mid = _models(s)
    content = {"start_page": "p1", "pages": [{
        "id": "p1", "title": "P",
        "params": [{"name": "city", "type": "string"}],
        "components": [
            {"id": "t", "type": "text", "text": "hello"},
            {"id": "m", "type": "metric", "metric_id": mid},
            {"id": "d", "type": "table", "dataset_id": dsid,
             "columns": ["city", "amount"], "limit": 50}]}]}
    assert validate_app(s, content, 1) == []


def test_duplicate_ids_and_missing_start(tmp_path):
    s = _env(tmp_path)
    content = {"start_page": "missing", "pages": [
        {"id": "p1", "title": "P", "params": [], "components": [
            {"id": "x", "type": "text", "text": "a"},
            {"id": "x", "type": "text", "text": "b"}]}]}
    errs = validate_app(s, content, 1)
    assert any("start" in e["field"] for e in errs)
    assert any("duplicate" in e["message"] for e in errs)


def test_dataset_required_param_must_be_exposed(tmp_path):
    s = _env(tmp_path)
    required = {**DATASET,
                "params": [{"name": "city", "type": "string",
                            "required": True}]}
    dsid, _ = _models(s, required)
    content = {"start_page": "p1", "pages": [{
        "id": "p1", "title": "P", "params": [],
        "components": [{"id": "d", "type": "table",
                        "dataset_id": dsid}]}]}
    assert any("params" in e["field"] for e in validate_app(s, content, 1))


def test_unknown_column_and_unpublished_ref(tmp_path):
    s = _env(tmp_path)
    dsid, _ = _models(s)
    content = {"start_page": "p1", "pages": [{
        "id": "p1", "title": "P", "params": [],
        "components": [
            {"id": "d", "type": "table", "dataset_id": dsid,
             "columns": ["nope"]},
            {"id": "m", "type": "metric", "metric_id": 999}]}]}
    errs = validate_app(s, content, 1)
    assert any("column not in dataset" in e["message"] for e in errs)
    assert any(e["field"] == "metric_id" for e in errs)


def test_table_can_bind_only_a_metric(tmp_path):
    s = _env(tmp_path)
    _, mid = _models(s)
    content = {"start_page": "p1", "pages": [{
        "id": "p1", "title": "P", "params": [],
        "components": [{"id": "m", "type": "table", "metric_id": mid}]}]}
    assert validate_app(s, content, 1) == []


def test_malformed_shapes_are_reported_not_raised(tmp_path):
    s = _env(tmp_path)
    content = {"start_page": [], "pages": [{
        "id": "p1", "title": "P", "params": 5,
        "components": [{"id": "x", "type": [], "text": "a"}]}]}
    errs = validate_app(s, content, 1)
    assert errs


def test_invalid_param_default_is_rejected(tmp_path):
    s = _env(tmp_path)
    content = {"start_page": "p1", "pages": [{
        "id": "p1", "title": "P",
        "params": [{"name": "n", "type": "number", "default": "abc"}],
        "components": []}]}
    assert validate_app(s, content, 1)
