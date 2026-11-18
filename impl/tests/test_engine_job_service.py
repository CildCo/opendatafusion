import uuid

import pytest

from odf.engine import JobStatus
from odf.models import Alert, Asset, AuditLog, EngineJob
from odf.services.engine_jobs import (MAX_SYNC_FAILURES, cancel_job,
                                      job_out, submit_job, sync_due, sync_job)


class _FakeSpark:
    def __init__(self, status=JobStatus.RUNNING, error=""):
        self.submitted = []
        self.cancelled = []
        self._status = status
        self.error = error

    def submit(self, spec):
        self.submitted.append(spec)
        return spec.name

    def status(self, name, namespace=None):
        return self._status

    def cancel(self, name, namespace=None):
        self.cancelled.append(name)

    def result(self, name, namespace=None):
        return {"state": "", "error": self.error}


class _FakeFlink:
    def __init__(self, detached_job="a" * 32, status=JobStatus.RUNNING):
        self.calls = []
        self.cancelled = []
        self._detached_job = detached_job
        self._status = status

    def execute(self, statement, properties=None, attached=True):
        self.calls.append((statement, attached))
        if attached:
            return {"resultType": "PAYLOAD",
                    "results": {"columns": [], "data": []}}
        return {"job_id": self._detached_job}

    def job_status(self, job_id):
        return self._status

    def cancel(self, job_id):
        self.cancelled.append(job_id)


@pytest.fixture()
def session():
    from odf.db import SessionLocal
    with SessionLocal() as s:
        yield s


def _name(prefix="job"):
    return "%s-%s" % (prefix, uuid.uuid4().hex[:10])




def _running(session, name=None):
    job = EngineJob(project_id=1, engine="spark",
                    name=name or "sync-%s" % uuid.uuid4().hex[:8],
                    spec_json={"image": "apache/spark:3.5.1",
                               "main_application_file": "local:///a.py"},
                    status="running", external_id="x", submitted_by="w",
                    attempts=1, sync_failures=0)
    session.add(job)
    session.commit()
    session.refresh(job)
    return job

def _spark_spec():
    return {"image": "apache/spark:3.5.1",
            "main_application_file": "local:///opt/spark/app.py"}


def test_submit_spark_runs_and_audits(session, monkeypatch):
    fake = _FakeSpark()
    monkeypatch.setattr("odf.services.engine_jobs._spark_engine", lambda: fake)
    name = _name()

    job = submit_job(session, 1, "spark", name, _spark_spec(), "tester")

    assert job.status == "running"
    assert job.external_id == name
    assert job.attempts == 1
    assert fake.submitted[0].name == name
    actions = [a.action for a in session.query(AuditLog)
               .filter_by(target=str(job.id)).all()]
    assert "engine_job_submitted" in actions


def test_submit_failure_retries_then_fails(session, monkeypatch):
    class Boom(_FakeSpark):
        def submit(self, spec):
            raise RuntimeError("api unavailable")

    monkeypatch.setattr("odf.services.engine_jobs._spark_engine", Boom)
    actor = "fail-" + uuid.uuid4().hex[:8]
    with pytest.raises(ValueError, match="engine submission failed"):
        submit_job(session, 1, "spark", _name(), _spark_spec(), actor)

    job = (session.query(EngineJob)
           .filter_by(submitted_by=actor).one())
    assert job.status == "failed"
    assert job.attempts == job.max_attempts


def test_submit_rejects_duplicate_name(session, monkeypatch):
    monkeypatch.setattr("odf.services.engine_jobs._spark_engine",
                        _FakeSpark)
    name = _name()
    submit_job(session, 1, "spark", name, _spark_spec(), "tester")
    with pytest.raises(ValueError, match="already exists"):
        submit_job(session, 1, "spark", name, _spark_spec(), "tester")


