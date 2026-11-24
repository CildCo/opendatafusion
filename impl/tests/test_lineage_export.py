import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.db import Base
from odf.lineage import catalog_sync, openlineage
from odf.models import (Asset, AssetVersion, Column, Dataset, DatasetTag,
                        Datasource, Job, LineageEdge, Project, Tag)
from odf.services.platform import update_doc


def _env():
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Project(id=1, code="p", name="P", status=1, environment="dev"))
    s.add(Datasource(id=1, project_id=1, name="warehouse", kind="sqlite",
                     dsn_encrypted="x"))
    s.add(Dataset(id=1, datasource_id=1, schema_name="main",
                  table_name="orders", domain_id=5))
    s.add(Column(dataset_id=1, name="id", data_type="bigint"))
    s.add(Column(dataset_id=1, name="amount", data_type="double"))
    s.add(Tag(id=1, project_id=1, name="core"))
    s.add(DatasetTag(dataset_id=1, tag_id=1))
    asset = Asset(id=1, project_id=1, type="pipeline", key="pipe_1",
                  name="copy", owner="admin", enabled=True)
    s.add(asset)
    s.flush()
    version = AssetVersion(asset_id=1, version=1, status="published",
                           created_by="admin", content_json={"nodes": [
                               {"id": "s", "type": "source",
                                "config": {"datasource_id": 1,
                                           "table": "orders"}},
                               {"id": "t", "type": "sink",
                                "config": {"datasource_id": 1,
                                           "table": "orders_copy"}}],
                               "edges": [{"from": "s", "to": "t"}]})
    s.add(version)
    s.flush()
    asset.draft_version_id = version.id
    asset.published_version_id = version.id
    s.add(Job(id=10, asset_id=1, asset_type="pipeline", status="running",
              attempts=0))
    s.add(LineageEdge(project_id=1, from_type="table", from_id="1:orders",
                      from_ref="1:orders", to_type="table",
                      to_id="1:orders_copy", to_ref="1:orders_copy"))
    s.commit()
    return s


def test_catalog_export_contains_tables_and_assets():
    s = _env()
    payload = catalog_sync.export_project(s, 1)
    assert payload["format"] == "odf-catalog"
    project = payload["projects"][0]
    table = project["datasets"][0]
    assert table["table"] == "orders"
    assert table["tags"] == ["core"]
    assert {c["name"] for c in table["columns"]} == {"id", "amount"}
    assert any(a["key"] == "pipe_1" for a in project["assets"])
    assert project["lineage"][0]["to"] == "1:orders_copy"


def test_openlineage_event_payload(monkeypatch):
    s = _env()
    update_doc(s, {"lineage": {
        "openlineage_url": "http://marquez:5000/api/v1/lineage",
        "namespace": "odf.test"}}, "admin")
    captured = {}

    def fake(url, method="GET", body=None, headers=None, **kwargs):
        captured.update({"url": url, "body": json.loads(body),
                         "headers": headers or {}})
        return 200, {}, b""

    monkeypatch.setattr("odf.services.net.request", fake)
    assert openlineage.emit(s, "START", s.get(Job, 10)) is True
    body = captured["body"]
    assert body["eventType"] == "START"
    assert body["job"]["name"] == "pipe_1"
    assert body["inputs"][0]["name"].endswith("orders")
    assert body["outputs"][0]["name"].endswith("orders_copy")
    update_doc(s, {"lineage": {"openlineage_url": ""}}, "admin")


def test_catalog_push_and_due(monkeypatch):
    s = _env()
    update_doc(s, {"lineage": {
        "catalog_sync_url": "http://catalog.example/ingest",
        "catalog_sync_interval_minutes": 60}}, "admin")
    captured = {}

    def fake(url, method="GET", body=None, headers=None, **kwargs):
        captured["body"] = json.loads(body)
        return 200, {}, b""

    monkeypatch.setattr("odf.services.net.request", fake)
    assert catalog_sync.due(s) is True
    out = catalog_sync.push(s)
    assert out["projects"] == 1
    assert captured["body"]["projects"][0]["code"] == "p"
    assert catalog_sync.due(s) is False
    update_doc(s, {"lineage": {"catalog_sync_url": "",
                               "catalog_sync_interval_minutes": 0}}, "admin")
