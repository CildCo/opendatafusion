from fastapi.testclient import TestClient

from odf.assets.service import create_asset
from odf.db import SessionLocal
from odf.main import app
from odf.models import AssetVersion, Project, ProjectMember, User
from odf.services.auth import create_token


def _user(uid, role, active=True):
    with SessionLocal() as s:
        u = s.get(User, uid)
        if not u:
            u = User(id=uid, username="gov%d" % uid, password_hash="x",
                     role=role, active=active)
            s.add(u)
        else:
            u.role = role
            u.active = active
        s.commit()


def _h(uid=1, project=1):
    return {"Authorization": "Bearer " + create_token(uid, project)}


def _api(project=1):
    with SessionLocal() as s:
        a = create_asset(s, project, "api", "Gov API", {
            "mode": "sql", "query": {"datasource_id": 1},
            "sql": "select 1 as n", "params": [],
            "auth": {"type": "aksk", "rate_limit_per_min": 60}},
            "admin", enabled=False)
        v = s.get(AssetVersion, a.draft_version_id)
        v.status = "published"
        a.published_version_id = v.id
        a.enabled = True
        s.commit()
        return a.id, a.key


def _projects():
    with SessionLocal() as s:
        for pid, code in ((1, "g1"), (2, "g2")):
            if not s.get(Project, pid):
                s.add(Project(id=pid, code=code, name=code, status=1))
        s.commit()


def test_project_listing_and_switch():
    _projects()
    _user(1, "admin")
    c = TestClient(app)
    mine = c.get("/api/v1/projects/mine", headers=_h())
    assert mine.status_code == 200
    assert {p["id"] for p in mine.json()} >= {1, 2}
    sw = c.post("/api/v1/auth/switch-project", json={"project_id": 2},
                headers=_h())
    assert sw.status_code == 200 and sw.json()["token"]
    _user(2, "viewer")
    with SessionLocal() as s:
        s.query(ProjectMember).filter_by(user_id=2).delete(
            synchronize_session=False)
        s.commit()
    assert c.get("/api/v1/projects/mine", headers=_h(2, 1)).json() == []
    with SessionLocal() as s:
        if not s.query(ProjectMember).filter_by(project_id=1,
                                                user_id=2).first():
            s.add(ProjectMember(project_id=1, user_id=2, role="viewer"))
            s.commit()
    assert [p["id"] for p in c.get("/api/v1/projects/mine",
                                   headers=_h(2, 1)).json()] == [1]
    with SessionLocal() as s:
        u = s.get(User, 2)
        u.active = False
        s.commit()
    assert c.post("/api/v1/auth/switch-project", json={"project_id": 1},
                  headers=_h(2, 1)).status_code == 401
    _user(2, "viewer")


def test_catalog_request_approve_and_grants():
    _projects()
    _user(1, "admin")
    aid, key = _api()
    c = TestClient(app)
    cat = c.get("/api/v1/api-catalog", headers=_h(1, 2)).json()
    assert any(x["id"] == aid for x in cat)
    assert all("sql" not in x for x in cat)
    req = c.post("/api/v1/api-requests",
                 json={"asset_id": aid, "note": "need"},
                 headers=_h(1, 2))
    assert req.status_code == 200
    rid = req.json()["id"]
    assert c.post(f"/api/v1/api-requests/{rid}/approve",
                  headers=_h(1, 2)).status_code == 404
    ok = c.post(f"/api/v1/api-requests/{rid}/approve", headers=_h(1, 1))
    assert ok.status_code == 200 and ok.json()["status"] == "approved"
    grants = c.get("/api/v1/api-grants", headers=_h(1, 1)).json()
    assert grants[0]["asset_id"] == aid
    assert c.get("/api/v1/api-grants", headers=_h(1, 2)).json() == []
    assert c.delete(f"/api/v1/api-grants/{grants[0]['id']}",
                    headers=_h(1, 2)).status_code == 404
    assert c.delete(f"/api/v1/api-grants/{grants[0]['id']}",
                    headers=_h(1, 1)).status_code == 200
    assert key


def test_outgoing_and_incoming_requests():
    _projects()
    _user(1, "admin")
    aid, _ = _api()
    c = TestClient(app)
    c.post("/api/v1/api-requests", json={"asset_id": aid},
           headers=_h(1, 2))
    outgoing = c.get("/api/v1/api-requests?direction=outgoing",
                     headers=_h(1, 2)).json()
    incoming = c.get("/api/v1/api-requests?direction=incoming",
                     headers=_h(1, 1)).json()
    assert outgoing and incoming and outgoing[0]["id"] == incoming[0]["id"]


def test_removed_and_inactive_members_are_rejected():
    _projects()
    _user(2, "viewer")
    with SessionLocal() as s:
        s.query(ProjectMember).filter_by(user_id=2).delete(
            synchronize_session=False)
        s.commit()
    c = TestClient(app)
    assert c.post("/api/v1/auth/switch-project", json={"project_id": 1},
                  headers=_h(2, 1)).status_code == 403
    aid, _ = _api()
    assert c.post("/api/v1/api-requests", json={"asset_id": aid},
                  headers=_h(2, 1)).status_code == 403
    with SessionLocal() as s:
        u = s.get(User, 2)
        u.active = False
        s.commit()
    assert c.post("/api/v1/api-requests", json={"asset_id": aid},
                  headers=_h(2, 1)).status_code == 401
    _user(2, "viewer")
