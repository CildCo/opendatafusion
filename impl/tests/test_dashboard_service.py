from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from odf.assets.service import create_asset, publish_asset
from odf.dashboards.service import dashboard_data
from odf.db import Base
from odf.models import Datasource
from odf.services.crypto import encrypt_secret

DATASET = {"mode": "visual", "query": {
    "datasource_id": 1, "table": "t",
    "select": [{"column": "city"}, {"column": "amount"}],
    "limit": 100}, "params": []}


def _env(tmp_path):
    url = "sqlite:///" + str(tmp_path / "d.db")
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


def _models(s):
    ds = create_asset(s, 1, "dataset", "D", DATASET, "admin", enabled=False)
    publish_asset(s, ds.id, "admin")
    mc = {"dataset_id": ds.id,
          "measure": {"agg": "sum", "column": "amount", "as": "value"},
          "dimensions": ["city"], "filters": [],
          "format": {"type": "number"}}
    m = create_asset(s, 1, "metric", "M", mc, "admin", enabled=False)
    publish_asset(s, m.id, "admin")
    return ds.id, m.id


def test_dashboard_data_widgets(tmp_path):
    s = _env(tmp_path)
    dsid, mid = _models(s)
    content = {"columns": 12, "widgets": [
        {"id": "c", "type": "card", "metric_id": mid,
         "x": 0, "y": 0, "w": 3, "h": 2},
        {"id": "l", "type": "line", "metric_id": mid, "dimension": "city",
         "x": 3, "y": 0, "w": 6, "h": 4},
        {"id": "t", "type": "table", "dataset_id": dsid,
         "x": 9, "y": 0, "w": 3, "h": 4}]}
    d = create_asset(s, 1, "dashboard", "D", content, "admin", enabled=False)
    out = dashboard_data(s, d.id)
    assert out["widgets"]["c"]["rows"][0]["value"] == 15
    assert len(out["widgets"]["l"]["rows"]) == 2
    assert out["widgets"]["t"]["row_count"] == 3


def test_widget_error_is_isolated(tmp_path):
    s = _env(tmp_path)
    from odf.dashboards import service
    content = {"widgets": [
        {"id": "bad", "type": "table", "dataset_id": 999,
         "x": 0, "y": 0, "w": 3, "h": 2},
        {"id": "ok", "type": "text", "text": "ok",
         "x": 3, "y": 0, "w": 3, "h": 2}]}
    out = service._execute_widgets(s, content, 100)
    assert out["bad"]["error"]
    assert out["ok"].get("text") == "ok"


def test_dashboard_param_filters_metric_and_table(tmp_path):
    s = _env(tmp_path)
    dsid, mid = _models(s)
    content = {"params": [{"name": "city", "type": "string"}], "widgets": [
        {"id": "m", "type": "card", "metric_id": mid,
         "x": 0, "y": 0, "w": 3, "h": 2,
         "filters": [{"column": "city", "op": "=", "param": "city"}]},
        {"id": "t", "type": "table", "dataset_id": dsid,
         "x": 3, "y": 0, "w": 3, "h": 2,
         "filters": [{"column": "city", "op": "=", "param": "city"}]}]}
    d = create_asset(s, 1, "dashboard", "D", content, "admin", enabled=False)
    out = dashboard_data(s, d.id, params={"city": "a"})
    assert out["params"]["city"] == "a"
    assert out["widgets"]["m"]["rows"][0]["value"] == 15
    assert out["widgets"]["t"]["row_count"] == 2


def test_dashboard_blank_optional_filter_returns_all(tmp_path):
    s = _env(tmp_path)
    dsid, _ = _models(s)
    content = {"params": [{"name": "city", "type": "string"}], "widgets": [
        {"id": "t", "type": "table", "dataset_id": dsid,
         "x": 0, "y": 0, "w": 3, "h": 2,
         "filters": [{"column": "city", "op": "=", "param": "city"}]}]}
    d = create_asset(s, 1, "dashboard", "D", content, "admin", enabled=False)
    out = dashboard_data(s, d.id, params={"city": ""})
    assert out["widgets"]["t"]["row_count"] == 3


def test_dashboard_required_param_is_enforced(tmp_path):
    s = _env(tmp_path)
    dsid, _ = _models(s)
    content = {"params": [{"name": "city", "type": "string",
                           "required": True}], "widgets": [
        {"id": "t", "type": "table", "dataset_id": dsid,
         "x": 0, "y": 0, "w": 3, "h": 2,
         "filters": [{"column": "city", "op": "=", "param": "city"}]}]}
    d = create_asset(s, 1, "dashboard", "D", content, "admin", enabled=False)
    try:
        dashboard_data(s, d.id)
    except ValueError as e:
        assert "city" in str(e)
    else:
        raise AssertionError("missing required param must fail")


def test_dashboard_cache_hits_and_separates_roles(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from odf.dashboards import service
    s = _env(tmp_path)
    dsid, mid = _models(s)
    content = {"columns": 12, "widgets": [
        {"id": "c", "type": "card", "metric_id": mid,
         "x": 0, "y": 0, "w": 3, "h": 2}]}
    d = create_asset(s, 1, "dashboard", "D", content, "admin", enabled=False)
    calls = {"n": 0}

    def fake(*args, **kwargs):
        calls["n"] += 1
        return {"c": {"columns": [], "rows": [], "row_count": 0,
                      "ms": 0, "error": None}}

    monkeypatch.setattr(service, "_execute_widgets", fake)
    monkeypatch.setattr(service, "get_settings", lambda: SimpleNamespace(
        dashboard_cache_ttl_s=60, dashboard_cache_size=10))
    service.cache.clear()
    first = dashboard_data(s, d.id)
    second = dashboard_data(s, d.id)
    assert calls["n"] == 1
    assert first["cached"] is False and second["cached"] is True
    dashboard_data(s, d.id, role="viewer")
    assert calls["n"] == 2
