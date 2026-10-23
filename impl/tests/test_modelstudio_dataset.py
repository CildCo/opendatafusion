from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from odf.assets.service import create_asset, publish_asset
from odf.db import Base
from odf.modelstudio.content import empty_dataset, validate_dataset
from odf.modelstudio.service import dataset_schema, preview_dataset
from odf.models import Datasource
from odf.services.crypto import encrypt_secret


def _env(tmp_path):
    url = "sqlite:///" + str(tmp_path / "m.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table t (id int, city text, amount int)"))
        c.execute(text("insert into t values (1,'a',10),(2,'b',20)"))
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                     dsn_encrypted=encrypt_secret(url)))
    s.commit()
    return s


def test_empty_dataset_is_invalid(tmp_path):
    s = _env(tmp_path)
    assert validate_dataset(s, empty_dataset(), 1)


def test_dataset_preview_and_schema(tmp_path):
    s = _env(tmp_path)
    content = {"mode": "visual", "query": {
        "datasource_id": 1, "table": "t",
        "select": [{"column": "id"}, {"column": "city"}],
        "filters": [{"column": "id", "op": ">", "value": 0}],
        "limit": 100}, "params": [], "sql": None, "auth": None}
    a = create_asset(s, 1, "dataset", "D", content, "admin", enabled=False)
    out = preview_dataset(s, a.id)
    assert out["row_count"] == 2
    publish_asset(s, a.id, "admin")
    schema = dataset_schema(s, a.id)
    assert [c["name"] for c in schema["columns"]] == ["id", "city"]


def test_dataset_rejects_unknown_column(tmp_path):
    s = _env(tmp_path)
    content = {"mode": "visual", "query": {
        "datasource_id": 1, "table": "t",
        "select": [{"column": "nope"}]}, "params": []}
    a = create_asset(s, 1, "dataset", "D", content, "admin", enabled=False)
    assert validate_dataset(s, content, 1)


def test_sql_mode_dataset_is_rejected(tmp_path):
    s = _env(tmp_path)
    content = {"mode": "sql", "query": {"datasource_id": 1},
               "sql": "select * from t", "params": []}
    a = create_asset(s, 1, "dataset", "D", content, "admin", enabled=False)
    assert validate_dataset(s, content, 1)
    import pytest
    with pytest.raises(ValueError):
        preview_dataset(s, a.id)


def test_duplicate_dataset_output_is_rejected(tmp_path):
    s = _env(tmp_path)
    content = {"mode": "visual", "query": {
        "datasource_id": 1, "table": "t",
        "select": [{"column": "id", "as": "x"},
                   {"column": "city", "as": "x"}]}, "params": []}
    assert validate_dataset(s, content, 1)


def test_dataset_aggregate_select_is_rejected(tmp_path):
    s = _env(tmp_path)
    content = {"mode": "visual", "query": {
        "datasource_id": 1, "table": "t",
        "select": [{"column": "amount", "agg": "sum"}]}, "params": []}
    assert validate_dataset(s, content, 1)


def test_preview_cache_hits_and_separates_roles(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from odf.modelstudio import service
    s = _env(tmp_path)
    content = {"mode": "visual", "query": {
        "datasource_id": 1, "table": "t",
        "select": [{"column": "id"}, {"column": "city"}],
        "limit": 100}, "params": []}
    a = create_asset(s, 1, "dataset", "D", content, "admin", enabled=False)
    publish_asset(s, a.id, "admin")
    calls = {"n": 0}

    def fake(*args, **kwargs):
        calls["n"] += 1
        return {"columns": [], "rows": [], "row_count": 0, "ms": 0,
                "sql": ""}

    monkeypatch.setattr(service, "run_content", fake)
    monkeypatch.setattr(service, "get_settings", lambda: SimpleNamespace(
        preview_cache_ttl_s=60, preview_cache_size=10))
    service.cache.clear()
    first = preview_dataset(s, a.id)
    second = preview_dataset(s, a.id)
    assert calls["n"] == 1
    assert first["cached"] is False and second["cached"] is True
    preview_dataset(s, a.id, role="viewer")
    assert calls["n"] == 2
