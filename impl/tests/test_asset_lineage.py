from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.db import Base
from odf.models import Asset, AssetVersion, Datasource, LineageEdge, Project


def _session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(Project(id=1, code="p1", name="P1", status=1))
    session.add(Datasource(project_id=1, name="pg", kind="postgres",
                           dsn_encrypted="x"))
    session.commit()
    return session


def _asset(session, kind, name, content):
    asset = Asset(project_id=1, type=kind, key="%s_%s" % (kind, name),
                  name=name, owner="u")
    session.add(asset)
    session.flush()
    version = AssetVersion(asset_id=asset.id, version=1,
                           content_json=content, status="published",
                           created_by="u")
    session.add(version)
    session.flush()
    asset.published_version_id = version.id
    session.commit()
    return asset


def test_asset_lineage_walks_dataset_metric_api_and_dashboard():
    from odf.services.asset_lineage import asset_lineage
    s = _session()
    ds = s.query(Datasource).first()
    dataset = _asset(s, "dataset", "orders_ds", {
        "mode": "visual",
        "query": {"datasource_id": ds.id, "table": "orders",
                  "select": [{"column": "id"},
                             {"column": "email", "as": "mail"}]},
    })
    metric = _asset(s, "metric", "order_count", {
        "dataset_id": dataset.id,
        "measure": {"agg": "count", "column": "id"},
        "dimensions": ["mail"],
    })
    api = _asset(s, "api", "orders_api", {
        "mode": "visual",
        "query": {"datasource_id": ds.id, "table": "orders",
                  "select": [{"column": "id"}]},
    })
    dashboard = _asset(s, "dashboard", "ops_board", {
        "widgets": [
            {"id": "w1", "type": "table", "dataset_id": dataset.id},
            {"id": "w2", "type": "chart", "metric_id": metric.id},
        ],
    })

    out = asset_lineage(s, 1, dashboard.id)
    ids = {node["id"] for node in out["nodes"]}
    table_ref = "1:orders"
    assert table_ref in ids
    assert "dataset:%d" % dataset.id in ids
    assert "metric:%d" % metric.id in ids
    assert "dashboard:%d" % dashboard.id in ids
    assert "api:%d" % api.id not in ids

    pairs = {(edge["from"], edge["to"]) for edge in out["edges"]}
    assert (table_ref, "dataset:%d" % dataset.id) in pairs
    assert ("dataset:%d" % dataset.id, "metric:%d" % metric.id) in pairs
    assert ("dataset:%d" % dataset.id, "dashboard:%d" % dashboard.id) in pairs
    assert ("metric:%d" % metric.id, "dashboard:%d" % dashboard.id) in pairs

    columns = {(row["from_column"], row["to_column"])
               for row in out["column_edges"]
               if row["to"] == "asset:%d" % dataset.id
               or row["to"] == "dataset:%d" % dataset.id}
    assert ("email", "mail") in columns


def test_asset_lineage_includes_recorded_column_edges_for_tables():
    from odf.services.asset_lineage import asset_lineage
    s = _session()
    ds = s.query(Datasource).first()
    api = _asset(s, "api", "orders_api", {
        "mode": "visual",
        "query": {"datasource_id": ds.id, "table": "orders",
                  "select": [{"column": "id"}]},
    })
    s.add(LineageEdge(project_id=1, from_type="table", from_id="1:orders",
                      from_ref="1:orders", from_column="id",
                      to_type="table", to_id="1:orders_copy",
                      to_ref="1:orders_copy", to_column="id"))
    s.commit()

    out = asset_lineage(s, 1, api.id)
    assert any(row["from_column"] == "id" and row["to_column"] == "id"
               for row in out["column_edges"])


def test_asset_lineage_rejects_other_projects():
    from odf.services.asset_lineage import asset_lineage
    s = _session()
    api = _asset(s, "api", "orders_api", {"mode": "visual", "query": {}})
    assert asset_lineage(s, 2, api.id) is None
