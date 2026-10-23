from fastapi.testclient import TestClient

from odf.db import SessionLocal
from odf.main import app
from odf.models import User
from odf.services.users import hash_password


def _user():
    with SessionLocal() as s:
        u = s.get(User, 960)
        if not u:
            u = User(id=960, username="revoke960", role="admin", active=True)
            s.add(u)
        u.password_hash = hash_password("OldPassw0rd!")
        u.active = True
        u.token_version = 0
        s.commit()


def test_password_change_revokes_existing_sessions():
    _user()
    c = TestClient(app)
    login = c.post("/api/v1/auth/login",
                   json={"username": "revoke960",
                         "password": "OldPassw0rd!", "project_id": 1})
    assert login.status_code == 200
    old = login.json()["token"]
    h = {"Authorization": "Bearer " + old}
    assert c.get("/api/v1/auth/me", headers=h).status_code == 200
    r = c.post("/api/v1/auth/change-password",
               json={"old_password": "OldPassw0rd!",
                     "new_password": "NewPassw0rd!"}, headers=h)
    assert r.status_code == 200 and r.json()["token"]
    new = r.json()["token"]
    assert c.get("/api/v1/auth/me", headers=h).status_code == 401
    assert c.get("/api/v1/auth/me",
                 headers={"Authorization": "Bearer " + new}).status_code == 200


def test_admin_reset_revokes_sessions():
    _user()
    c = TestClient(app)
    token = c.post("/api/v1/auth/login",
                   json={"username": "revoke960",
                         "password": "OldPassw0rd!", "project_id": 1}
                   ).json()["token"]
    h = {"Authorization": "Bearer " + token}
    r = c.post("/api/v1/users/960/reset-password",
               json={"password": "ResetPassw0rd!"}, headers=h)
    assert r.status_code == 200
    assert c.get("/api/v1/auth/me", headers=h).status_code == 401
    login = c.post("/api/v1/auth/login",
                   json={"username": "revoke960",
                         "password": "ResetPassw0rd!", "project_id": 1})
    assert login.status_code == 200
