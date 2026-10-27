import json
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

from odf.db import SessionLocal
from odf.engine.flink_sql import FlinkSqlGateway
from odf.main import app
from odf.models import User
from odf.services.auth import create_token
from odf.services.engine_jobs import submit_job


def _client(handler):
    return httpx.Client(base_url="http://gateway",
                        transport=httpx.MockTransport(handler))


def test_savepoint_triggers_then_returns_location():
    calls = []

    def handler(request):
        calls.append((request.method, str(request.url)))
        if request.method == "POST":
            return httpx.Response(202, json={"request-id": "t1"})
        return httpx.Response(200, json={
            "status": {"id": "COMPLETED"},
            "operation": {"location": "s3://bucket/sp/savepoint-abc"}})

    gateway = FlinkSqlGateway("http://gateway", rest_url="http://flink:8081",
                              client=_client(handler))
    out = gateway.savepoint("j1", "s3://bucket/sp")

    assert calls[0] == ("POST", "http://flink:8081/jobs/j1/savepoints")
    assert out == {"trigger_id": "t1", "status": "COMPLETED",
                   "location": "s3://bucket/sp/savepoint-abc"}


def test_savepoint_polls_until_complete():
    seen = {"n": 0}

    def handler(request):
        if request.method == "POST":
            return httpx.Response(202, json={"request-id": "t2"})
        seen["n"] += 1
        state = "IN_PROGRESS" if seen["n"] == 1 else "COMPLETED"
        return httpx.Response(200, json={"status": {"id": state},
                                         "operation": {"location": "s3://x"}})

    gateway = FlinkSqlGateway("http://gateway", rest_url="http://flink:8081",
                              client=_client(handler))
    out = gateway.savepoint("j2", "")
    assert out["status"] == "COMPLETED"
    assert seen["n"] == 2


def test_savepoint_sends_cancel_flag():
    captured = {}

    def handler(request):
        if request.method == "POST":
            captured.update(json.loads(request.content))
            return httpx.Response(202, json={"request-id": "t3"})
        return httpx.Response(200, json={"status": {"id": "COMPLETED"},
                                         "operation": {"location": "s3://x"}})

    gateway = FlinkSqlGateway("http://gateway", rest_url="http://flink:8081",
                              client=_client(handler))
    gateway.savepoint("j3", "s3://sp", stop=True)
    assert captured == {"cancel-job": True, "target-directory": "s3://sp"}


def test_savepoint_requires_rest_url():
    gateway = FlinkSqlGateway("http://gateway", client=_client(
        lambda r: httpx.Response(200, json={})))
    with pytest.raises(ValueError, match="rest url"):
        gateway.savepoint("j4", "")


class FakeFlink:
    def __init__(self):
        self.saved = []

    def execute(self, statement, properties=None, attached=True):
        return {"job_id": "b" * 32}

    def job_status(self, job_id):
        from odf.engine import JobStatus
        return JobStatus.RUNNING

    def cancel(self, job_id):
        pass

    def savepoint(self, job_id, target_dir="", stop=False):
        self.saved.append((job_id, target_dir, stop))
        return {"trigger_id": "t1", "status": "COMPLETED",
                "location": "s3://bucket/sp/savepoint-1"}


@pytest.fixture()
def session():
    with SessionLocal() as s:
        yield s


def _headers(uid=961):
    with SessionLocal() as s:
        user = s.get(User, uid)
        if not user:
            user = User(id=uid, username="sp_%d" % uid, password_hash="x",
                        role="editor", active=True)
            s.add(user)
        else:
            user.role = "editor"
            user.active = True
        s.commit()
    return {"Authorization": "Bearer " + create_token(uid, 1)}


def _flink_job(session, monkeypatch):
    fake = FakeFlink()
    monkeypatch.setattr("odf.services.engine_jobs._flink_gateway", lambda: fake)
    job = submit_job(session, 1, "flink", "sp-%s" % uuid.uuid4().hex[:8],
                     {"statement": "INSERT INTO t SELECT * FROM s",
                      "attached": False}, "tester")
    return fake, job


def test_savepoint_api_records_location(session, monkeypatch):
    fake, job = _flink_job(session, monkeypatch)
    client = TestClient(app)

    response = client.post(
        "/api/v1/engine/jobs/%d/savepoint" % job.id, headers=_headers(),
        json={"target_directory": "s3://bucket/sp"})

    assert response.status_code == 200
    body = response.json()
    assert body["location"] == "s3://bucket/sp/savepoint-1"
    assert body["status"] == "COMPLETED"
    assert fake.saved == [("b" * 32, "s3://bucket/sp", False)]


def test_savepoint_with_stop_cancels_the_job(session, monkeypatch):
    fake, job = _flink_job(session, monkeypatch)
    client = TestClient(app)

    response = client.post(
        "/api/v1/engine/jobs/%d/savepoint" % job.id, headers=_headers(),
        json={"target_directory": "s3://bucket/sp", "stop": True})

    assert response.status_code == 200
    session.refresh(job)
    assert job.status == "cancelled"
    assert fake.saved[0][2] is True


def test_savepoint_rejects_spark_jobs(session, monkeypatch):
    class FakeSpark:
        def submit(self, spec):
            return spec.name

    monkeypatch.setattr("odf.services.engine_jobs._spark_engine", FakeSpark)
    job = submit_job(session, 1, "spark", "sps-%s" % uuid.uuid4().hex[:8],
                     {"image": "apache/spark:3.5.1",
                      "main_application_file": "local:///a.py"}, "tester")
    response = TestClient(app).post(
        "/api/v1/engine/jobs/%d/savepoint" % job.id, headers=_headers(),
        json={"target_directory": "s3://bucket/sp"})
    assert response.status_code == 400
    assert "flink" in response.json()["detail"]
