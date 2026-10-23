from fastapi.testclient import TestClient

from odf.assets.service import create_asset
from odf.db import SessionLocal
from odf.main import app
from odf.models import ChangeRequest, User
from odf.services.approval import issue_token
from odf.services.auth import create_token

CONTENT = {"nodes": [
    {"id": "s", "type": "source",
     "config": {"datasource_id": 1, "table": "t", "pk": "id"}},
    {"id": "o", "type": "sink",
     "config": {"datasource_id": 1, "table": "t", "pk": ["id"]}}],
    "edges": [{"from": "s", "to": "o"}]}
EMPTY = {"nodes": [], "edges": []}


def _ensure_user(user_id, role):
    with SessionLocal() as s:
        u = s.get(User, user_id)
        if not u:
            u = User(id=user_id, username="u%d" % user_id,
                     password_hash="x", role=role, active=True)
            s.add(u)
        else:
            u.role = role
            u.active = True
        s.commit()


def _h(user_id=1, project_id=1):
    return {"Authorization": "Bearer " + create_token(user_id, project_id)}


def test_pipeline_api_lifecycle():
    _ensure_user(1, "admin")
    c = TestClient(app)
    h = _h()
    r = c.post("/api/v1/pipelines",
               json={"name": "p1", "content": CONTENT}, headers=h)
    assert r.status_code == 200
    pid = r.json()["id"]

    got = c.get(f"/api/v1/pipelines/{pid}", headers=h)
    assert got.status_code == 200
    assert got.json()["draft"]["nodes"]
    assert c.put(f"/api/v1/pipelines/{pid}/draft",
                 json={"content": CONTENT}, headers=h).status_code == 200
    v = c.post(f"/api/v1/pipelines/{pid}/validate",
               json={"content": EMPTY}, headers=h)
    assert v.status_code == 200 and v.json()["valid"] is False

    bad = c.post(f"/api/v1/pipelines/{pid}/publish?approval_token=bad",
                 headers=h)
    assert bad.status_code == 403
    good = c.post(
        f"/api/v1/pipelines/{pid}/publish?approval_token="
        + issue_token(pid, "publish_pipeline"), headers=h)
    assert good.status_code == 200
    with SessionLocal() as s:
        assert s.query(ChangeRequest).filter_by(
            action="publish_pipeline", target=str(pid)).count() == 1
    assert c.post(f"/api/v1/pipelines/{pid}/run", headers=h).status_code == 200


def test_publish_rejects_invalid_dag():
    _ensure_user(1, "admin")
    c = TestClient(app)
    h = _h()
    pid = c.post("/api/v1/pipelines",
                 json={"name": "bad", "content": EMPTY},
                 headers=h).json()["id"]
    r = c.post(f"/api/v1/pipelines/{pid}/publish?approval_token="
               + issue_token(pid, "publish_pipeline"), headers=h)
    assert r.status_code == 400


def test_run_requires_published_version():
    _ensure_user(1, "admin")
    c = TestClient(app)
    h = _h()
    pid = c.post("/api/v1/pipelines",
                 json={"name": "draft", "content": CONTENT},
                 headers=h).json()["id"]
    assert c.post(f"/api/v1/pipelines/{pid}/run",
                  headers=h).status_code == 400


def test_preview_returns_structured_error():
    _ensure_user(1, "admin")
    c = TestClient(app)
    h = _h()
    pid = c.post("/api/v1/pipelines",
                 json={"name": "p", "content": CONTENT},
                 headers=h).json()["id"]
    r = c.post(f"/api/v1/pipelines/{pid}/preview",
               json={"node_id": "missing"}, headers=h)
    assert r.status_code == 400
    assert isinstance(r.json()["detail"], dict)
    assert r.json()["detail"]["errors"]


def test_pipeline_requires_project_membership_and_editor():
    _ensure_user(1, "admin")
    _ensure_user(2, "viewer")
    c = TestClient(app)
    with SessionLocal() as s:
        other = create_asset(s, 2, "pipeline", "other", CONTENT, "admin")
        other_id = other.id
    assert c.get(f"/api/v1/pipelines/{other_id}",
                 headers=_h(1, 1)).status_code == 404

    pid = c.post("/api/v1/pipelines",
                 json={"name": "p", "content": CONTENT},
                 headers=_h(1, 1)).json()["id"]
    assert c.put(f"/api/v1/pipelines/{pid}/draft",
                 json={"content": CONTENT},
                 headers=_h(2, 1)).status_code == 403


def test_update_cron_and_name():
    _ensure_user(1, "admin")
    c = TestClient(app)
    h = _h()
    pid = c.post("/api/v1/pipelines",
                 json={"name": "p", "content": CONTENT},
                 headers=h).json()["id"]
    r = c.put(f"/api/v1/pipelines/{pid}",
              json={"name": "renamed", "cron": "0 */5 * * * ?"}, headers=h)
    assert r.status_code == 200
    got = c.get(f"/api/v1/pipelines/{pid}", headers=h).json()
    assert got["name"] == "renamed"
    assert got["cron"] == "0 */5 * * * ?"
    assert c.put(f"/api/v1/pipelines/{pid}", json={"cron": "bad"},
                 headers=h).status_code == 400
