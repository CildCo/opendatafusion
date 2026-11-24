import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from odf.db import SessionLocal
from odf.main import app
from odf.models import Alert, Asset, AuditLog, Job, Project, User
from odf.services.auth import create_token


def _user(uid, role):
    with SessionLocal() as s:
        u = s.get(User, uid)
        if not u:
            u = User(id=uid, username="ops_u%d" % uid, password_hash="x",
                     role=role, active=True)
            s.add(u)
        else:
            u.role = role
        s.commit()


def _h(uid=1, project=903):
    return {"Authorization": "Bearer " + create_token(uid, project)}


def _fixture():
    with SessionLocal() as s:
        for pid, code in ((903, "ops903"), (904, "ops904")):
            if not s.get(Project, pid):
                s.add(Project(id=pid, code=code, name=code))
        s.flush()
        s.query(Job).filter(Job.id.in_([9311, 9312])).delete(
            synchronize_session=False)
        s.query(Alert).filter(Alert.id.in_([9411, 9412])).delete(
            synchronize_session=False)
        s.query(Asset).filter(Asset.id.in_([9211, 9212])).delete(
            synchronize_session=False)
        s.add_all([
            Asset(id=9211, project_id=903, type="pipeline",
                  key="ops-asset", name="ops-asset", owner="ops"),
            Asset(id=9212, project_id=904, type="pipeline",
                  key="ops-asset-2", name="other-asset", owner="ops"),
            Job(id=9311, asset_id=9211, asset_type="pipeline",
                status="failed", attempts=3, last_error="boom",
                finished_at=datetime.now(timezone.utc)),
            Job(id=9312, asset_id=9212, asset_type="pipeline",
                status="failed", attempts=3, last_error="other"),
            Alert(id=9411, project_id=903, severity="warning",
                  title="ops", status="open"),
            Alert(id=9412, project_id=904, severity="critical",
                  title="other", status="open"),
        ])
        s.commit()


def test_ops_routes_are_project_scoped():
    _user(1, "admin")
    _fixture()
    c = TestClient(app)
    h = _h()
    assert c.get("/api/v1/ops/summary", headers=h).status_code == 200
    jobs = c.get("/api/v1/ops/jobs", headers=h).json()
    assert [j["id"] for j in jobs] == [9311]
    alerts = c.get("/api/v1/ops/alerts", headers=h).json()
    assert [a["id"] for a in alerts] == [9411]
    assert c.post("/api/v1/ops/jobs/9312/retry",
                  headers=h).status_code == 404
    assert c.post("/api/v1/ops/alerts/9412/ack",
                  headers=h).status_code == 404


def test_retry_and_alert_actions():
    _user(1, "editor")
    _fixture()
    c = TestClient(app)
    h = _h()
    r = c.post("/api/v1/ops/jobs/9311/retry", headers=h)
    assert r.status_code == 200 and r.json()["status"] == "queued"
    assert c.post("/api/v1/ops/jobs/9311/retry",
                  headers=h).status_code == 400
    assert c.post("/api/v1/ops/alerts/9411/ack",
                  headers=h).status_code == 200
    assert c.post("/api/v1/ops/alerts/9411/close",
                  headers=h).status_code == 200


def test_audit_requires_admin_and_alerts_ignore_spoofed_project():
    _user(1, "editor")
    _fixture()
    c = TestClient(app)
    h = _h()
    assert c.get("/api/v1/ops/audit", headers=h).status_code == 403
    assert c.get("/api/v1/audit", headers=h).status_code == 403
    _user(1, "admin")
    assert c.get("/api/v1/ops/audit", headers=_h()).status_code == 200
    alerts = c.get("/api/v1/alerts?project_id=904",
                   headers=_h()).json()["items"]
    assert [a["id"] for a in alerts] == [9411]
    assert c.post("/api/v1/alerts/9412/ack",
                  headers=_h()).status_code == 404


def test_viewer_cannot_mutate_alerts():
    _user(1, "viewer")
    _fixture()
    c = TestClient(app)
    h = _h()
    assert c.post("/api/v1/alerts/9411/ack", headers=h).status_code == 403
    assert c.post("/api/v1/alerts/9411/close", headers=h).status_code == 403
    assert c.post("/api/v1/alerts/rules",
                  json={"name": "x", "kind": "lag"},
                  headers=h).status_code == 403


def test_ops_audit_shows_usernames():
    _user(1, "admin")
    action = "ui_probe_%s" % uuid.uuid4().hex[:8]
    with SessionLocal() as s:
        s.add(AuditLog(actor="1", action=action, target="9501",
                       at=datetime(2026, 1, 1, tzinfo=timezone.utc)))
        s.add(AuditLog(actor="ops_u1", action=action, target="9502",
                       at=datetime(2026, 1, 2, tzinfo=timezone.utc)))
        s.commit()
    try:
        rows = TestClient(app).get(f"/api/v1/ops/audit?action={action}",
                                   headers=_h()).json()
        with SessionLocal() as s:
            username = s.get(User, 1).username
        assert [r["actor"] for r in rows] == ["ops_u1", username]
        assert username != "1"
    finally:
        with SessionLocal() as s:
            s.query(AuditLog).filter_by(action=action).delete()
            s.commit()

