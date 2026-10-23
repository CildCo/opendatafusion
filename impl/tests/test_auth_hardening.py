import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.db import Base, SessionLocal
from odf.main import app
from odf.models import Project, ProjectMember, User
from odf.services.auth import (create_token, effective_role)
from odf.services.passwords import validate_password
from odf.services.totp import (code_for, generate_secret, verify_code)
from odf.services.users import create_user, hash_password


def _env():
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add_all([Project(id=1, code="h1", name="h1", status=1),
               Project(id=2, code="h2", name="h2", status=1)])
    s.commit()
    return s


def test_password_policy():
    with pytest.raises(ValueError):
        validate_password("short")
    with pytest.raises(ValueError):
        validate_password("alllowercase123!")
    validate_password("GoodPassw0rd!")


def test_totp_vector_and_window():
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
    assert code_for(secret, 59) == "287082"
    assert verify_code(secret, "287082", 59)
    assert not verify_code(secret, "000000", 59)


def test_project_role_override():
    s = _env()
    u = create_user(s, "role_u", "x", role="viewer")
    assert effective_role(s, u, 1) == "viewer"
    s.add(ProjectMember(project_id=1, user_id=u.id, role="editor"))
    s.commit()
    assert effective_role(s, u, 1) == "editor"
    assert effective_role(s, u, 2) == "viewer"


def _user(uid, role, active=True):
    with SessionLocal() as s:
        u = s.get(User, uid)
        if not u:
            u = User(id=uid, username="hard%d" % uid,
                     password_hash=hash_password("GoodPassw0rd!"),
                     role=role, active=active)
            s.add(u)
        else:
            u.username = "hard%d" % uid
            u.password_hash = hash_password("GoodPassw0rd!")
            u.role = role
            u.active = active
            u.totp_enabled = False
            u.totp_secret_encrypted = None
        s.commit()


def test_change_password_and_refresh():
    _user(1, "viewer")
    h = {"Authorization": "Bearer " + create_token(1, 1)}
    c = TestClient(app)
    weak = c.post("/api/v1/auth/change-password",
                  json={"old_password": "GoodPassw0rd!",
                        "new_password": "weak"}, headers=h)
    assert weak.status_code == 400
    ok = c.post("/api/v1/auth/change-password",
                json={"old_password": "GoodPassw0rd!",
                      "new_password": "NewPassw0rd!"}, headers=h)
    assert ok.status_code == 200
    assert c.post("/api/v1/auth/refresh", headers=h).status_code == 401
    new_h = {"Authorization": "Bearer " + ok.json()["token"]}
    r = c.post("/api/v1/auth/refresh", headers=new_h)
    assert r.status_code == 200 and r.json()["token"]


def test_totp_setup_enable_and_login():
    _user(2, "viewer")
    with SessionLocal() as s:
        if not s.query(ProjectMember).filter_by(project_id=1,
                                                user_id=2).first():
            s.add(ProjectMember(project_id=1, user_id=2, role="viewer"))
            s.commit()
    h = {"Authorization": "Bearer " + create_token(2, 1)}
    c = TestClient(app)
    setup = c.post("/api/v1/auth/totp/setup", headers=h)
    assert setup.status_code == 200
    secret = setup.json()["secret"]
    assert "otpauth://" in setup.json()["uri"]
    assert c.post("/api/v1/auth/totp/enable",
                  json={"code": "000000"}, headers=h).status_code == 400
    code = code_for(secret)
    assert c.post("/api/v1/auth/totp/enable", json={"code": code},
                  headers=h).status_code == 200
    no_otp = c.post("/api/v1/auth/login",
                    json={"username": "hard2",
                          "password": "GoodPassw0rd!", "project_id": 1})
    assert no_otp.status_code == 401
    with SessionLocal() as s:
        u = s.get(User, 2)
        assert u.totp_enabled is True
        assert secret not in (u.totp_secret_encrypted or "")
    ok = c.post("/api/v1/auth/login",
                json={"username": "hard2", "password": "GoodPassw0rd!",
                      "project_id": 1,
                      "otp": code_for(secret, time.time() + 30)})
    assert ok.status_code == 200
