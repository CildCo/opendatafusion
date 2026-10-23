from datetime import datetime, timezone

from fastapi.testclient import TestClient

from odf.db import SessionLocal
from odf.main import app
from odf.models import Alert, Asset, Flow, Job, Project, User
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
        s.query(Flow).filter(Flow.id.in_([9111, 9112])).delete(
            synchronize_session=False)
        s.query(Asset).filter(Asset.id.in_([9211])).delete(
            synchronize_session=False)
        s.add_all([
            Flow(id=9111, project_id=903, name="ops-flow"),
            Flow(id=9112, project_id=904, name="other-flow"),
            Asset(id=9211, project_id=903, type="pipeline",
                  key="ops-asset", name="ops-asset", owner="ops"),
            Job(id=9311, flow_id=9111, status="failed", attempts=3,
                last_error="boom", finished_at=datetime.now(timezone.utc)),
            Job(id=9312, flow_id=9112, status="failed", attempts=3,
                last_error="other"),
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
    health = c.get("/api/v1/ops/health", headers=h).json()
    assert [f["flow_id"] for f in health["flows"]] == [9111]


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
    alerts = c.get("/api/v1/alerts?project_id=904", headers=_h()).json()
    assert [a["id"] for a in alerts] == [9411]
    assert c.post("/api/v1/alerts/9412/ack",
                  headers=_h()).status_code == 404
    health = c.get("/api/v1/health/snapshot", headers=_h()).json()
    assert [f["flow_id"] for f in health] == [9111]


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
