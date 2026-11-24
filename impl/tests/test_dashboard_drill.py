from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from odf.assets.service import create_asset, publish_asset
from odf.dashboards.service import dashboard_drill
from odf.db import Base
from odf.models import Datasource
from odf.services.crypto import encrypt_secret

DATASET = {"mode": "visual", "query": {
    "datasource_id": 1, "table": "t",
    "select": [{"column": "order_date"}, {"column": "city"},
               {"column": "amount"}],
    "limit": 100}, "params": []}


def _env(tmp_path):
    url = "sqlite:///" + str(tmp_path / "drill.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table t (order_date text, city text, "
                       "amount int)"))
        c.execute(text(
            "insert into t values "
            "('2025-12-20','a',4),('2026-01-15','a',10),"
            "('2026-01-20','b',5),('2026-02-03','a',7)"))
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                     dsn_encrypted=encrypt_secret(url)))
    s.commit()
    return s


def _dashboard(s, filters=None):
    d = create_asset(s, 1, "dataset", "D", DATASET, "admin", enabled=False)
    publish_asset(s, d.id, "admin")
    mc = {"dataset_id": d.id,
          "measure": {"agg": "sum", "column": "amount", "as": "value"},
          "dimensions": ["city"], "filters": filters or [],
          "time": {"column": "order_date", "grain": "month"},
          "compare": "none", "format": {"type": "number"}}
    m = create_asset(s, 1, "metric", "M", mc, "admin", enabled=False)
    publish_asset(s, m.id, "admin")
    content = {"columns": 12, "widgets": [
        {"id": "l", "type": "line", "metric_id": m.id,
         "dimension": "order_date", "x": 0, "y": 0, "w": 6, "h": 4}]}
    dash = create_asset(s, 1, "dashboard", "Dash", content, "admin",
                        enabled=False)
    publish_asset(s, dash.id, "admin")
    return dash.id


def test_drill_by_time_bucket_returns_rows_in_bucket(tmp_path):
    s = _env(tmp_path)
    dash = _dashboard(s)
    out = dashboard_drill(s, dash, "l", "order_date", "2026-01-01")
    assert out["row_count"] == 2
    assert {r["city"] for r in out["rows"]} == {"a", "b"}
    assert out["dimension"] == "order_date"


def test_drill_by_dimension_value(tmp_path):
    s = _env(tmp_path)
    dash = _dashboard(s)
    out = dashboard_drill(s, dash, "l", "city", "a")
    assert out["row_count"] == 3
    assert all(r["city"] == "a" for r in out["rows"])


def test_drill_applies_metric_and_widget_filters(tmp_path):
    s = _env(tmp_path)
    dash = _dashboard(s, filters=[{"column": "city", "op": "=",
                                   "value": "a"}])
    out = dashboard_drill(s, dash, "l", "order_date", "2026-01-01")
    assert out["row_count"] == 1
    assert out["rows"][0]["city"] == "a"


def test_drill_rejects_unknown_dimension(tmp_path):
    s = _env(tmp_path)
    dash = _dashboard(s)
    try:
        dashboard_drill(s, dash, "l", "nope", "a")
    except ValueError as error:
        assert "dimension" in str(error)
    else:
        raise AssertionError("unknown dimension must fail")
