import uuid

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from odf.assets.service import create_asset
from odf.db import SessionLocal
from odf.main import app
from odf.models import User
from odf.services.approval import issue_token
from odf.services.auth import create_token
from odf.services.datasource import create_datasource


def _content(ds_id):
    return {
        "mode": "visual",
        "query": {"datasource_id": ds_id, "table": "t",
                  "select": [{"column": "id"}]},
        "sql": None, "params": [],
        "auth": {"type": "aksk", "rate_limit_per_min": 60},
    }


def _setup(tmp_path):
    url = "sqlite:///" + str(tmp_path / "routes.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table t (id int)"))
        c.execute(text("insert into t values (1)"))
    with SessionLocal() as s:
        ds = create_datasource(s, 1, "api-routes-%s" % uuid.uuid4().hex[:8],
                               url, "sqlite")
        return ds.id


def _user(uid, role):
    with SessionLocal() as s:
        u = s.get(User, uid)
        if not u:
            u = User(id=uid, username="api_u%d" % uid,
                     password_hash="x", role=role, active=True)
            s.add(u)
        else:
            u.role = role
            u.active = True
        s.commit()


def _h(uid=1, project=1):
    return {"Authorization": "Bearer " + create_token(uid, project)}


def test_api_lifecycle_and_roles(tmp_path):
    _user(1, "admin")
    _user(2, "viewer")
    content = _content(_setup(tmp_path))
    c = TestClient(app)
    r = c.post("/api/v1/apis", json={"name": "A1", "content": content},
               headers=_h())
    assert r.status_code == 200
    aid = r.json()["id"]
    assert c.get(f"/api/v1/apis/{aid}", headers=_h()).status_code == 200
    assert c.put(f"/api/v1/apis/{aid}/draft", json={"content": content},
                 headers=_h()).status_code == 200
    assert c.put(f"/api/v1/apis/{aid}/draft", json={"content": content},
                 headers=_h(2)).status_code == 403
    assert c.post(f"/api/v1/apis/{aid}/validate",
                  json={"content": content},
                  headers=_h()).json()["valid"] is True
    pid = c.post("/api/v1/apis", json={"name": "bad",
                                       "content": {"mode": "visual"}},
                 headers=_h()).json()["id"]
    assert c.post(f"/api/v1/apis/{pid}/publish?approval_token="
                  + issue_token(pid, "publish_api"),
                  headers=_h()).status_code == 400
    good = c.post(f"/api/v1/apis/{aid}/publish?approval_token="
                  + issue_token(aid, "publish_api"), headers=_h())
    assert good.status_code == 200
    tested = c.post(f"/api/v1/apis/{aid}/test", json={"params": {}},
                    headers=_h())
    assert tested.status_code == 200
    assert tested.json()["row_count"] == 1
    assert c.get(f"/api/v1/apis/{aid}/docs", headers=_h()).json()["path"]


def test_project_isolation(tmp_path):
    _user(1, "admin")
    c = TestClient(app)
    with SessionLocal() as s:
        other = create_asset(s, 2, "api", "other",
                             _content(_setup(tmp_path)), "admin",
                             enabled=False)
        oid = other.id
    assert c.get(f"/api/v1/apis/{oid}", headers=_h()).status_code == 404
