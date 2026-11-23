from pathlib import Path

from sqlalchemy import create_engine, text

from odf.assets.service import (create_asset, publish_asset)
from odf.models import Asset, Datasource
from odf.services.crypto import encrypt_secret


SAMPLE_NAME = "示例数据源"


def _sqlite_path(project_id: int) -> Path:
    from odf.filesource import _allowed_roots
    root = _allowed_roots()[0]
    folder = root / "sample"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / ("sample_%d.db" % project_id)


def _fill(path: Path):
    engine = create_engine("sqlite:///%s" % path.as_posix())
    with engine.begin() as conn:
        conn.execute(text(
            "create table if not exists sample_orders ("
            "id integer primary key, order_no text, customer text, "
            "region text, amount numeric, created_at text)"))
        conn.execute(text(
            "create table if not exists sample_orders_clean ("
            "id integer primary key, order_no text, customer text, "
            "region text, amount numeric, created_at text)"))
        count = conn.execute(text(
            "select count(*) from sample_orders")).scalar() or 0
        if not count:
            rows = [
                (i, "SO-%04d" % i, "客户 %d" % ((i % 7) + 1),
                 ["华东", "华南", "华北", "西南"][i % 4],
                 round(120 + i * 37.5, 2),
                 "2026-11-%02d" % ((i % 20) + 1))
                for i in range(1, 41)
            ]
            conn.execute(text(
                "insert into sample_orders values "
                "(:id, :order_no, :customer, :region, :amount, "
                ":created_at)"), [
                dict(zip(("id", "order_no", "customer", "region",
                          "amount", "created_at"), row)) for row in rows])
    engine.dispose()


def _datasource(session, project_id: int):
    existing = (session.query(Datasource)
                .filter_by(project_id=project_id, name=SAMPLE_NAME,
                           kind="sqlite").first())
    if existing:
        return existing
    path = _sqlite_path(project_id)
    _fill(path)
    ds = Datasource(project_id=project_id, name=SAMPLE_NAME, kind="sqlite",
                    dsn_encrypted=encrypt_secret(
                        "sqlite:///%s" % path.as_posix()))
    session.add(ds)
    session.commit()
    session.refresh(ds)
    return ds


def _pipeline_content(ds_id: int):
    return {
        "nodes": [
            {"id": "source_1", "type": "source",
             "position": {"x": 80, "y": 120}, "name": "示例订单",
             "config": {"datasource_id": ds_id,
                        "table": "sample_orders",
                        "cursor_column": "id", "pk": "id"}},
            {"id": "sink_1", "type": "sink",
             "position": {"x": 430, "y": 120}, "name": "清洗后订单",
             "config": {"datasource_id": ds_id,
                        "table": "sample_orders_clean",
                        "mode": "upsert", "pk": ["id"]}},
        ],
        "edges": [{"id": "e1", "from": "source_1", "to": "sink_1"}],
        "settings": {"batch": 500},
    }


def _dataset_content(ds_id: int):
    columns = ["id", "order_no", "customer", "region", "amount",
               "created_at"]
    return {"mode": "visual",
            "query": {"datasource_id": ds_id, "table": "sample_orders",
                      "select": [{"column": c} for c in columns]}}


def _metric_content(dataset_id: int):
    return {"dataset_id": dataset_id,
            "measure": {"agg": "sum", "column": "amount",
                        "as": "revenue"},
            "dimensions": ["region"], "filters": [],
            "format": {"type": "currency", "unit": "CNY", "decimals": 2}}


def _dashboard_content(metric_id: int):
    return {"columns": 12, "row_height": 80, "widgets": [
        {"id": "w1", "type": "card", "metric_id": metric_id,
         "x": 0, "y": 0, "w": 3, "h": 2},
        {"id": "w2", "type": "bar", "metric_id": metric_id,
         "dimension": "region", "x": 3, "y": 0, "w": 9, "h": 4},
        {"id": "w3", "type": "text", "text": "示例看板：按区域查看营收。",
         "x": 0, "y": 2, "w": 3, "h": 2},
    ]}


def _api_content(ds_id: int):
    return {"mode": "visual",
            "query": {"datasource_id": ds_id, "table": "sample_orders",
                      "select": [{"column": "order_no"},
                                 {"column": "region"},
                                 {"column": "amount"}]},
            "params": [], "auth": {"type": "aksk",
                                   "rate_limit_per_min": 60}}


def _find_asset(session, project_id, kind, name):
    return (session.query(Asset)
            .filter_by(project_id=project_id, type=kind, name=name)
            .first())


def _ensure(session, project_id, kind, name, content, actor):
    existing = _find_asset(session, project_id, kind, name)
    if existing:
        return existing
    asset = create_asset(session, project_id, kind, name, content, actor)
    publish_asset(session, asset.id, actor)
    session.refresh(asset)
    return asset


def create_sample(session, project_id: int, actor: str):
    ds = _datasource(session, project_id)
    pipeline = _ensure(session, project_id, "pipeline", "示例 · 订单同步",
                       _pipeline_content(ds.id), actor)
    dataset = _ensure(session, project_id, "dataset", "示例 · 订单明细",
                      _dataset_content(ds.id), actor)
    metric = _ensure(session, project_id, "metric", "示例 · 区域营收",
                     _metric_content(dataset.id), actor)
    dashboard = _ensure(session, project_id, "dashboard", "示例 · 营收看板",
                        _dashboard_content(metric.id), actor)
    api = _ensure(session, project_id, "api", "示例 · 订单查询",
                  _api_content(ds.id), actor)
    return {
        "datasource": {"id": ds.id, "name": ds.name},
        "pipeline": {"id": pipeline.id, "link": "/pipelines/%d" % pipeline.id},
        "dataset": {"id": dataset.id, "link": "/datasets/%d" % dataset.id},
        "metric": {"id": metric.id, "link": "/metrics/%d" % metric.id},
        "dashboard": {"id": dashboard.id,
                      "link": "/dashboards/%d/run" % dashboard.id},
        "api": {"id": api.id, "link": "/apis/%d" % api.id},
    }
