import uuid

import pytest

from odf.engine import JobStatus
from odf.models import EngineJob
from odf.services import jobs as job_service


class FakeSpark:
    def __init__(self, status):
        self._status = status

    def submit(self, spec):
        return spec.name

    def status(self, name, namespace=None):
        return self._status

    def result(self, name, namespace=None):
        return {"state": "", "error": ""}

    def cancel(self, name, namespace=None):
        pass


@pytest.fixture()
def session():
    from odf.db import SessionLocal
    with SessionLocal() as s:
        yield s


def _running(session, name=None):
    job = EngineJob(project_id=1, engine="spark",
                    name=name or "sync-%s" % uuid.uuid4().hex[:8],
                    spec_json={"image": "apache/spark:3.5.1",
                               "main_application_file": "local:///a.py"},
                    status="running", external_id="x", submitted_by="w",
                    attempts=1)
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def test_tick_syncs_running_engine_jobs(session, monkeypatch):
    monkeypatch.setattr("odf.services.engine_jobs._spark_engine",
                        lambda: FakeSpark(JobStatus.SUCCEEDED))
    job = _running(session)

    job_service.tick(session, "worker-1")

    session.refresh(job)
    assert job.status == "succeeded"


def test_tick_is_not_blocked_by_sync_failure(session, monkeypatch):
    class Boom:
        def status(self, name, namespace=None):
            raise RuntimeError("k8s down")

    monkeypatch.setattr("odf.services.engine_jobs._spark_engine", Boom)
    job = _running(session)

    job_service.tick(session, "worker-1")

    session.refresh(job)
    assert job.status == "running"


def test_tick_returns_none_without_queued_work(session, monkeypatch):
    monkeypatch.setattr(job_service, "claim", lambda s, w: None)
    assert job_service.tick(session, "worker-1") is None


def test_tick_processes_claimed_job(session, monkeypatch):
    processed = []
    monkeypatch.setattr(job_service, "claim", lambda s, w: object())
    monkeypatch.setattr(job_service, "process_job",
                        lambda s, job, w: processed.append(job))
    job_service.tick(session, "worker-1")
    assert len(processed) == 1
