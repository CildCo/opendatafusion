import uuid

import pytest
from fastapi.testclient import TestClient

from odf.db import SessionLocal
from odf.lakehouse.service import (ensure_schema, list_tables,
                                   project_schema, table_columns)
from odf.main import app
from odf.models import Datasource, User
from odf.services.auth import create_token
from odf.services.crypto import encrypt_secret


class FakeClient:
    def __init__(self, rows=None, catalog="iceberg"):
        self.catalog = catalog
        self.statements = []
        self.rows = rows or []

    def query(self, sql, max_rows=1000):
        self.statements.append(sql)
        return {"columns": ["table_name", "column_name", "data_type"],
                "rows": self.rows, "row_count": len(self.rows),
                "truncated": False}

    def execute(self, sql):
        self.statements.append(sql)


@pytest.fixture()
def session():
    with SessionLocal() as s:
        yield s


def _user(uid, role, project_id=1):
    with SessionLocal() as s:
        user = s.get(User, uid)
        if not user:
            user = User(id=uid, username="lh_%d" % uid, password_hash="x",
                        role=role, active=True)
            s.add(user)
        else:
            user.role = role
            user.active = True
        s.commit()
    return {"Authorization": "Bearer " + create_token(uid, project_id)}


def _ds(session, project_id=1, kind="trino"):
    ds = Datasource(project_id=project_id,
                    name="lake-%s" % uuid.uuid4().hex[:6], kind=kind,
                    dsn_encrypted=encrypt_secret(
                        "trino://odf@trino:8080/iceberg/demo"))
    session.add(ds)
    session.commit()
    session.refresh(ds)
    return ds


def test_project_schema_is_stable():
    assert project_schema(7) == "odf_p7"
    assert project_schema(7) == project_schema(7)


def test_ensure_schema_creates_namespace():
    client = FakeClient()
    ensure_schema(client, 3)
    assert client.statements == [
        'CREATE SCHEMA IF NOT EXISTS "iceberg"."odf_p3"']


def test_list_tables_groups_columns():
    client = FakeClient([
        {"table_name": "events", "column_name": "id",
         "data_type": "bigint"},
        {"table_name": "events", "column_name": "name",
         "data_type": "varchar"},
        {"table_name": "orders", "column_name": "id",
         "data_type": "bigint"},
    ])
    tables = list_tables(client, "odf_p1")
    assert [t["table"] for t in tables] == ["events", "orders"]
    assert tables[0]["columns"] == [{"name": "id", "type": "bigint"},
                                    {"name": "name", "type": "varchar"}]
    assert "table_schema = 'odf_p1'" in client.statements[0]


def test_table_columns_filters_table():
    client = FakeClient([
        {"table_name": "events", "column_name": "id",
         "data_type": "bigint"}])
    assert table_columns(client, "odf_p1", "events") == [
        {"name": "id", "type": "bigint"}]
    assert "table_name = 'events'" in client.statements[0]


def test_tables_route_uses_project_schema(monkeypatch, session):
    ds = _ds(session)
    fake = FakeClient([{"table_name": "events", "column_name": "id",
                        "data_type": "bigint"}])
    monkeypatch.setattr("odf.lakehouse.service.client_for_datasource",
                        lambda d: fake)
    monkeypatch.setattr("odf.lakehouse.api.client_for_datasource",
                        lambda d: fake)
    response = TestClient(app).get(
        "/api/v1/lakehouse/tables?datasource_id=%d" % ds.id,
        headers=_user(931, "viewer"))
    assert response.status_code == 200
    body = response.json()
    assert body["schema"] == "odf_p1"
    assert body["tables"][0]["table"] == "events"


def test_tables_route_rejects_foreign_datasource(session):
    ds = _ds(session, project_id=2)
    response = TestClient(app).get(
        "/api/v1/lakehouse/tables?datasource_id=%d" % ds.id,
        headers=_user(932, "viewer", 1))
    assert response.status_code == 404


