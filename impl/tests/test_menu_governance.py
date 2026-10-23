from fastapi.testclient import TestClient

from odf.db import SessionLocal
from odf.main import app
from odf.models import PortalSetting, Project, ProjectMember, User
from odf.services.auth import create_token


def _setup(allowed):
    with SessionLocal() as s:
        if not s.get(Project, 1):
            s.add(Project(id=1, code="menu1", name="menu1", status=1))
        for uid, role in ((1, "admin"), (2, "viewer")):
            u = s.get(User, uid)
            if not u:
                u = User(id=uid, username="menu%d" % uid,
                         password_hash="x", role=role, active=True)
                s.add(u)
            else:
                u.role = role
                u.active = True
        s.flush()
        if not s.query(ProjectMember).filter_by(project_id=1,
                                                user_id=2).first():
            s.add(ProjectMember(project_id=1, user_id=2, role="viewer"))
        row = s.query(PortalSetting).filter_by(project_id=1).first()
        if not row:
            row = PortalSetting(project_id=1, brand_name="OpenDataFusion",
                                primary_color="#1d4ed8", welcome_title="",
                                welcome_text="", hidden_menus=[],
                                updated_by="")
            s.add(row)
        row.allowed_menus = allowed
        row.hidden_menus = []
        s.commit()


def _h(uid, project=1):
    return {"Authorization": "Bearer " + create_token(uid, project)}


def test_menu_permissions_enforced():
    try:
        _setup(["/datasets"])
        c = TestClient(app)
        assert c.get("/api/v1/apps", headers=_h(2)).status_code == 403
        assert c.get("/api/v1/datasets", headers=_h(2)).status_code == 200
        assert c.get("/api/v1/ops/summary", headers=_h(2)).status_code == 403
        assert c.get("/api/v1/apps", headers=_h(1)).status_code == 200
    finally:
        _setup(None)


def test_unrestricted_menus_allow_all():
    _setup(None)
    c = TestClient(app)
    assert c.get("/api/v1/apps", headers=_h(2)).status_code == 200


def test_hidden_menus_are_enforced_without_allowlist():
    try:
        _setup(None)
        with SessionLocal() as s:
            row = s.query(PortalSetting).filter_by(project_id=1).first()
            row.hidden_menus = ["/apps"]
            s.commit()
        c = TestClient(app)
        assert c.get("/api/v1/apps", headers=_h(2)).status_code == 403
        assert c.get("/api/v1/datasets", headers=_h(2)).status_code == 200
    finally:
        _setup(None)