def test_submit_rejects_foreign_asset(session, monkeypatch):
    monkeypatch.setattr("odf.services.engine_jobs._spark_engine",
                        _FakeSpark)
    other = Asset(project_id=2, type="pipeline", key="p-" + uuid.uuid4().hex,
                  name="other", owner="x")
    session.add(other)
    session.commit()
    with pytest.raises(ValueError, match="asset"):
        submit_job(session, 1, "spark", _name(), _spark_spec(), "tester",
                   asset_id=other.id)


def test_submit_rejects_unknown_engine(session):
    with pytest.raises(ValueError, match="engine"):
        submit_job(session, 1, "trino", _name(), {}, "tester")


def test_sync_marks_success(session, monkeypatch):
    fake = _FakeSpark(status=JobStatus.SUCCEEDED)
    monkeypatch.setattr("odf.services.engine_jobs._spark_engine", lambda: fake)
    job = submit_job(session, 1, "spark", _name(), _spark_spec(), "tester")

    sync_job(session, job)

    assert job.status == "succeeded"
    assert job.finished_at is not None
    assert job.synced_at is not None


def test_sync_marks_failure_and_alerts(session, monkeypatch):
    fake = _FakeSpark(status=JobStatus.FAILED, error="driver exited 1")
    monkeypatch.setattr("odf.services.engine_jobs._spark_engine", lambda: fake)
    name = _name()
    job = submit_job(session, 1, "spark", name, _spark_spec(), "tester")

    sync_job(session, job)

    assert job.status == "failed"
    assert job.error == "driver exited 1"
    alert = (session.query(Alert)
             .filter_by(project_id=1,
                        title="engine job failed: %s" % name).one())
    assert alert.severity == "error"


def test_sync_leaves_terminal_jobs_alone(session, monkeypatch):
    fake = _FakeSpark(status=JobStatus.RUNNING)
    monkeypatch.setattr("odf.services.engine_jobs._spark_engine", lambda: fake)
    job = submit_job(session, 1, "spark", _name(), _spark_spec(), "tester")
    job.status = "succeeded"
    session.commit()

    sync_job(session, job)
    assert job.status == "succeeded"


def test_cancel_marks_cancelled(session, monkeypatch):
    fake = _FakeSpark()
    monkeypatch.setattr("odf.services.engine_jobs._spark_engine", lambda: fake)
    job = submit_job(session, 1, "spark", _name(), _spark_spec(), "tester")

    cancel_job(session, job, "tester")

    assert job.status == "cancelled"
    assert fake.cancelled == [job.name]


def test_flink_attached_finishes_immediately(session, monkeypatch):
    fake = _FakeFlink()
    monkeypatch.setattr("odf.services.engine_jobs._flink_gateway", lambda: fake)
    job = submit_job(session, 1, "flink", _name(), {"statement": "SHOW CATALOGS"},
                     "tester")
    assert job.status == "succeeded"
    assert fake.calls == [("SHOW CATALOGS", True)]
    assert job.result_json["resultType"] == "PAYLOAD"


def test_flink_detached_records_job_id(session, monkeypatch):
    fake = _FakeFlink()
    monkeypatch.setattr("odf.services.engine_jobs._flink_gateway", lambda: fake)
    job = submit_job(session, 1, "flink", _name(), {
        "statement": "INSERT INTO t SELECT * FROM s", "attached": False},
        "tester")
    assert job.status == "running"
    assert job.external_id == "a" * 32


def test_sync_due_skips_terminal_and_does_not_resubmit(session, monkeypatch):
    fake = _FakeSpark(status=JobStatus.RUNNING)
    monkeypatch.setattr("odf.services.engine_jobs._spark_engine", lambda: fake)
    running = submit_job(session, 1, "spark", _name(), _spark_spec(), "tester")
    done = submit_job(session, 1, "spark", _name(), _spark_spec(), "tester")
    done.status = "succeeded"
    session.commit()
    submitted_before = len(fake.submitted)

    count = sync_due(session, 50)

    assert count >= 1
    assert len(fake.submitted) == submitted_before
    assert running.status == "running"


