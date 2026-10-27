import uuid

import pytest
from fastapi.testclient import TestClient

from odf.db import SessionLocal
from odf.lakehouse.maintenance import maintain
from odf.main import app
from odf.models import Datasource, User
from odf.services.auth import create_token
from odf.services.crypto import encrypt_secret
from odf.trino.client import TrinoError


class FakeClient:
    catalog = "iceberg"

    def __init__(self, tables=None, fail_on=None):
        self.statements = []
        self._rows = [{"table_name": t, "column_name": "id",
                       "data_type": "bigint"} for t in (tables or ["events"])]
        self._fail_on = fail_on or ()

    def query(self, sql, max_rows=1000):
        return {"columns": [], "rows": self._rows, "row_count": len(self._rows),
                "truncated": False}

    def execute(self, sql):
        if any(name in sql for name in self._fail_on):
            raise TrinoError("boom")
        self.statements.append(sql)


def test_maintain_runs_optimize_then_expire():
    client = FakeClient()
    results = maintain(client, "odf_p1", tables=["events"], retention="7d")
    assert client.statements == [
        "ALTER TABLE \"odf_p1\".\"events\" "
        "EXECUTE optimize(file_size_threshold => '128MB')",
        "ALTER TABLE \"odf_p1\".\"events\" "
        "EXECUTE expire_snapshots(retention_threshold => '7d')",
    ]
    assert results == [{"table": "events", "optimize": "ok", "expire": "ok"}]


def test_maintain_discovers_tables_when_none_given():
    client = FakeClient(tables=["a", "b"])
    results = maintain(client, "odf_p1")
    assert [r["table"] for r in results] == ["a", "b"]
    assert len(client.statements) == 4


def test_maintain_can_skip_expiry():
    client = FakeClient()
    maintain(client, "odf_p1", tables=["events"], expire_snapshots=False)
    assert len(client.statements) == 1
    assert "optimize" in client.statements[0]


def test_maintain_records_failures_per_table():
    client = FakeClient(tables=["good", "bad"], fail_on=["bad"])
    results = maintain(client, "odf_p1", expire_snapshots=False)
    assert results[0]["optimize"] == "ok"
    assert results[1]["optimize"] == "failed"


def test_maintain_rejects_unsafe_identifiers():
    client = FakeClient()
    with pytest.raises(ValueError, match="invalid identifier"):
        maintain(client, "odf_p1", tables=["events; drop table x"])


def _user(uid, role, project_id=1):
    with SessionLocal() as s:
        user = s.get(User, uid)
        if not user:
            user = User(id=uid, username="mt_%d" % uid, password_hash="x",
                        role=role, active=True)
            s.add(user)
        else:
            user.role = role
            user.active = True
        s.commit()
    return {"Authorization": "Bearer " + create_token(uid, project_id)}


def _ds(kind="trino", project_id=1):
    with SessionLocal() as s:
        ds = Datasource(project_id=project_id,
                        name="mt-%s" % uuid.uuid4().hex[:6], kind=kind,
                        dsn_encrypted=encrypt_secret(
                            "trino://odf@trino:8080/iceberg/demo"))
        s.add(ds)
        s.commit()
        s.refresh(ds)
        return ds.id


def test_maintain_route_requires_editor():
    response = TestClient(app).post(
        "/api/v1/lakehouse/maintain", headers=_user(971, "viewer"),
        json={"datasource_id": _ds()})
    assert response.status_code == 403


def test_maintain_route_rejects_non_trino():
    response = TestClient(app).post(
        "/api/v1/lakehouse/maintain", headers=_user(972, "editor"),
        json={"datasource_id": _ds("sqlite")})
    assert response.status_code == 400


def test_maintain_route_returns_results(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr("odf.lakehouse.api.client_for_datasource",
                        lambda ds: fake)
    response = TestClient(app).post(
        "/api/v1/lakehouse/maintain", headers=_user(973, "editor"),
        json={"datasource_id": _ds(), "tables": ["events"]})
    assert response.status_code == 200
    body = response.json()
    assert body["schema"] == "odf_p1"
    assert body["results"][0]["optimize"] == "ok"


def test_maintain_explains_disabled_gc():
    class NoGc(FakeClient):
        def execute(self, sql):
            raise TrinoError(
                "Cannot expire snapshots: GC is disabled (deleting files "
                "may corrupt other tables)")

    results = maintain(NoGc(), "odf_p1", tables=["events"], optimize=False)
    assert results[0]["expire"] == ("failed: snapshot cleanup is "
                                    "disabled for this catalog")
