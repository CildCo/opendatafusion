import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from odf.services.auth import create_token, require_user


def test_require_user_rejects_missing():
    with pytest.raises(HTTPException) as e:
        require_user(None)
    assert e.value.status_code == 401


def test_require_user_accepts_token():
    from odf.db import SessionLocal
    from odf.models import User
    with SessionLocal() as s:
        if not s.get(User, 1):
            s.add(User(id=1, username="authdeps", password_hash="x",
                       role="admin", active=True))
            s.commit()
        else:
            u = s.get(User, 1)
            u.active = True
            s.commit()
        token = create_token(1, 2)
        claims = require_user(HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=token), s)
    assert claims["project_id"] == 2


def test_protected_route_requires_token():
    from fastapi.testclient import TestClient
    from odf.main import app
    assert TestClient(app).get("/api/v1/datasources").status_code == 401


def test_protected_route_accepts_token():
    from fastapi.testclient import TestClient
    from odf.db import SessionLocal
    from odf.main import app
    from odf.models import User
    with SessionLocal() as s:
        u = s.get(User, 1)
        if not u:
            s.add(User(id=1, username="authdeps", password_hash="x",
                       role="admin", active=True))
        else:
            u.active = True
        s.commit()
    token = create_token(1, 2)
    r = TestClient(app).get("/api/v1/datasources",
                            headers={"Authorization": "Bearer " + token})
    assert r.status_code == 200


def test_create_datasource_writes_audit():
    from fastapi.testclient import TestClient
    from odf.db import SessionLocal
    from odf.main import app
    from odf.models import AuditLog, User
    with SessionLocal() as s:
        u = s.get(User, 1)
        if not u:
            s.add(User(id=1, username="authdeps", password_hash="x",
                       role="admin", active=True))
        else:
            u.active = True
            u.role = "admin"
        s.commit()
    token = create_token(1, 1)
    r = TestClient(app).post(
        "/api/v1/datasources",
        json={"name": "aud", "dsn": "sqlite:///./aud.db", "kind": "sqlite"},
        headers={"Authorization": "Bearer " + token})
    assert r.status_code == 200
    with SessionLocal() as s:
        assert s.query(AuditLog).filter_by(action="create_datasource").count() >= 1


def test_publish_requires_approval_token():
    from fastapi.testclient import TestClient
    from odf.db import SessionLocal
    from odf.main import app
    from odf.models import User
    with SessionLocal() as s:
        u = s.get(User, 1)
        if not u:
            s.add(User(id=1, username="authdeps", password_hash="x",
                       role="admin", active=True))
        else:
            u.active = True
            u.role = "admin"
        s.commit()
    token = create_token(1, 1)
    r = TestClient(app).post(
        "/api/v1/interfaces/1/publish",
        params={"approval_token": "bad"},
        headers={"Authorization": "Bearer " + token})
    assert r.status_code == 403
