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
            u = User(id=uid, username="dash_u%d" % uid,
                     password_hash="x", role=role, active=True)
            s.add(u)
        else:
            u.role = role
        s.commit()


def _h(uid=1, project=1):
    return {"Authorization": "Bearer " + create_token(uid, project)}


def test_dashboard_routes_and_publish():
    _user(1, "admin")
    c = TestClient(app)
    h = _h()
    r = c.post("/api/v1/dashboards",
               json={"name": "D", "content": {"widgets": []}}, headers=h)
    assert r.status_code == 200
    did = r.json()["id"]
    assert c.get(f"/api/v1/dashboards/{did}", headers=h).status_code == 200
    assert c.post(f"/api/v1/dashboards/{did}/data",
                  json={"content": {"widgets": []}},
                  headers=h).status_code == 200
    r = c.post(f"/api/v1/dashboards/{did}/publish?approval_token="
               + issue_token(did, "publish_dashboard"), headers=h)
    assert r.status_code == 200
    assert c.get(f"/api/v1/dashboards/{did}",
                 headers=h).json()["published_version"] == 1


def test_widget_error_is_isolated_over_http():
    _user(1, "admin")
    c = TestClient(app)
    h = _h()
    content = {"widgets": [
        {"id": "bad", "type": "line", "metric_id": 999,
         "x": 0, "y": 0, "w": 3, "h": 2},
        {"id": "ok", "type": "text", "text": "ok",
         "x": 3, "y": 0, "w": 3, "h": 2}]}
    did = c.post("/api/v1/dashboards",
                 json={"name": "iso", "content": content},
                 headers=h).json()["id"]
    r = c.post(f"/api/v1/dashboards/{did}/data",
               json={"content": content}, headers=h)
    assert r.status_code == 200
    assert r.json()["widgets"]["bad"]["error"]
    assert r.json()["widgets"]["ok"]["text"] == "ok"


def test_dashboard_data_accepts_params():
    _user(1, "admin")
    c = TestClient(app)
    h = _h()
    content = {"params": [{"name": "city", "type": "string",
                           "default": "a"}],
               "widgets": [{"id": "t", "type": "text", "text": "x",
                            "x": 0, "y": 0, "w": 3, "h": 2}]}
    did = c.post("/api/v1/dashboards",
                 json={"name": "P", "content": content},
                 headers=h).json()["id"]
    r = c.post(f"/api/v1/dashboards/{did}/data",
               json={"content": content, "params": {"city": "b"}},
               headers=h)
    assert r.status_code == 200
    assert r.json()["params"]["city"] == "b"


def test_published_data_flag_uses_published_content():
    _user(1, "admin")
    c = TestClient(app)
    h = _h()
    a = {"widgets": [{"id": "t", "type": "text", "text": "A",
                      "x": 0, "y": 0, "w": 3, "h": 2}]}
    d = {"widgets": [{"id": "t", "type": "text", "text": "DRAFT",
                      "x": 0, "y": 0, "w": 3, "h": 2}]}
    did = c.post("/api/v1/dashboards",
                 json={"name": "P", "content": a}, headers=h).json()["id"]
    c.post(f"/api/v1/dashboards/{did}/publish?approval_token="
           + issue_token(did, "publish_dashboard"), headers=h)
    c.put(f"/api/v1/dashboards/{did}/draft", json={"content": d}, headers=h)
    pub = c.post(f"/api/v1/dashboards/{did}/data",
                 json={"published": True}, headers=h).json()
    assert pub["widgets"]["t"]["text"] == "A"
    draft = c.post(f"/api/v1/dashboards/{did}/data", json={}, headers=h).json()
    assert draft["widgets"]["t"]["text"] == "DRAFT"