def test_sync_route_rejects_non_trino(session):
    ds = _ds(session, kind="sqlite")
    response = TestClient(app).post(
        "/api/v1/lakehouse/sync",
        json={"datasource_id": ds.id}, headers=_user(933, "editor"))
    assert response.status_code == 400


def test_sync_route_syncs_trino(monkeypatch, session):
    ds = _ds(session)
    monkeypatch.setattr("odf.lakehouse.api.sync_datasource",
                        lambda s, did: 3)
    response = TestClient(app).post(
        "/api/v1/lakehouse/sync", json={"datasource_id": ds.id},
        headers=_user(934, "editor"))
    assert response.status_code == 200
    assert response.json() == {"datasource_id": ds.id, "tables": 3}


def test_schema_route_creates_namespace(monkeypatch, session):
    ds = _ds(session)
    fake = FakeClient()
    monkeypatch.setattr("odf.lakehouse.api.client_for_datasource",
                        lambda d: fake)
    response = TestClient(app).post(
        "/api/v1/lakehouse/schema", json={"datasource_id": ds.id},
        headers=_user(935, "editor"))
    assert response.status_code == 200
    assert response.json()["schema"] == "odf_p1"
    assert fake.statements == ['CREATE SCHEMA IF NOT EXISTS "iceberg"."odf_p1"']


def test_tables_route_prefers_the_datasource_schema(monkeypatch, session):
    ds = _ds(session)
    fake = FakeClient([{"table_name": "events", "column_name": "id",
                        "data_type": "bigint"}])
    fake.schema = "demo"
    monkeypatch.setattr("odf.lakehouse.api.client_for_datasource",
                        lambda d: fake)
    response = TestClient(app).get(
        "/api/v1/lakehouse/tables?datasource_id=%d" % ds.id,
        headers=_user(936, "viewer"))
    assert response.status_code == 200
    assert response.json()["schema"] == "demo"


def _boom_client(message):
    class Boom:
        catalog = "iceberg"
        schema = ""

        def query(self, sql, max_rows=1000):
            raise ValueError(message)

        def execute(self, sql):
            raise ValueError(message)

    return Boom()


def test_tables_route_does_not_echo_error_text(monkeypatch, session):
    ds = _ds(session)
    monkeypatch.setattr("odf.lakehouse.api.client_for_datasource",
                        lambda d: _boom_client("internal detail: table x"))
    response = TestClient(app).get(
        "/api/v1/lakehouse/tables?datasource_id=%d" % ds.id,
        headers=_user(937, "viewer"))
    assert response.status_code == 400
    assert "internal detail" not in response.text


def test_columns_route_does_not_echo_error_text(monkeypatch, session):
    ds = _ds(session)
    monkeypatch.setattr("odf.lakehouse.api.client_for_datasource",
                        lambda d: _boom_client("internal detail: column y"))
    response = TestClient(app).get(
        "/api/v1/lakehouse/tables/events/columns?datasource_id=%d" % ds.id,
        headers=_user(938, "viewer"))
    assert response.status_code == 400
    assert "internal detail" not in response.text


def test_schema_route_does_not_echo_error_text(monkeypatch, session):
    ds = _ds(session)
    monkeypatch.setattr("odf.lakehouse.api.client_for_datasource",
                        lambda d: _boom_client("internal detail: schema z"))
    response = TestClient(app).post(
        "/api/v1/lakehouse/schema", json={"datasource_id": ds.id},
        headers=_user(939, "editor"))
    assert response.status_code == 400
    assert "internal detail" not in response.text


def test_sync_route_does_not_echo_error_text(monkeypatch, session):
    ds = _ds(session)

    def boom(session_, datasource_id):
        raise ValueError("internal detail: sync w")

    monkeypatch.setattr("odf.lakehouse.api.sync_datasource", boom)
    response = TestClient(app).post(
        "/api/v1/lakehouse/sync", json={"datasource_id": ds.id},
        headers=_user(940, "editor"))
    assert response.status_code == 400
    assert "internal detail" not in response.text
