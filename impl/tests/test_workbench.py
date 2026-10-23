import hashlib

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from odf.db import SessionLocal
from odf.main import app
from odf.models import AuditLog, Datasource, User
from odf.services.auth import create_token
from odf.services.crypto import encrypt_secret
from odf.workbench.service import run_query


def _env(tmp_path):
    url = "sqlite:///" + str(tmp_path / "w.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table t (id int, v text)"))
        c.execute(text("insert into t values (1,'a'),(2,'b'),(3,'c')"))
    with SessionLocal() as s:
        for did, pid, name in ((501, 1, "wb"), (502, 2, "wb2")):
            row = s.get(Datasource, did)
            if row:
                row.dsn_encrypted = encrypt_secret(url)
                row.project_id = pid
            else:
                s.add(Datasource(id=did, project_id=pid, name=name,
                                 kind="sqlite",
                                 dsn_encrypted=encrypt_secret(url)))
        s.commit()
    return url


def _user(uid, role):
    with SessionLocal() as s:
        u = s.get(User, uid)
        if not u:
            u = User(id=uid, username="wb_u%d" % uid, password_hash="x",
                     role=role, active=True)
            s.add(u)
        else:
            u.role = role
            u.active = True
        s.commit()


def _h(project=1):
    return {"Authorization": "Bearer " + create_token(1, project)}


def test_run_query_rows_truncation_and_audit(tmp_path):
    _env(tmp_path)
    with SessionLocal() as s:
        out = run_query(s, 1, 501, "select id, v from t order by id",
                        limit=2, actor="u")
        assert out["columns"] == ["id", "v"]
        assert out["row_count"] == 2 and out["truncated"] is True
        assert out["rows"][0] == {"id": 1, "v": "a"}
        row = (s.query(AuditLog).filter_by(action="workbench_query")
               .order_by(AuditLog.id.desc()).first())
        assert row.target == "501"
        assert row.detail_json["sql_sha256"] == hashlib.sha256(
            b"select id, v from t order by id").hexdigest()
        assert "a" not in str(row.detail_json.get("rows", ""))


def test_workbench_rejects_writes_and_other_projects(tmp_path):
    import pytest
    _env(tmp_path)
    with SessionLocal() as s:
        for sql in ("delete from t", "select 1; drop table t"):
            with pytest.raises(ValueError):
                run_query(s, 1, 501, sql, actor="u")
        with pytest.raises(ValueError):
            run_query(s, 1, 502, "select * from t", actor="u")


def test_workbench_route(tmp_path):
    _env(tmp_path)
    _user(1, "editor")
    c = TestClient(app)
    r = c.post("/api/v1/workbench/query",
               json={"datasource_id": 501, "sql": "select * from t",
                     "limit": 10}, headers=_h())
    assert r.status_code == 200
    assert r.json()["row_count"] == 3
    assert c.post("/api/v1/workbench/query",
                  json={"datasource_id": 501,
                        "sql": "update t set v='x'"}, headers=_h()
                  ).status_code == 400
    assert c.post("/api/v1/workbench/query",
                  json={"datasource_id": 502, "sql": "select * from t"},
                  headers=_h()).status_code == 404


def test_workbench_requires_editor(tmp_path):
    _env(tmp_path)
    _user(1, "viewer")
    c = TestClient(app)
    r = c.post("/api/v1/workbench/query",
               json={"datasource_id": 501, "sql": "select * from t"},
               headers=_h())
    assert r.status_code == 403
