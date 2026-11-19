import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from odf.db import SessionLocal
from odf.main import app
from odf.models import AuditLog, Flow, FlowRun, FlowVersion, Job, Project, User
from odf.services.auth import create_token

PROJECT_ID = 915


@pytest.fixture()
def flow(tmp_path):
    with SessionLocal() as s:
        if not s.get(Project, PROJECT_ID):
            s.add(Project(id=PROJECT_ID, code="flow-depth",
                          name="Flow depth", status=1))
            s.commit()
        f = Flow(project_id=PROJECT_ID, name="flow-%s" % uuid.uuid4().hex[:8],
                 cron="", status=1)
        s.add(f)
        s.commit()
        v1 = FlowVersion(flow_id=f.id, version=1, created_by="tester",
                         dag_json={"pk": "id"})
        v2 = FlowVersion(flow_id=f.id, version=2, created_by="tester",
                         dag_json={"pk": "id", "batch": 500})
        s.add_all([v1, v2])
        started = datetime.now(timezone.utc)
        r = FlowRun(flow_id=f.id, status=2, started_at=started,
                    finished_at=started + timedelta(milliseconds=1500),
                    in_num=10, out_num=9, err_num=1, cursor_value="42")
        s.add(r)
        s.commit()
        ids = (f.id, r.id)
    yield ids
    with SessionLocal() as s:
        s.query(AuditLog).filter(AuditLog.target == str(ids[0])).delete()
        s.query(Job).filter_by(flow_id=ids[0]).delete()
        s.query(FlowRun).filter_by(flow_id=ids[0]).delete()
        s.query(FlowVersion).filter_by(flow_id=ids[0]).delete()
        s.query(Flow).filter_by(id=ids[0]).delete()
        s.commit()


def _headers(user_id=915, project_id=PROJECT_ID):
    with SessionLocal() as s:
        if not s.get(User, user_id):
            s.add(User(id=user_id, username="flow-depth", password_hash="x",
                       role="admin", active=True))
            s.commit()
    return {"Authorization": "Bearer " + create_token(user_id, project_id)}


def test_run_list_includes_timing(flow):
    flow_id, run_id = flow
    client = TestClient(app)
    rows = client.get(f"/api/v1/flows/{flow_id}/runs",
                      headers=_headers()).json()
    run = next(r for r in rows if r["id"] == run_id)
    assert run["started_at"]
    assert run["finished_at"]
    assert run["duration_ms"] == 1500


def test_retry_enqueues_a_job_and_records_it(flow):
    flow_id, run_id = flow
    client = TestClient(app)
    r = client.post(f"/api/v1/flows/{flow_id}/runs/{run_id}/retry",
                    headers=_headers())
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    with SessionLocal() as s:
        job = s.get(Job, job_id)
        assert job and job.flow_id == flow_id and job.status == "queued"
        audit = (s.query(AuditLog)
                 .filter_by(action="retry_flow", target=str(flow_id)).first())
        assert audit
        assert audit.detail_json["run_id"] == run_id


def test_version_detail_returns_the_dag(flow):
    flow_id, _ = flow
    client = TestClient(app)
    r = client.get(f"/api/v1/flows/{flow_id}/versions/1", headers=_headers())
    assert r.status_code == 200
    assert r.json()["dag"] == {"pk": "id"}
    assert client.get(f"/api/v1/flows/{flow_id}/versions/99",
                      headers=_headers()).status_code == 404


def test_new_flow_routes_are_project_scoped(flow):
    flow_id, run_id = flow
    client = TestClient(app)
    other = _headers(project_id=9999)
    assert client.post(f"/api/v1/flows/{flow_id}/runs/{run_id}/retry",
                       headers=other).status_code == 404
    assert client.get(f"/api/v1/flows/{flow_id}/versions/1",
                      headers=other).status_code == 404
