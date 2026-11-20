import uuid

from odf.db import SessionLocal
from odf.models import Asset, AssetVersion, Project
from odf.modelstudio import service

PROJECT_ID = 919


def _project():
    with SessionLocal() as s:
        if not s.get(Project, PROJECT_ID):
            s.add(Project(id=PROJECT_ID, code="metric-cat", name="Metric",
                          status=1))
            s.commit()


def _asset(s, kind, name, content, published=True):
    asset = Asset(project_id=PROJECT_ID, type=kind, key=uuid.uuid4().hex,
                  name=name, owner="tester", enabled=True)
    s.add(asset)
    s.commit()
    version = AssetVersion(asset_id=asset.id, version=1,
                           content_json=content,
                           status="published" if published else "draft",
                           created_by="tester")
    s.add(version)
    s.commit()
    if published:
        asset.published_version_id = version.id
    else:
        asset.draft_version_id = version.id
    s.commit()
    return asset


def test_metric_catalog_reports_definition_dataset_and_usage():
    _project()
    with SessionLocal() as s:
        ds = _asset(s, "dataset", "Orders DS",
                    {"mode": "visual", "query": {"select": []}})
        metric = _asset(s, "metric", "Revenue", {
            "dataset_id": ds.id,
            "measure": {"agg": "sum", "column": "amount", "as": "value"},
            "dimensions": ["city"],
            "filters": [],
            "format": {"type": "number", "unit": "CNY", "decimals": 2},
        })
        _asset(s, "dashboard", "Sales board", {
            "widgets": [{"type": "metric", "metric_id": metric.id}],
        })
        _asset(s, "app", "Sales app", {
            "components": [{"type": "metric", "metric_id": metric.id}],
        }, published=False)
        rows = service.metric_catalog(s, PROJECT_ID)
        row = next(r for r in rows if r["id"] == metric.id)
        assert row["dataset_name"] == "Orders DS"
        assert row["measure"]["agg"] == "sum"
        assert row["measure"]["column"] == "amount"
        assert row["dimensions"] == ["city"]
        assert row["usage_count"] == 2
        assert {u["type"] for u in row["usage"]} == {"dashboard", "app"}
        assert any(u["published"] for u in row["usage"])
        assert service.metric_catalog(s, 9999) == []


def test_metric_catalog_handles_missing_content():
    _project()
    with SessionLocal() as s:
        metric = Asset(project_id=PROJECT_ID, type="metric",
                       key=uuid.uuid4().hex, name="Empty metric",
                       owner="tester", enabled=True)
        s.add(metric)
        s.commit()
        rows = service.metric_catalog(s, PROJECT_ID)
        row = next(r for r in rows if r["id"] == metric.id)
        assert row["measure"] == {}
        assert row["usage_count"] == 0


def test_metric_lineage_walks_upstream_tables():
    from odf.models import Datasource, LineageEdge
    from odf.services.crypto import encrypt_secret
    from odf.modelstudio import service

    _project()
    with SessionLocal() as s:
        ds = Datasource(project_id=PROJECT_ID, name="pg-lineage",
                        kind="sqlite",
                        dsn_encrypted=encrypt_secret("sqlite://"))
        s.add(ds)
        s.commit()
        dataset = _asset(s, "dataset", "Orders DS", {
            "mode": "visual",
            "query": {"datasource_id": ds.id, "table": "shop.orders"},
        })
        metric = _asset(s, "metric", "Revenue", {
            "dataset_id": dataset.id,
            "measure": {"agg": "sum", "column": "amount", "as": "value"},
            "dimensions": ["city"],
            "filters": [],
        })
        target = "%d:shop.orders" % ds.id
        s.add_all([
            LineageEdge(project_id=PROJECT_ID, from_type="table",
                        from_id="1", from_ref="1:raw.orders",
                        to_type="table", to_id="2", to_ref=target),
            LineageEdge(project_id=PROJECT_ID, from_type="table",
                        from_id="1", from_ref="1:raw.orders",
                        from_column="amount", to_type="table",
                        to_id="2", to_ref=target, to_column="amount"),
        ])
        s.commit()
        out = service.metric_lineage(s, PROJECT_ID, metric.id)
        assert out["dataset_name"] == "Orders DS"
        assert out["datasource_name"] == "pg-lineage"
        assert out["table"] == "shop.orders"
        refs = {(e["from"], e["to"]) for e in out["edges"]}
        assert ("1:raw.orders", target) in refs
        assert (target, "dataset:%d" % dataset.id) in refs
        assert ("dataset:%d" % dataset.id, "metric:%d" % metric.id) in refs
        assert out["column_edges"][0]["from_column"] == "amount"
        assert service.metric_lineage(s, 9999, metric.id) is None
