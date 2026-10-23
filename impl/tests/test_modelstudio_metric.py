import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from odf.assets.service import create_asset, publish_asset
from odf.db import Base
from odf.modelstudio.content import empty_metric, validate_metric
from odf.modelstudio.service import query_metric
from odf.models import Datasource
from odf.services.crypto import encrypt_secret

DATASET = {"mode": "visual", "query": {
    "datasource_id": 1, "table": "t",
    "select": [{"column": "city"}, {"column": "amount"}],
    "limit": 100}, "params": [], "sql": None, "auth": None}


def _env(tmp_path):
    url = "sqlite:///" + str(tmp_path / "m.db")
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


def test_metric_requires_published_dataset(tmp_path):
    s = _env(tmp_path)
    d = create_asset(s, 1, "dataset", "D", DATASET, "admin", enabled=False)
    content = {"dataset_id": d.id,
               "measure": {"agg": "sum", "column": "amount", "as": "value"},
               "dimensions": ["city"], "filters": [],
               "format": {"type": "number"}}
    assert validate_metric(s, content, 1)


def test_metric_query_grouped(tmp_path):
    s = _env(tmp_path)
    d = create_asset(s, 1, "dataset", "D", DATASET, "admin", enabled=False)
    publish_asset(s, d.id, "admin")
    content = {"dataset_id": d.id,
               "measure": {"agg": "sum", "column": "amount", "as": "value"},
               "dimensions": ["city"], "filters": [],
               "format": {"type": "number"}}
    m = create_asset(s, 1, "metric", "M", content, "admin", enabled=False)
    out = query_metric(s, m.id)
    rows = {r["city"]: r["value"] for r in out["rows"]}
    assert rows == {"a": 15, "b": 7}


def test_metric_rejects_unknown_column(tmp_path):
    s = _env(tmp_path)
    d = create_asset(s, 1, "dataset", "D", DATASET, "admin", enabled=False)
    publish_asset(s, d.id, "admin")
    content = empty_metric()
    content.update({"dataset_id": d.id,
                    "measure": {"agg": "sum", "column": "nope",
                                "as": "value"}})
    assert validate_metric(s, content, 1)


def test_metric_in_filter_and_published_only(tmp_path):
    s = _env(tmp_path)
    d = create_asset(s, 1, "dataset", "D", DATASET, "admin", enabled=False)
    publish_asset(s, d.id, "admin")
    content = {"dataset_id": d.id,
               "measure": {"agg": "sum", "column": "amount", "as": "value"},
               "dimensions": ["city"],
               "filters": [{"column": "city", "op": "in", "value": ["a"]}],
               "format": {"type": "number"}}
    m = create_asset(s, 1, "metric", "M", content, "admin", enabled=False)
    assert validate_metric(s, content, 1) == []
    with pytest.raises(ValueError):
        query_metric(s, m.id, published_only=True)
    publish_asset(s, m.id, "admin")
    out = query_metric(s, m.id, published_only=True)
    assert out["rows"] == [{"city": "a", "value": 15}]


def test_empty_in_filter_is_rejected(tmp_path):
    s = _env(tmp_path)
    d = create_asset(s, 1, "dataset", "D", DATASET, "admin", enabled=False)
    publish_asset(s, d.id, "admin")
    content = {"dataset_id": d.id,
               "measure": {"agg": "count", "column": "*", "as": "value"},
               "dimensions": [], "filters": [
                   {"column": "city", "op": "in", "value": []}],
               "format": {"type": "number"}}
    assert validate_metric(s, content, 1)


def test_malformed_metric_is_a_validation_error(tmp_path):
    s = _env(tmp_path)
    d = create_asset(s, 1, "dataset", "D", DATASET, "admin", enabled=False)
    publish_asset(s, d.id, "admin")
    for content in [
        {"dataset_id": d.id, "measure": "x"},
        {"dataset_id": d.id, "measure": {"agg": "sum", "column": "amount"},
         "dimensions": 3},
        {"dataset_id": d.id, "measure": {"agg": "sum", "column": "amount"},
         "filters": "x"},
    ]:
        assert validate_metric(s, content, 1)