def test_job_out_shape(session, monkeypatch):
    monkeypatch.setattr("odf.services.engine_jobs._spark_engine", _FakeSpark)
    job = submit_job(session, 1, "spark", _name(), _spark_spec(), "tester")
    out = job_out(job)
    assert out["id"] == job.id
    assert out["engine"] == "spark"
    assert out["status"] == "running"
    assert out["name"] == job.name
    assert out["attempts"] == 1


def test_sync_failure_is_counted(session, monkeypatch):
    class Boom:
        def status(self, name, namespace=None):
            raise RuntimeError("k8s down")

    monkeypatch.setattr("odf.services.engine_jobs._spark_engine", Boom)
    job = _running(session)
    sync_due(session, 50)
    session.refresh(job)
    assert job.sync_failures >= 1
    assert job.status == "running"


def test_job_fails_after_repeated_sync_failures(session, monkeypatch):
    class Boom:
        def status(self, name, namespace=None):
            raise RuntimeError("k8s down")

    monkeypatch.setattr("odf.services.engine_jobs._spark_engine", Boom)
    job = _running(session)
    job.sync_failures = MAX_SYNC_FAILURES - 1
    session.commit()

    sync_due(session, 50)

    session.refresh(job)
    assert job.status == "failed"
    assert job.error == "engine status unavailable"


def test_cancel_tolerates_a_missing_engine_object(session, monkeypatch):
    import httpx

    class Gone:
        def cancel(self, name, namespace=None):
            raise httpx.HTTPStatusError(
                "gone", request=httpx.Request("DELETE", "http://k8s/x"),
                response=httpx.Response(404))

    monkeypatch.setattr("odf.services.engine_jobs._spark_engine", lambda: Gone())
    job = _running(session)
    cancel_job(session, job, "tester")
    assert job.status == "cancelled"


def test_cancel_surfaces_other_engine_errors(session, monkeypatch):
    import httpx

    class Broken:
        def cancel(self, name, namespace=None):
            raise httpx.HTTPStatusError(
                "boom", request=httpx.Request("DELETE", "http://k8s/x"),
                response=httpx.Response(500))

    monkeypatch.setattr("odf.services.engine_jobs._spark_engine", lambda: Broken())
    job = _running(session)
    with pytest.raises(httpx.HTTPStatusError):
        cancel_job(session, job, "tester")


def test_detached_flink_job_requires_a_real_id(session, monkeypatch):
    class BadGateway:
        def execute(self, statement, properties=None, attached=True):
            return {"job_id": "None"}

    monkeypatch.setattr("odf.services.engine_jobs._flink_gateway",
                        lambda: BadGateway())
    with pytest.raises(ValueError, match="job id"):
        submit_job(session, 1, "flink", "bad-%s" % uuid.uuid4().hex[:6],
                   {"statement": "INSERT INTO t SELECT 1", "attached": False},
                   "tester")


def test_status_uses_the_project_namespace(session, monkeypatch):
    seen = {}

    class NsAware:
        def status(self, name, namespace=None):
            seen["namespace"] = namespace
            from odf.engine import JobStatus
            return JobStatus.RUNNING

        def submit(self, spec):
            return spec.name

    monkeypatch.setattr("odf.services.engine_jobs._spark_engine", lambda: NsAware())
    job = EngineJob(project_id=1, engine="spark", name="ns-%s" % uuid.uuid4().hex[:8],
                    spec_json={"image": "apache/spark:3.5.1",
                               "main_application_file": "local:///a.py",
                               "namespace": "odf-p1"},
                    status="running", external_id="x", submitted_by="w", attempts=1)
    session.add(job)
    session.commit()

    sync_job(session, job)
    assert seen["namespace"] == "odf-p1"
