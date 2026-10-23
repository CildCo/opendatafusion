from fastapi.testclient import TestClient
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from odf.connectors.sql import insert_for
from odf.db import SessionLocal
from odf.main import app
from odf.models import Datasource, User
from odf.services.auth import create_token
from odf.services.crypto import encrypt_secret
from odf.services.datasource import (normalize_dsn, prepare_connection,
                                     get_dsn)


def test_normalize_mysql_dsn():
    assert normalize_dsn("mysql", "mysql://u:p@h:3306/db") == \
        "mysql+pymysql://u:p@h:3306/db"
    assert normalize_dsn("mariadb", "mariadb://u@h/db") == \
        "mysql+pymysql://u@h/db"
    assert normalize_dsn("mysql", "mysql+pymysql://u@h/db") == \
        "mysql+pymysql://u@h/db"
    assert normalize_dsn("postgres", "postgresql://u@h/db") == \
        "postgresql://u@h/db"


def test_get_dsn_normalizes():
    with SessionLocal() as s:
        ds = Datasource(project_id=1, name="m", kind="mysql",
                        dsn_encrypted=encrypt_secret(
                            "mysql://u:p@h/db"))
        s.add(ds)
        s.commit()
        assert get_dsn(ds).startswith("mysql+pymysql://")


def test_insert_for_supports_mysql():
    assert insert_for("postgresql") is pg_insert
    assert insert_for("sqlite") is sqlite_insert
    assert insert_for("mysql") is mysql_insert
    assert insert_for("mariadb") is mysql_insert


class _Conn:
    def __init__(self):
        self.sql = []

    def execute(self, stmt):
        self.sql.append(str(stmt))


def test_prepare_connection_sets_mysql_ansi_quotes():
    c = _Conn()
    prepare_connection(c, "mysql", 5000)
    assert any("ANSI_QUOTES" in x for x in c.sql)


def _user(uid, role):
    with SessionLocal() as s:
        u = s.get(User, uid)
        if not u:
            u = User(id=uid, username="ds_u%d" % uid, password_hash="x",
                     role=role, active=True)
            s.add(u)
        else:
            u.role = role
            u.active = True
        s.commit()


def _h(uid=1, project=1):
    return {"Authorization": "Bearer " + create_token(uid, project)}


def test_datasource_routes_are_project_scoped():
    _user(1, "admin")
    with SessionLocal() as s:
        s.add(Datasource(project_id=1, name="p1-ds", kind="sqlite",
                         dsn_encrypted=encrypt_secret("sqlite://")))
        s.add(Datasource(project_id=2, name="p2-ds", kind="sqlite",
                         dsn_encrypted=encrypt_secret("sqlite://")))
        s.commit()
    c = TestClient(app)
    rows = c.get("/api/v1/datasources", headers=_h()).json()
    assert rows and all(r["name"] != "p2-ds" for r in rows)
    _user(1, "viewer")
    assert c.post("/api/v1/datasources", json={
        "name": "x", "dsn": "sqlite://", "kind": "sqlite"},
        headers=_h()).status_code == 403


def test_mysql_factory_and_project_creation():
    from types import SimpleNamespace
    from odf.connectors.factory import sink_for, source_for
    ds = SimpleNamespace(kind="mysql")
    assert source_for(ds, {}).__class__.__name__ == "SQLSource"
    assert sink_for(ds, {}).__class__.__name__ == "SQLSink"
    _user(1, "admin")
    c = TestClient(app)
    r = c.post("/api/v1/datasources",
               json={"name": "p2", "dsn": "sqlite://", "kind": "sqlite"},
               headers=_h(1, 2))
    assert r.status_code == 200
    with SessionLocal() as s:
        assert s.get(Datasource, r.json()["id"]).project_id == 2
