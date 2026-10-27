import pytest
from sqlalchemy import create_engine, text

from odf.db import SessionLocal
from odf.models import AuditLog, Datasource
from odf.services.crypto import encrypt_secret
from odf.workbench import federation


def _env(tmp_path):
    urls = {}
    for did, name, ddl, rows in (
            (511, "a", "create table a (id int, name text)",
             "insert into a values (1,'x'),(2,'y')"),
            (512, "b", "create table b (id int, score int)",
             "insert into b values (1,10),(2,20)")):
        url = "sqlite:///" + str(tmp_path / ("%s.db" % name))
        raw = create_engine(url)
        with raw.begin() as c:
            c.execute(text(ddl))
            c.execute(text(rows))
        urls[did] = url
    with SessionLocal() as s:
        for did, pid, name in ((511, 1, "fa"), (512, 1, "fb"),
                               (513, 2, "other")):
            row = s.get(Datasource, did)
            url = urls.get(did, urls[511])
            if row:
                row.dsn_encrypted = encrypt_secret(url)
                row.project_id = pid
                row.kind = "sqlite"
            else:
                s.add(Datasource(id=did, project_id=pid, name=name,
                                 kind="sqlite",
                                 dsn_encrypted=encrypt_secret(url)))
        s.commit()
    return urls


SOURCES = [{"alias": "a", "datasource_id": 511, "table": "a"},
           {"alias": "b", "datasource_id": 512, "table": "b"}]


def test_join_two_sources(tmp_path):
    _env(tmp_path)
    with SessionLocal() as s:
        out = federation.run_federated(
            s, 1, SOURCES,
            "select a.name, b.score from a join b on a.id = b.id "
            "order by a.id", limit=10, actor="u")
        assert out["columns"] == ["name", "score"]
        assert out["rows"] == [{"name": "x", "score": 10},
                               {"name": "y", "score": 20}]
        assert out["truncated"] is False
        row = (s.query(AuditLog).filter_by(action="federated_query")
               .order_by(AuditLog.id.desc()).first())
        assert row.detail_json["row_count"] == 2
        assert "x" not in str(row.detail_json)


def test_bad_aliases_tables_and_projects(tmp_path):
    _env(tmp_path)
    with SessionLocal() as s:
        for sources in (
                [{"alias": "1a", "datasource_id": 511, "table": "a"}],
                [{"alias": "a", "datasource_id": 511, "table": "a"},
                 {"alias": "a", "datasource_id": 512, "table": "b"}],
                [{"alias": "a", "datasource_id": 511, "table": "nope"}],
                [{"alias": "a", "datasource_id": 513, "table": "a"}]):
            with pytest.raises(ValueError):
                federation.run_federated(s, 1, sources, "select * from a",
                                         actor="u")


def test_write_and_file_functions_are_rejected(tmp_path):
    _env(tmp_path)
    with SessionLocal() as s:
        with pytest.raises(ValueError):
            federation.run_federated(s, 1, SOURCES,
                                     "delete from a", actor="u")
        with pytest.raises(ValueError):
            federation.run_federated(
                s, 1, SOURCES,
                "select * from read_csv_auto('/etc/passwd')", actor="u")


def test_oversized_source_is_rejected(tmp_path, monkeypatch):
    _env(tmp_path)
    monkeypatch.setattr(federation, "MAX_SOURCE_ROWS", 1)
    with SessionLocal() as s:
        with pytest.raises(ValueError) as e:
            federation.run_federated(s, 1, SOURCES,
                                     "select * from a", actor="u")
        assert "too large" in str(e.value)


def test_federation_route(tmp_path):
    _env(tmp_path)
    from fastapi.testclient import TestClient
    from odf.main import app
    from odf.models import User
    from odf.services.auth import create_token
    with SessionLocal() as s:
        u = s.get(User, 1)
        if not u:
            u = User(id=1, username="fed", password_hash="x",
                     role="admin", active=True)
            s.add(u)
        else:
            u.active = True
        s.commit()
    c = TestClient(app)
    h = {"Authorization": "Bearer " + create_token(1, 1)}
    r = c.post("/api/v1/workbench/federated",
               json={"sources": SOURCES,
                     "sql": "select count(*) as n from a"}, headers=h)
    assert r.status_code == 200
    assert r.json()["rows"] == [{"n": 2}]
    assert c.post("/api/v1/workbench/federated",
                  json={"sources": SOURCES, "sql": "select * from nope"},
                  headers=h).status_code == 400


def test_file_functions_and_non_sql_sources_are_rejected(tmp_path):
    _env(tmp_path)
    with SessionLocal() as s:
        row = s.get(Datasource, 514)
        if not row:
            s.add(Datasource(id=514, project_id=1, name="http",
                             kind="http", dsn_encrypted=encrypt_secret(
                                 "http://example.invalid")))
            s.commit()
        else:
            row.kind = "http"
            s.commit()
    for sql in ("select * from read_csv_auto('/etc/passwd')",
                "select * from read_text('/etc/passwd')",
                "select * from read_json_auto('/etc/passwd')"):
        with pytest.raises(ValueError):
            federation.run_federated(SessionLocal(), 1, SOURCES, sql,
                                     actor="u")
    with pytest.raises(ValueError):
        federation.run_federated(
            SessionLocal(), 1,
            [{"alias": "h", "datasource_id": 514, "table": "x"}],
            "select 1", actor="u")
