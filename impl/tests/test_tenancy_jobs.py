import uuid
from types import SimpleNamespace

import pytest

from odf.services.engine_jobs import submit_job


class FakeSpark:
    def __init__(self):
        self.submitted = []

    def submit(self, spec):
        self.submitted.append(spec)
        return spec.name

    def status(self, name, namespace=None):
        from odf.engine import JobStatus
        return JobStatus.RUNNING

    def cancel(self, name, namespace=None):
        pass

    def result(self, name, namespace=None):
        return {"state": "", "error": ""}


@pytest.fixture()
def session():
    from odf.db import SessionLocal
    with SessionLocal() as s:
        yield s


def _settings(enabled=True):
    return SimpleNamespace(
        lakehouse_enabled=False, spark_image="", spark_jars="",
        lakehouse_catalog="iceberg", lakehouse_uri="",
        lakehouse_warehouse="", lakehouse_s3_endpoint="",
        lakehouse_s3_region="", k8s_tenancy_enabled=enabled,
        k8s_tenancy_prefix="odf", k8s_quota_cpu="4",
        k8s_quota_memory="8Gi", k8s_quota_pods=20,
    )


def _spec():
    return {"image": "apache/spark:3.5.1",
            "main_application_file": "local:///app.py"}


def test_submit_targets_the_project_namespace(session, monkeypatch):
    fake = FakeSpark()
    prepared = []
    monkeypatch.setattr("odf.services.engine_jobs._spark_engine", lambda: fake)
    monkeypatch.setattr("odf.services.engine_jobs.get_settings",
                        lambda: _settings(True))
    monkeypatch.setattr("odf.services.tenancy.ensure_project_namespace",
                        lambda project_id, settings=None: prepared.append(
                            project_id) or "odf-p%d" % project_id)

    submit_job(session, 3, "spark", "ns-%s" % uuid.uuid4().hex[:8], _spec(),
               "tester")

    assert prepared == [3]
    assert fake.submitted[0].namespace == "odf-p3"


def test_submit_keeps_configured_namespace_when_tenancy_is_off(
        session, monkeypatch):
    fake = FakeSpark()
    monkeypatch.setattr("odf.services.engine_jobs._spark_engine", lambda: fake)
    monkeypatch.setattr("odf.services.engine_jobs.get_settings",
                        lambda: _settings(False))

    submit_job(session, 3, "spark", "ns-%s" % uuid.uuid4().hex[:8], _spec(),
               "tester")

    assert fake.submitted[0].namespace is None


def test_explicit_namespace_wins(session, monkeypatch):
    fake = FakeSpark()
    monkeypatch.setattr("odf.services.engine_jobs._spark_engine", lambda: fake)
    monkeypatch.setattr("odf.services.engine_jobs.get_settings",
                        lambda: _settings(True))
    monkeypatch.setattr("odf.services.tenancy.ensure_project_namespace",
                        lambda project_id, settings=None: "odf-p%d" % project_id)

    spec = dict(_spec(), namespace="custom-ns")
    submit_job(session, 3, "spark", "ns-%s" % uuid.uuid4().hex[:8], spec,
               "tester")

    assert fake.submitted[0].namespace == "custom-ns"
