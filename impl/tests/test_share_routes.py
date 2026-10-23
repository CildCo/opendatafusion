from fastapi.testclient import TestClient

from odf.assets.service import create_asset, publish_asset, update_draft
from odf.db import SessionLocal
from odf.main import app
from odf.models import User
from odf.services.auth import create_token

APP = {"start_page": "p1", "pages": [{
    "id": "p1", "title": "P", "params": [],
    "components": [{"id": "t", "type": "text", "text": "shared"}]}]}
DASH = {"widgets": [{"id": "t", "type": "text", "text": "dash",
                     "x": 0, "y": 0, "w": 3, "h": 2}]}


def _user(uid, role):
    with SessionLocal() as s:
        u = s.get(User, uid)
        if not u:
            u = User(id=uid, username="share_u%d" % uid, password_hash="x",
                     role=role, active=True)
            s.add(u)
        else:
            u.role = role
            u.active = True
        s.commit()


def _h(uid=1, project=1):
    return {"Authorization": "Bearer " + create_token(uid, project)}


def _published(kind="app", content=None):
    with SessionLocal() as s:
        a = create_asset(s, 1, kind, "S", content or
                         (APP if kind == "app" else DASH), "admin",
                         enabled=False)
        publish_asset(s, a.id, "admin")
        return a.id


def test_editor_creates_and_revokes_share():
    _user(1, "admin")
    aid = _published()
    c = TestClient(app)
    h = _h()
    r = c.post(f"/api/v1/apps/{aid}/share", json={"expires_days": 7},
               headers=h)
    assert r.status_code == 200
    token = r.json()["token"]
    listed = c.get(f"/api/v1/apps/{aid}/shares", headers=h).json()
    assert listed[0]["active"] is True
    assert "token" not in listed[0]
    pub = c.get("/api/v1/public/share", headers={"X-Share-Token": token})
    assert pub.status_code == 200
    assert pub.json()["content"]["pages"][0]["components"][0]["text"] == "shared"
    data = c.post("/api/v1/public/share/data", json={},
                  headers={"X-Share-Token": token})
    assert data.status_code == 200
    assert data.json()["components"]["t"]["text"] == "shared"
    sid = listed[0]["id"]
    rev = c.post(f"/api/v1/apps/{aid}/shares/{sid}/revoke", headers=h)
    assert rev.status_code == 200
    assert c.get("/api/v1/public/share",
                 headers={"X-Share-Token": token}).status_code == 404


def test_public_requires_header_and_handles_dashboard():
    _user(1, "admin")
    did = _published("dashboard")
    c = TestClient(app)
    assert c.get("/api/v1/public/share").status_code == 404
    r = c.post(f"/api/v1/dashboards/{did}/share",
               json={"expires_days": 1}, headers=_h())
    token = r.json()["token"]
    view = c.get("/api/v1/public/share", headers={"X-Share-Token": token})
    assert view.json()["kind"] == "dashboard"
    data = c.post("/api/v1/public/share/data", json={},
                  headers={"X-Share-Token": token})
    assert data.json()["widgets"]["t"]["text"] == "dash"


def test_viewer_cannot_share_and_projects_are_scoped():
    _user(1, "viewer")
    aid = _published()
    c = TestClient(app)
    assert c.post(f"/api/v1/apps/{aid}/share", json={},
                  headers=_h()).status_code == 403
    _user(1, "admin")
    assert c.post(f"/api/v1/apps/{aid}/share", json={},
                  headers=_h(1, 2)).status_code == 404
    assert c.get(f"/api/v1/apps/{aid}/shares",
                 headers=_h(1, 2)).status_code == 404


def test_public_data_uses_published_content():
    _user(1, "admin")
    aid = _published()
    with SessionLocal() as s:
        draft = {"start_page": "p1", "pages": [{
            "id": "p1", "title": "P", "params": [],
            "components": [{"id": "t", "type": "text", "text": "draft"}]}]}
        update_draft(s, aid, draft, "admin")
    c = TestClient(app)
    token = c.post(f"/api/v1/apps/{aid}/share", json={},
                   headers=_h()).json()["token"]
    data = c.post("/api/v1/public/share/data", json={},
                  headers={"X-Share-Token": token})
    assert data.json()["components"]["t"]["text"] == "shared"
