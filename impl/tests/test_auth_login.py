from fastapi.testclient import TestClient

from odf.db import SessionLocal
from odf.main import app
from odf.models import Project, ProjectMember, User
from odf.services.users import create_user


def _project(pid):
    with SessionLocal() as s:
        if not s.get(Project, pid):
            s.add(Project(id=pid, code="login%d" % pid, name="login"))
            s.commit()


def test_login_requires_project_membership_for_viewers():
    _project(907)
    _project(908)
    with SessionLocal() as s:
        u = s.query(User).filter_by(username="login_viewer").first()
        if not u:
            u = create_user(s, "login_viewer", "pw123456", role="viewer")
        if not s.query(ProjectMember).filter_by(project_id=907,
                                                user_id=u.id).first():
            s.add(ProjectMember(project_id=907, user_id=u.id, role="viewer"))
            s.commit()
        uid = u.id
    c = TestClient(app)
    ok = c.post("/api/v1/auth/login",
                json={"username": "login_viewer", "password": "pw123456",
                      "project_id": 907})
    assert ok.status_code == 200
    bad = c.post("/api/v1/auth/login",
                 json={"username": "login_viewer", "password": "pw123456",
                       "project_id": 908})
    assert bad.status_code == 403
    assert uid
