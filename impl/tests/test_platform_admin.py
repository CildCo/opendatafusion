import pytest
from fastapi.testclient import TestClient

from odf.db import SessionLocal
from odf.main import app
from odf.models import PlatformSetting, Project, ProjectMember, User
from odf.services.auth import create_token
from odf.services.platform import (apply_runtime, get_doc, public_doc,
                                   update_doc)
from odf.services.users import hash_password

PROJECT = 930
OTHER = 931
PLATFORM = 9301
PROJECT_ADMIN = 9302
VIEWER = 9303


@pytest.fixture()
def fixture():
    with SessionLocal() as s:
        for pid, code in ((PROJECT, "admin930"), (OTHER, "admin931")):
            if not s.get(Project, pid):
                s.add(Project(id=pid, code=code, name=code, status=1))
        for uid, name, role, admin in (
                (PLATFORM, "padmin", "admin", True),
                (PROJECT_ADMIN, "padmin_proj", "viewer", False),
                (VIEWER, "padmin_viewer", "viewer", False)):
            user = s.get(User, uid)
            if not user:
                user = User(id=uid, username=name, password_hash="x",
                            role=role, active=True, platform_admin=admin)
                s.add(user)
            else:
                user.role, user.active = role, True
                user.platform_admin = admin
        s.commit()
        for uid, role in ((PROJECT_ADMIN, "admin"), (VIEWER, "viewer")):
            row = (s.query(ProjectMember)
                   .filter_by(project_id=PROJECT, user_id=uid).first())
            if not row:
                s.add(ProjectMember(project_id=PROJECT, user_id=uid,
                                    role=role))
            else:
                row.role = role
        s.commit()
        original = (s.get(PlatformSetting, 1).settings_json
                    if s.get(PlatformSetting, 1) else None)
    yield
    with SessionLocal() as s:
        row = s.get(PlatformSetting, 1)
        if row:
            row.settings_json = original or {}
            s.commit()
    with SessionLocal() as s:
        apply_runtime(s)


def headers(uid, project=PROJECT):
    return {"Authorization": "Bearer " + create_token(uid, project)}


def test_settings_are_masked_and_public_doc_hides_secrets(fixture):
    with SessionLocal() as s:
        doc = update_doc(s, {"identity": {"oidc": {
            "enabled": True, "issuer": "https://idp.example",
            "client_id": "console",
            "client_secret": "top-secret",
            "redirect_uri": "https://odf.example/auth/callback"}}}, "tester")
        assert doc["identity"]["oidc"]["client_secret"] == "********"
        public = public_doc(s)
        assert "identity" not in public
        assert "top-secret" not in str(public)
        internal = get_doc(s, mask=False)
        assert internal["identity"]["oidc"]["client_secret"] == "top-secret"
        from odf.settings import get_settings
        assert get_settings().oidc_issuer == "https://idp.example"
        update_doc(s, {"identity": {"oidc": {"enabled": False}}}, "tester")
        assert get_settings().oidc_issuer == ""


def test_platform_settings_routes_are_platform_admin_only(fixture):
    c = TestClient(app)
    assert c.get("/api/v1/platform/settings",
                 headers=headers(VIEWER)).status_code == 403
    assert c.get("/api/v1/platform/settings",
                 headers=headers(PLATFORM)).status_code == 200
    assert c.get("/api/v1/platform/overview",
                 headers=headers(PLATFORM)).status_code == 200
    blocked = c.post("/api/v1/platform/identity/test-oidc",
                     json={"issuer": "http://127.0.0.1:1"},
                     headers=headers(PLATFORM))
    assert blocked.status_code == 400
    public = c.get("/api/v1/platform/public")
    assert public.status_code == 200
    assert "brand" in public.json()


def test_auth_me_reports_the_effective_project_role(fixture):
    c = TestClient(app)
    me = c.get("/api/v1/auth/me", headers=headers(PROJECT_ADMIN)).json()
    assert me["role"] == "admin"
    assert me["platform_admin"] is False


def test_project_admin_member_directory_is_scoped(fixture):
    from odf.models import ProjectMember
    with SessionLocal() as s:
        if not s.get(User, 9304):
            s.add(User(id=9304, username="padmin_new", password_hash="x",
                       role="viewer", active=True))
            s.commit()
    c = TestClient(app)
    members = c.get("/api/v1/projects/%d/members" % PROJECT,
                    headers=headers(PROJECT_ADMIN)).json()
    assert members and members[0]["username"]
    found = c.get("/api/v1/projects/%d/users/lookup?username=padmin_new"
                  % PROJECT, headers=headers(PROJECT_ADMIN))
    assert found.status_code == 200
    assert found.json()["member"] is False
    other = c.get("/api/v1/projects/%d/users/lookup?username=padmin_new"
                  % OTHER, headers=headers(PROJECT_ADMIN))
    assert other.status_code == 404
    added = c.post("/api/v1/projects/%d/members" % PROJECT,
                   json={"user_id": 9304, "role": "viewer"},
                   headers=headers(PROJECT_ADMIN))
    assert added.status_code == 200
    again = c.get("/api/v1/projects/%d/users/lookup?username=padmin_new"
                  % PROJECT, headers=headers(PROJECT_ADMIN))
    assert again.json()["member"] is True
    with SessionLocal() as s:
        s.query(ProjectMember).filter_by(project_id=PROJECT,
                                         user_id=9304).delete()
        s.commit()


def test_project_admin_scopes_members_to_their_project(fixture):
    c = TestClient(app)
    own = c.get("/api/v1/projects/%d/members" % PROJECT,
                headers=headers(PROJECT_ADMIN)).status_code
    other = c.get("/api/v1/projects/%d/members" % OTHER,
                  headers=headers(PROJECT_ADMIN)).status_code
    assert own == 200
    assert other == 404


def test_project_quota_update_requires_platform_admin(fixture):
    c = TestClient(app)
    body = {"quota": {"cpu": "8", "memory": "16Gi"}}
    assert c.put("/api/v1/projects/%d" % PROJECT, json=body,
                 headers=headers(PROJECT_ADMIN)).status_code == 403
    ok = c.put("/api/v1/projects/%d" % PROJECT, json=body,
               headers=headers(PLATFORM))
    assert ok.status_code == 200
    assert ok.json()["quota"]["cpu"] == "8"


def test_platform_role_cannot_change_itself(fixture):
    c = TestClient(app)
    r = c.put("/api/v1/users/%d/platform-admin?platform_admin=false" % PLATFORM,
              headers=headers(PLATFORM))
    assert r.status_code == 400
    assert "your own" in r.json()["detail"]


def test_login_requires_mfa_for_selected_roles(fixture):
    with SessionLocal() as s:
        update_doc(s, {"login": {"mfa_required_roles": ["viewer"]}}, "tester")
        viewer = s.get(User, VIEWER)
        viewer.password_hash = hash_password("ViewerPassw0rd!")
        s.commit()
    c = TestClient(app)
    r = c.post("/api/v1/auth/login", json={
        "username": "padmin_viewer", "password": "ViewerPassw0rd!",
        "project_id": PROJECT})
    assert r.status_code == 403
    assert "Two-factor" in r.json()["detail"]
    with SessionLocal() as s:
        update_doc(s, {"login": {"mfa_required_roles": []}}, "tester")
