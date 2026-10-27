import uuid

import pytest
from fastapi.testclient import TestClient

from odf.db import SessionLocal
from odf.main import app
from odf.models import AuditLog, User
from odf.services.auth import create_token


class FakeEngine:
    def __init__(self):
        self.submitted = []
        self.cancelled = []

    def submit(self, spec):
        self.submitted.append(spec)
        return spec.name

    def status(self, name, namespace=None):
        from odf.engine import JobStatus
        return JobStatus.RUNNING

    def cancel(self, name, namespace=None):
        self.cancelled.append(name)

    def result(self, name, namespace=None):
        return {"state": "", "error": ""}


class FakeGateway:
    def __init__(self):
        self.calls = []

    def execute(self, statement, properties=None, attached=True):
        self.calls.append((statement, attached))
        return {"resultType": "PAYLOAD",
                "results": {"columns": [], "data": []}}

    def job_status(self, job_id):
        from odf.engine import JobStatus
        return JobStatus.RUNNING

    def cancel(self, job_id):
        pass


def _user(uid, role):
    with SessionLocal() as s:
        user = s.get(User, uid)
        if not user:
            user = User(id=uid, username="eng_%d" % uid, password_hash="x",
                        role=role, active=True)
            s.add(user)
        else:
            user.role = role
            user.active = True
        s.commit()
    return uid


def _headers(uid, role, project_id=1):
    _user(uid, role)
    return {"Authorization": "Bearer " + create_token(uid, project_id)}


def _name(prefix="eng"):
    return "%s-%s" % (prefix, uuid.uuid4().hex[:8])


def _spark_spec(**overrides):
    spec = {"image": "apache/spark:3.5.1",
            "main_application_file": "local:///opt/spark/work-dir/job.py",
            "driver_memory": "2g", "executor_instances": 2,
            "spark_conf": {"spark.sql.catalog.x": "y"}}
    spec.update(overrides)
    return spec


def _submit(client, headers, name, engine="spark", spec=None):
    return client.post("/api/v1/engine/jobs", headers=headers,
                       json={"engine": engine, "name": name,
                             "spec": spec if spec is not None else _spark_spec()})


def test_submit_spark_job_returns_201(monkeypatch):
    fake = FakeEngine()
    monkeypatch.setattr("odf.services.engine_jobs._spark_engine", lambda: fake)
    name = _name()
    response = _submit(TestClient(app), _headers(911, "editor"), name)

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == name
    assert body["status"] == "running"
    assert body["engine"] == "spark"
    spec = fake.submitted[0]
    assert spec.image == "apache/spark:3.5.1"
    assert spec.driver_memory == "2g"
    assert spec.executor_instances == 2
    assert spec.spark_conf["spark.sql.catalog.x"] == "y"


def test_viewer_cannot_submit():
    response = _submit(TestClient(app), _headers(912, "viewer"), _name())
    assert response.status_code == 403


def test_disallowed_image_is_rejected(monkeypatch):
    monkeypatch.setattr("odf.services.engine_jobs._spark_engine", FakeEngine)
    response = _submit(TestClient(app), _headers(913, "editor"), _name(),
                       spec=_spark_spec(image="evil/image:latest"))
    assert response.status_code == 400
    assert "image" in response.json()["detail"]


def test_main_file_scheme_is_rejected(monkeypatch):
    monkeypatch.setattr("odf.services.engine_jobs._spark_engine", FakeEngine)
    response = _submit(TestClient(app), _headers(913, "editor"), _name(),
                       spec=_spark_spec(main_application_file="http://x/job.py"))
    assert response.status_code == 400


def test_submit_without_engine_config_returns_503():
    response = _submit(TestClient(app), _headers(914, "editor"), _name())
    assert response.status_code == 503


def test_list_jobs_is_project_scoped(monkeypatch):
    monkeypatch.setattr("odf.services.engine_jobs._spark_engine", FakeEngine)
    client = TestClient(app)
    mine = _name()
    theirs = _name()
    assert _submit(client, _headers(915, "editor", 1), mine).status_code == 201
    assert _submit(client, _headers(915, "editor", 2), theirs).status_code == 201

    rows = client.get("/api/v1/engine/jobs",
                      headers=_headers(915, "editor", 1)).json()
    names = [r["name"] for r in rows]
    assert mine in names
    assert theirs not in names


def test_get_job_from_other_project_returns_404(monkeypatch):
    monkeypatch.setattr("odf.services.engine_jobs._spark_engine", FakeEngine)
    client = TestClient(app)
    created = _submit(client, _headers(916, "editor", 1), _name()).json()

    response = client.get("/api/v1/engine/jobs/%d" % created["id"],
                          headers=_headers(916, "editor", 2))
    assert response.status_code == 404


