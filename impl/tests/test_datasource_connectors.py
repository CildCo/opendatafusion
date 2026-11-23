import json

import pytest
from fastapi.testclient import TestClient

from odf.db import SessionLocal
from odf.main import app
from odf.models import Project, ProjectMember, User
from odf.services.auth import create_token

PROJECT = 940
USER = 9401

POSTGRES = {"host": "db.internal", "port": 5432, "database": "sales",
            "username": "odf", "password": "top-secret",
            "sslmode": "require"}


@pytest.fixture()
def seeded():
    with SessionLocal() as s:
        if not s.get(Project, PROJECT):
            s.add(Project(id=PROJECT, code="conn940", name="conn940",
                          status=1))
        if not s.get(User, USER):
            s.add(User(id=USER, username="conn_admin", password_hash="x",
                       role="admin", active=True))
        if not (s.query(ProjectMember)
                .filter_by(project_id=PROJECT, user_id=USER).first()):
            s.add(ProjectMember(project_id=PROJECT, user_id=USER,
                                role="admin"))
        s.commit()
    yield
    from odf.models import Datasource
    with SessionLocal() as s:
        ids = [d.id for d in s.query(Datasource)
               .filter_by(project_id=PROJECT).all()]
        for ds_id in ids:
            c = TestClient(app)
            c.delete("/api/v1/datasources/%d?force=true" % ds_id,
                     headers=headers())


def headers():
    return {"Authorization": "Bearer " + create_token(USER, PROJECT)}


def test_connector_catalog_is_available(seeded):
    r = TestClient(app).get("/api/v1/datasources/connectors",
                            headers=headers())
    assert r.status_code == 200
    kinds = {row["kind"] for row in r.json()["connectors"]}
    assert {"postgres", "mysql", "trino", "file", "http", "es"} <= kinds
    assert r.json()["groups"]


def test_create_datasource_from_structured_config(seeded):
    c = TestClient(app)
    r = c.post("/api/v1/datasources", headers=headers(), json={
        "name": "sales", "kind": "postgres", "config": POSTGRES})
    assert r.status_code == 200
    assert "top-secret" not in r.json()["dsn"]
    row = next(x for x in c.get("/api/v1/datasources",
                                headers=headers()).json()
               if x["name"] == "sales")
    assert row["config"]["host"] == "db.internal"
    assert row["config"]["password"] == ""
    assert row["config"]["has_password"] is True
    assert "top-secret" not in json.dumps(row)
    assert row["capabilities"]["metadata"] is True


def test_unknown_kind_and_missing_fields_are_rejected(seeded):
    c = TestClient(app)
    bad = c.post("/api/v1/datasources", headers=headers(), json={
        "name": "x", "kind": "not-a-db", "config": {"host": "h"}})
    assert bad.status_code == 400
    missing = c.post("/api/v1/datasources", headers=headers(), json={
        "name": "x", "kind": "postgres",
        "config": {"host": "db", "username": "u"}})
    assert missing.status_code == 400
    assert "required" in missing.json()["detail"]


def test_test_before_save_reports_an_error(seeded):
    c = TestClient(app)
    r = c.post("/api/v1/datasources/test", headers=headers(), json={
        "kind": "file", "config": {"path": "/no/such/file.csv"}})
    assert r.status_code == 200
    assert r.json()["ok"] is False
    assert r.json()["error"]


def test_http_source_sync_explains_the_capability(seeded):
    c = TestClient(app)
    created = c.post("/api/v1/datasources", headers=headers(), json={
        "name": "api", "kind": "http",
        "config": {"url": "https://api.example.com"}})
    ds_id = created.json()["id"]
    sync = c.post("/api/v1/datasources/%d/sync" % ds_id,
                  headers=headers())
    assert sync.status_code == 400
    assert "pipeline connector" in sync.json()["detail"]


