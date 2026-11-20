import pytest
from fastapi.testclient import TestClient

from odf.db import SessionLocal
from odf.main import app
from odf.models import User
from odf.services.auth import create_token

ADMIN_A = 9201
ADMIN_B = 9202
VIEWER = 9203


@pytest.fixture()
def users():
    with SessionLocal() as s:
        for uid, name, role in ((ADMIN_A, "guard_a", "admin"),
                                (ADMIN_B, "guard_b", "admin"),
                                (VIEWER, "guard_v", "viewer")):
            u = s.get(User, uid)
            if not u:
                u = User(id=uid, username=name, password_hash="x",
                         role=role, active=True)
                s.add(u)
            else:
                u.role, u.active = role, True
        s.commit()
    yield
    with SessionLocal() as s:
        s.query(User).filter(User.id.in_([ADMIN_A, ADMIN_B, VIEWER])).update(
            {User.active: True}, synchronize_session=False)
        s.commit()


def _h(uid=ADMIN_A):
    return {"Authorization": "Bearer " + create_token(uid, 1)}


def test_admin_cannot_deactivate_themselves(users):
    c = TestClient(app)
    r = c.put(f"/api/v1/users/{ADMIN_A}/active?active=false",
              headers=_h(ADMIN_A))
    assert r.status_code == 400
    assert "your own" in r.json()["detail"]
    with SessionLocal() as s:
        assert s.get(User, ADMIN_A).active is True


def test_admin_cannot_change_their_own_role(users):
    c = TestClient(app)
    r = c.put(f"/api/v1/users/{ADMIN_A}/role?role=viewer",
              headers=_h(ADMIN_A))
    assert r.status_code == 400
    assert "your own" in r.json()["detail"]
    with SessionLocal() as s:
        assert s.get(User, ADMIN_A).role == "admin"


def test_admin_can_deactivate_another_user(users):
    c = TestClient(app)
    r = c.put(f"/api/v1/users/{VIEWER}/active?active=false",
              headers=_h(ADMIN_A))
    assert r.status_code == 200
    assert r.json()["active"] is False


def test_unknown_user_still_returns_404(users):
    c = TestClient(app)
    assert c.put("/api/v1/users/999999/active?active=false",
                 headers=_h(ADMIN_A)).status_code == 404
