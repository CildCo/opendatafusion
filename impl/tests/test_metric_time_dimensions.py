from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from odf.appstudio.content import validate_app
from odf.assets.service import create_asset, publish_asset
from odf.dashboards.content import validate_dashboard
from odf.db import Base
from odf.models import Datasource
from odf.services.crypto import encrypt_secret

DATASET = {"mode": "visual", "query": {
    "datasource_id": 1, "table": "t",
    "select": [{"column": "order_date"}, {"column": "city"},
               {"column": "amount"}],
    "limit": 100}, "params": []}


def _env(tmp_path):
    url = "sqlite:///" + str(tmp_path / "d.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table t (order_date text, city text, "
                       "amount int)"))
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                     dsn_encrypted=encrypt_secret(url)))
    s.commit()
    return s


def _metric(s):
    d = create_asset(s, 1, "dataset", "D", DATASET, "admin", enabled=False)
    publish_asset(s, d.id, "admin")
    mc = {"dataset_id": d.id,
          "measure": {"agg": "sum", "column": "amount", "as": "value"},
          "dimensions": ["city"], "filters": [],
          "time": {"column": "order_date", "grain": "month"},
          "compare": "previous", "format": {"type": "number"}}
    m = create_asset(s, 1, "metric", "M", mc, "admin", enabled=False)
    publish_asset(s, m.id, "admin")
    return m.id


def test_dashboard_chart_uses_time_dimension(tmp_path):
    s = _env(tmp_path)
    mid = _metric(s)
    content = {"columns": 12, "widgets": [
        {"id": "l", "type": "line", "metric_id": mid,
         "dimension": "order_date", "x": 0, "y": 0, "w": 6, "h": 4},
        {"id": "p", "type": "pivot", "metric_id": mid,
         "row_dimension": "order_date", "column_dimension": "city",
         "x": 6, "y": 0, "w": 6, "h": 4}]}
    assert validate_dashboard(s, content, 1) == []


def test_app_metric_accepts_time_column(tmp_path):
    s = _env(tmp_path)
    mid = _metric(s)
    content = {"start_page": "p1", "pages": [{
        "id": "p1", "title": "P", "params": [],
        "components": [
            {"id": "m", "type": "metric", "metric_id": mid,
             "columns": ["order_date", "value"]}]}]}
    assert validate_app(s, content, 1) == []
