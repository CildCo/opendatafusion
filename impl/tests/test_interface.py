from odf.services.interface import render_sql


def test_render_uses_bind_params():
    sql, binds = render_sql("select * from t where a = ${a}", {"a": 1})
    assert ":a" in sql and binds == {"a": 1}


def test_param_value_is_not_concatenated():
    sql, binds = render_sql("select * from t where a = ${a}",
                            {"a": "1; drop table x"})
    assert "drop table" not in sql
    assert binds["a"] == "1; drop table x"


PROJECT = 917
OTHER = 918
DS_ID = 9710
IFACE_ID = 9711


def _setup():
    from odf.db import SessionLocal
    from odf.models import Datasource, Interface, Project

    with SessionLocal() as s:
        for pid, code in ((PROJECT, "iface917"), (OTHER, "iface918")):
            if not s.get(Project, pid):
                s.add(Project(id=pid, code=code, name=code, status=1))
        if not s.get(Datasource, DS_ID):
            s.add(Datasource(id=DS_ID, project_id=PROJECT, name="iface-ds",
                             kind="sqlite", dsn_encrypted="x"))
        s.query(Interface).filter_by(id=IFACE_ID).delete()
        s.add(Interface(id=IFACE_ID, project_id=PROJECT,
                        datasource_id=DS_ID, interface_key="ifacekey9711",
                        name="iface-9711", sql_text="select 1",
                        params_json=[], output_json=[], status=0))
        s.commit()


def _headers(project=PROJECT):
    from odf.db import SessionLocal
    from odf.models import User
    from odf.services.auth import create_token
    with SessionLocal() as s:
        if not s.get(User, 917):
            s.add(User(id=917, username="iface_u", password_hash="x",
                       role="admin", active=True))
            s.commit()
    return {"Authorization": "Bearer " + create_token(917, project)}


def test_interface_routes_are_project_scoped():
    from fastapi.testclient import TestClient
    from odf.main import app

    _setup()
    c = TestClient(app)
    rows = c.get("/api/v1/interfaces?project_id=%d" % OTHER,
                 headers=_headers()).json()
    assert IFACE_ID in [r["id"] for r in rows]
    other = _headers(OTHER)
    assert c.get("/api/v1/interfaces/%d" % IFACE_ID,
                 headers=other).status_code == 404
    assert c.post("/api/v1/interfaces/%d/execute" % IFACE_ID, json={},
                  headers=other).status_code == 404
    r = c.post("/api/v1/interfaces", headers=_headers(),
               json={"project_id": OTHER, "datasource_id": DS_ID,
                     "name": "cross", "sql_text": "select 1"})
    assert r.status_code == 403


def test_delete_interface_removes_it_and_audits():
    from fastapi.testclient import TestClient
    from odf.db import SessionLocal
    from odf.main import app
    from odf.models import Interface

    _setup()
    c = TestClient(app)
    assert c.delete("/api/v1/interfaces/%d" % IFACE_ID,
                    headers=_headers(OTHER)).status_code == 404
    assert c.delete("/api/v1/interfaces/%d" % IFACE_ID,
                    headers=_headers()).status_code == 204
    with SessionLocal() as s:
        assert not s.get(Interface, IFACE_ID)