def test_metric_alias_conflicts_with_dimension(tmp_path):
    s = _env(tmp_path)
    d = create_asset(s, 1, "dataset", "D", DATASET, "admin", enabled=False)
    publish_asset(s, d.id, "admin")
    content = {"dataset_id": d.id,
               "measure": {"agg": "sum", "column": "amount", "as": "city"},
               "dimensions": ["city"], "filters": []}
    assert validate_metric(s, content, 1)


def test_metric_bind_key_does_not_collide_with_dataset(tmp_path):
    url = "sqlite:///" + str(tmp_path / "coll.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table t2 (m0 int, city text, amount int)"))
        c.execute(text("insert into t2 values (1,'a',10),(1,'a',5),(2,'b',7)"))
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                     dsn_encrypted=encrypt_secret(url)))
    s.commit()
    ds = {"mode": "visual", "query": {
        "datasource_id": 1, "table": "t2",
        "select": [{"column": "m0"}, {"column": "city"},
                   {"column": "amount"}],
        "filters": [{"column": "m0", "op": "=", "value": 1}],
        "limit": 100}, "params": []}
    d = create_asset(s, 1, "dataset", "D", ds, "admin", enabled=False)
    publish_asset(s, d.id, "admin")
    metric = {"dataset_id": d.id,
              "measure": {"agg": "sum", "column": "amount", "as": "value"},
              "dimensions": ["city"],
              "filters": [{"column": "city", "op": "=", "value": "a"}],
              "format": {"type": "number"}}
    m = create_asset(s, 1, "metric", "M", metric, "admin", enabled=False)
    out = query_metric(s, m.id)
    assert out["rows"] == [{"city": "a", "value": 15}]


def test_metric_aggregates_beyond_dataset_preview_limit(tmp_path):
    url = "sqlite:///" + str(tmp_path / "big.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table big (city text, amount int)"))
        for _ in range(150):
            c.execute(text("insert into big values ('a', 1)"))
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                     dsn_encrypted=encrypt_secret(url)))
    s.commit()
    ds = {"mode": "visual", "query": {
        "datasource_id": 1, "table": "big",
        "select": [{"column": "city"}, {"column": "amount"}],
        "limit": 10}, "params": []}
    d = create_asset(s, 1, "dataset", "D", ds, "admin", enabled=False)
    publish_asset(s, d.id, "admin")
    metric = {"dataset_id": d.id,
              "measure": {"agg": "count", "column": "*", "as": "value"},
              "dimensions": [], "filters": [],
              "format": {"type": "number"}}
    m = create_asset(s, 1, "metric", "M", metric, "admin", enabled=False)
    out = query_metric(s, m.id)
    assert out["rows"] == [{"value": 150}]


def test_metric_query_cache_hits_and_separates_roles(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from odf.modelstudio import service
    s = _env(tmp_path)
    d = create_asset(s, 1, "dataset", "D", DATASET, "admin", enabled=False)
    publish_asset(s, d.id, "admin")
    content = {"dataset_id": d.id,
               "measure": {"agg": "sum", "column": "amount", "as": "value"},
               "dimensions": ["city"], "filters": [],
               "format": {"type": "number"}}
    m = create_asset(s, 1, "metric", "M", content, "admin", enabled=False)
    publish_asset(s, m.id, "admin")
    calls = {"n": 0}

    def fake(*args, **kwargs):
        calls["n"] += 1
        return {"columns": [], "rows": [], "row_count": 0, "ms": 0,
                "sql": ""}

    monkeypatch.setattr(service, "_execute_metric", fake)
    monkeypatch.setattr(service, "get_settings", lambda: SimpleNamespace(
        metric_cache_ttl_s=60, metric_cache_size=10, query_max_rows=10000))
    service.cache.clear()
    first = service.query_metric(s, m.id)
    second = service.query_metric(s, m.id)
    assert calls["n"] == 1
    assert first["cached"] is False and second["cached"] is True
    service.query_metric(s, m.id, role="viewer")
    assert calls["n"] == 2