def test_es_metadata_sync_creates_indices(seeded, monkeypatch):
    payloads = {
        "/_cat/indices?format=json&h=index": [
            {"index": "orders"}, {"index": ".kibana"}],
        "/orders/_mapping": {"orders": {"mappings": {"properties": {
            "id": {"type": "long"}, "name": {"type": "text"}}}}},
    }

    def fake_request(url, **kwargs):
        for suffix, body in payloads.items():
            if url.endswith(suffix):
                return 200, {}, json.dumps(body).encode()
        raise AssertionError("unexpected URL " + url)

    monkeypatch.setattr("odf.services.net.request", fake_request)
    c = TestClient(app)
    created = c.post("/api/v1/datasources", headers=headers(), json={
        "name": "search", "kind": "es",
        "config": {"url": "http://es.internal:9200"}})
    ds_id = created.json()["id"]
    sync = c.post("/api/v1/datasources/%d/sync" % ds_id,
                  headers=headers())
    assert sync.status_code == 200, sync.text
    assert sync.json()["tables"] == 1
    tables = c.get("/api/v1/datasources/%d/tables" % ds_id,
                   headers=headers()).json()
    row = next(t for t in tables if t["table"] == "orders")
    assert row["schema"] == "es"
    assert {c["name"] for c in row["columns"]} == {"id", "name"}


def test_edit_without_password_keeps_the_stored_secret(seeded):
    from odf.models import Datasource
    from odf.services.datasource import get_dsn
    c = TestClient(app)
    created = c.post("/api/v1/datasources", headers=headers(), json={
        "name": "edit me", "kind": "postgres", "config": POSTGRES})
    ds_id = created.json()["id"]
    r = c.put("/api/v1/datasources/%d" % ds_id, headers=headers(), json={
        "name": "renamed", "config": {"host": "db2.internal",
                                      "password": ""}})
    assert r.status_code == 200, r.text
    with SessionLocal() as s:
        dsn = get_dsn(s.get(Datasource, ds_id))
    assert "db2.internal" in dsn
    assert "top-secret" in dsn


def test_duckdb_datasource_is_usable(seeded, tmp_path):
    import duckdb
    path = tmp_path / "analytics.duckdb"
    con = duckdb.connect(str(path))
    try:
        con.execute("create table events(id integer, name varchar)")
        con.execute("insert into events values (1, 'a'), (2, 'b')")
    finally:
        con.close()
    c = TestClient(app)
    created = c.post("/api/v1/datasources", headers=headers(), json={
        "name": "duck", "kind": "duckdb", "config": {"path": str(path)}})
    assert created.status_code == 200, created.text
    ds_id = created.json()["id"]
    assert c.post("/api/v1/datasources/%d/test" % ds_id,
                  headers=headers()).json()["ok"] is True
    sync = c.post("/api/v1/datasources/%d/sync" % ds_id, headers=headers())
    assert sync.status_code == 200, sync.text
    tables = c.get("/api/v1/datasources/%d/tables" % ds_id,
                   headers=headers()).json()
    row = next(t for t in tables if t["table"] == "events")
    assert {c["name"] for c in row["columns"]} == {"id", "name"}


def test_mongodb_probe_and_metadata(seeded, monkeypatch):
    assert __import__("odf.connectors.mongo", fromlist=["x"])
    monkeypatch.setattr("odf.connectors.mongo.ping", lambda dsn, timeout=5: True)
    monkeypatch.setattr("odf.connectors.mongo.collections", lambda dsn, timeout=5: [
        {"schema": "app", "table": "orders", "columns": [
            {"name": "_id", "type": "object"},
            {"name": "total", "type": "double"}]}])
    c = TestClient(app)
    created = c.post("/api/v1/datasources", headers=headers(), json={
        "name": "mongo", "kind": "mongodb",
        "config": {"host": "mongo", "port": 27017, "database": "app",
                   "username": "odf", "password": "pw"}})
    assert created.status_code == 200, created.text
    ds_id = created.json()["id"]
    assert c.post("/api/v1/datasources/%d/test" % ds_id,
                  headers=headers()).json()["ok"] is True
    sync = c.post("/api/v1/datasources/%d/sync" % ds_id, headers=headers())
    assert sync.status_code == 200, sync.text
    tables = c.get("/api/v1/datasources/%d/tables" % ds_id,
                   headers=headers()).json()
    assert tables[0]["schema"] == "app"
    assert {x["name"] for x in tables[0]["columns"]} == {"_id", "total"}


def test_kafka_probe_and_pipeline_only_metadata(seeded, monkeypatch):
    monkeypatch.setattr("odf.connectors.kafka.ping", lambda dsn, timeout=5: True)
    c = TestClient(app)
    created = c.post("/api/v1/datasources", headers=headers(), json={
        "name": "events", "kind": "kafka",
        "config": {"bootstrap": "kafka:9092"}})
    assert created.status_code == 200, created.text
    ds_id = created.json()["id"]
    assert c.post("/api/v1/datasources/%d/test" % ds_id,
                  headers=headers()).json()["ok"] is True
    sync = c.post("/api/v1/datasources/%d/sync" % ds_id, headers=headers())
    assert sync.status_code == 400
    assert "pipeline connector" in sync.json()["detail"]