def test_cancel_job_marks_cancelled(monkeypatch):
    fake = FakeEngine()
    monkeypatch.setattr("odf.services.engine_jobs._spark_engine", lambda: fake)
    client = TestClient(app)
    headers = _headers(917, "editor")
    created = _submit(client, headers, _name()).json()

    response = client.delete("/api/v1/engine/jobs/%d" % created["id"],
                             headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert fake.cancelled


def test_engine_sql_requires_approver(monkeypatch):
    monkeypatch.setattr("odf.services.engine_jobs._flink_gateway",
                        FakeGateway)
    response = TestClient(app).post(
        "/api/v1/engine/sql", headers=_headers(918, "editor"),
        json={"statement": "SHOW CATALOGS"})
    assert response.status_code == 403


def test_engine_sql_runs_read_only_statement(monkeypatch):
    gateway = FakeGateway()
    monkeypatch.setattr("odf.services.engine_jobs._flink_gateway",
                        lambda: gateway)
    response = TestClient(app).post(
        "/api/v1/engine/sql", headers=_headers(919, "approver"),
        json={"statement": "SHOW CATALOGS",
              "properties": {"execution.runtime-mode": "streaming"}})

    assert response.status_code == 200
    body = response.json()
    assert body["result"]["resultType"] == "PAYLOAD"
    assert gateway.calls == [("SHOW CATALOGS", True)]


def test_engine_sql_blocks_writes_by_default(monkeypatch):
    gateway = FakeGateway()
    monkeypatch.setattr("odf.services.engine_jobs._flink_gateway",
                        lambda: gateway)
    response = TestClient(app).post(
        "/api/v1/engine/sql", headers=_headers(919, "approver"),
        json={"statement": "DROP TABLE demo.events"})
    assert response.status_code == 403
    assert gateway.calls == []


def test_engine_sql_allows_writes_when_enabled(monkeypatch):
    gateway = FakeGateway()
    monkeypatch.setattr("odf.services.engine_jobs._flink_gateway",
                        lambda: gateway)

    class Enabled:
        engine_sql_write_enabled = True
        k8s_allowed_images = "apache/spark,flink"

    monkeypatch.setattr("odf.api.engine.get_settings", lambda: Enabled())
    response = TestClient(app).post(
        "/api/v1/engine/sql", headers=_headers(920, "approver"),
        json={"statement": "DROP TABLE demo.events"})
    assert response.status_code == 200


def test_engine_sql_rejects_oversized_statement():
    response = TestClient(app).post(
        "/api/v1/engine/sql", headers=_headers(921, "approver"),
        json={"statement": "SELECT " + "1" * 100001})
    assert response.status_code == 422


def test_engine_sql_is_audited(monkeypatch):
    monkeypatch.setattr("odf.services.engine_jobs._flink_gateway",
                        lambda: FakeGateway())
    client = TestClient(app)
    response = client.post(
        "/api/v1/engine/sql", headers=_headers(922, "approver"),
        json={"statement": "SELECT 1"})
    assert response.status_code == 200
    with SessionLocal() as s:
        actions = [a.action for a in s.query(AuditLog).filter_by(
            actor="922").all()]
    assert "engine_sql" in actions


def test_flink_job_requires_statement(monkeypatch):
    monkeypatch.setattr("odf.services.engine_jobs._flink_gateway",
                        FakeGateway)
    response = _submit(TestClient(app), _headers(923, "editor"), _name(),
                       engine="flink", spec={})
    assert response.status_code == 400


def test_spark_job_without_image_uses_lakehouse_profile(monkeypatch):
    from types import SimpleNamespace

    fake = FakeEngine()
    monkeypatch.setattr("odf.services.engine_jobs._spark_engine", lambda: fake)
    profile = SimpleNamespace(
        lakehouse_enabled=True, lakehouse_catalog="iceberg",
        lakehouse_uri="http://nessie:19120/iceberg",
        lakehouse_warehouse="warehouse", lakehouse_s3_endpoint="",
        lakehouse_s3_region="us-east-1",
        spark_image="odf/spark-iceberg:3.5.1", spark_jars="",
        k8s_allowed_images="apache/spark,flink,odf/spark",
        engine_sql_write_enabled=False,
        flink_sql_gateway_url="", flink_rest_url="")
    monkeypatch.setattr("odf.api.engine.get_settings", lambda: profile)
    monkeypatch.setattr("odf.services.engine_jobs.get_settings",
                        lambda: profile)

    response = _submit(TestClient(app), _headers(924, "editor"), _name(),
                       spec={"main_application_file": "local:///app.py"})

    assert response.status_code == 201
    spec = fake.submitted[0]
    assert spec.image == "odf/spark-iceberg:3.5.1"
    assert spec.spark_conf["spark.sql.catalog.iceberg.type"] == "rest"
    assert spec.spark_conf["spark.sql.catalog.iceberg.uri"] == \
        "http://nessie:19120/iceberg"
