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