def test_s3_probe_and_metadata(seeded, monkeypatch):
    import json as _json
    monkeypatch.setattr("odf.connectors.s3.ping", lambda dsn: True)
    monkeypatch.setattr("odf.connectors.s3.table_name", lambda opts: "orders")
    monkeypatch.setattr("odf.connectors.s3.describe", lambda dsn: [
        {"key": "folder/orders.parquet", "table": "orders", "columns": [
            {"name": "id", "type": "BIGINT"},
            {"name": "name", "type": "VARCHAR"}]}])
    c = TestClient(app)
    created = c.post("/api/v1/datasources", headers=headers(), json={
        "name": "lake", "kind": "s3",
        "config": {"endpoint": "http://minio:9000", "bucket": "warehouse",
                   "key": "folder/orders.parquet", "access_key": "ak",
                   "secret_key": "sk", "region": "us-east-1"}})
    assert created.status_code == 200, created.text
    assert "sk" not in created.json()["dsn"]
    ds_id = created.json()["id"]
    row = next(x for x in c.get("/api/v1/datasources", headers=headers()).json()
               if x["id"] == ds_id)
    assert row["config"]["secret_key"] == ""
    assert row["config"]["access_key"] == "ak"
    assert "sk" not in _json.dumps(row)
    assert c.post("/api/v1/datasources/%d/test" % ds_id,
                  headers=headers()).json()["ok"] is True
    sync = c.post("/api/v1/datasources/%d/sync" % ds_id, headers=headers())
    assert sync.status_code == 200, sync.text
    tables = c.get("/api/v1/datasources/%d/tables" % ds_id,
                   headers=headers()).json()
    assert tables[0]["schema"] == "file"
    assert {x["name"] for x in tables[0]["columns"]} == {"id", "name"}


def test_hive_probe_and_metadata(seeded, monkeypatch):
    monkeypatch.setattr("odf.connectors.hive.ping", lambda dsn: True)
    monkeypatch.setattr("odf.connectors.hive.tables", lambda dsn: [
        {"schema": "default", "table": "events", "columns": [
            {"name": "id", "type": "bigint"},
            {"name": "name", "type": "string"}]}])
    c = TestClient(app)
    created = c.post("/api/v1/datasources", headers=headers(), json={
        "name": "hive", "kind": "hive",
        "config": {"host": "hive", "port": 10000, "database": "default",
                   "username": "odf", "password": "pw", "auth": "NOSASL"}})
    assert created.status_code == 200, created.text
    ds_id = created.json()["id"]
    assert c.post("/api/v1/datasources/%d/test" % ds_id,
                  headers=headers()).json()["ok"] is True
    sync = c.post("/api/v1/datasources/%d/sync" % ds_id, headers=headers())
    assert sync.status_code == 200, sync.text
    tables = c.get("/api/v1/datasources/%d/tables" % ds_id,
                   headers=headers()).json()
    assert tables[0]["schema"] == "default"
    assert {x["name"] for x in tables[0]["columns"]} == {"id", "name"}


def test_dm_probe_and_metadata(seeded, monkeypatch):
    monkeypatch.setattr("odf.connectors.dm.ping", lambda dsn: True)
    monkeypatch.setattr("odf.connectors.dm.tables", lambda dsn: [
        {"schema": "APP", "table": "ORDERS", "columns": [
            {"name": "ID", "type": "BIGINT"},
            {"name": "TOTAL", "type": "DECIMAL"}]}])
    c = TestClient(app)
    created = c.post("/api/v1/datasources", headers=headers(), json={
        "name": "dm", "kind": "dm",
        "config": {"host": "dm", "port": 5236, "username": "SYSDBA",
                   "password": "pw", "schema": "APP"}})
    assert created.status_code == 200, created.text
    ds_id = created.json()["id"]
    assert c.post("/api/v1/datasources/%d/test" % ds_id,
                  headers=headers()).json()["ok"] is True
    sync = c.post("/api/v1/datasources/%d/sync" % ds_id, headers=headers())
    assert sync.status_code == 200, sync.text
    tables = c.get("/api/v1/datasources/%d/tables" % ds_id,
                   headers=headers()).json()
    assert tables[0]["schema"] == "APP"
    assert {x["name"] for x in tables[0]["columns"]} == {"ID", "TOTAL"}
