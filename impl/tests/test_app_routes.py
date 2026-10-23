from fastapi.testclient import TestClient

from odf.db import SessionLocal
from odf.main import app
from odf.models import User
from odf.services.approval import issue_token
from odf.services.auth import create_token


def _user(uid, role):
    with SessionLocal() as s:
        u = s.get(User, uid)
        if not u:
            u = User(id=uid, username="app_u%d" % uid,
                     password_hash="x", role=role, active=True)
            s.add(u)
        else:
            u.role = role
            u.active = True
        s.commit()


def _h(uid=1, project=1):
    return {"Authorization": "Bearer " + create_token(uid, project)}


TEXT_APP = {"start_page": "p1", "pages": [
    {"id": "p1", "title": "P", "params": [],
     "components": [{"id": "t", "type": "text", "text": "hello"}]}]}


def test_app_routes_and_publish():
    _user(1, "admin")
    c = TestClient(app)
    h = _h()
    r = c.post("/api/v1/apps", json={"name": "A", "content": TEXT_APP},
               headers=h)
    assert r.status_code == 200
    aid = r.json()["id"]
    assert c.get(f"/api/v1/apps/{aid}", headers=h).status_code == 200
    d = c.post(f"/api/v1/apps/{aid}/data", json={"content": TEXT_APP},
               headers=h)
    assert d.status_code == 200
    assert d.json()["components"]["t"]["text"] == "hello"
    p = c.post(f"/api/v1/apps/{aid}/publish?approval_token="
               + issue_token(aid, "publish_app"), headers=h)
    assert p.status_code == 200
    got = c.get(f"/api/v1/apps/{aid}", headers=h).json()
    assert got["published_version"] == 1


def test_published_data_and_invalid_page():
    _user(1, "admin")
    c = TestClient(app)
    h = _h()
    aid = c.post("/api/v1/apps", json={"name": "A", "content": TEXT_APP},
                 headers=h).json()["id"]
    assert c.post(f"/api/v1/apps/{aid}/data", json={"published": True},
                  headers=h).status_code == 400
    c.post(f"/api/v1/apps/{aid}/publish?approval_token="
           + issue_token(aid, "publish_app"), headers=h)
    r = c.post(f"/api/v1/apps/{aid}/data", json={"published": True},
               headers=h)
    assert r.status_code == 200
    assert r.json()["components"]["t"]["text"] == "hello"
    bad = c.post(f"/api/v1/apps/{aid}/data",
                 json={"content": {"pages": []}}, headers=h)
    assert bad.status_code == 400


def test_validate_and_cross_project_isolation():
    _user(1, "admin")
    c = TestClient(app)
    aid = c.post("/api/v1/apps", json={"name": "A", "content": TEXT_APP},
                 headers=_h()).json()["id"]
    v = c.post(f"/api/v1/apps/{aid}/validate",
               json={"content": {"start_page": "x", "pages": []}},
               headers=_h())
    assert v.status_code == 200 and not v.json()["valid"]
    other = _h(1, 2)
    assert c.get(f"/api/v1/apps/{aid}", headers=other).status_code == 404
    assert c.post(f"/api/v1/apps/{aid}/data", json={},
                  headers=other).status_code == 404


def test_rollback_app_restores_previous_content():
    _user(1, "admin")
    c = TestClient(app)
    h = _h()
    aid = c.post("/api/v1/apps", json={"name": "A", "content": TEXT_APP},
                 headers=h).json()["id"]
    c.post(f"/api/v1/apps/{aid}/publish?approval_token="
           + issue_token(aid, "publish_app"), headers=h)
    v2 = {"start_page": "p1", "pages": [
        {"id": "p1", "title": "P", "params": [],
         "components": [{"id": "t", "type": "text", "text": "v2"}]}]}
    c.put(f"/api/v1/apps/{aid}/draft", json={"content": v2}, headers=h)
    c.post(f"/api/v1/apps/{aid}/publish?approval_token="
           + issue_token(aid, "publish_app"), headers=h)
    r = c.post(f"/api/v1/apps/{aid}/rollback?approval_token="
               + issue_token(aid, "rollback_app"),
               json={"version": 1}, headers=h)
    assert r.status_code == 200 and r.json()["version"] == 3
    got = c.get(f"/api/v1/apps/{aid}", headers=h).json()
    assert got["published"]["pages"][0]["components"][0]["text"] == "hello"


def test_changes_cannot_cross_projects():
    import pytest
    from odf.assets.service import create_asset
    from odf.services.changes import apply, propose

    _user(1, "admin")
    c = TestClient(app)
    with SessionLocal() as s:
        a = create_asset(s, 2, "app", "other", TEXT_APP, "admin",
                         enabled=False)
        aid = a.id
        cid = propose(s, 2, "admin", "publish_app", aid).id
    r = c.post("/api/v1/changes",
               json={"project_id": 2, "action": "publish_app",
                     "target": aid}, headers=_h(1, 1))
    assert r.status_code == 403
    assert c.post(f"/api/v1/changes/{cid}/approve",
                  headers=_h(1, 1)).status_code == 404
    with SessionLocal() as s:
        c2 = propose(s, 1, "admin", "publish_app", aid)
    with pytest.raises(ValueError):
        apply(SessionLocal(), c2.id, issue_token(aid, "publish_app"))
