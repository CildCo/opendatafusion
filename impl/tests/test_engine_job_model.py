import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from odf.models import EngineJob


@pytest.fixture()
def session():
    from odf.db import SessionLocal
    with SessionLocal() as s:
        yield s


def _name(prefix):
    return "%s-%s" % (prefix, uuid.uuid4().hex[:8])


def test_engine_job_defaults(session):
    job = EngineJob(project_id=1, engine="spark", name=_name("defaults"),
                    spec_json={"image": "apache/spark:3.5.1"},
                    submitted_by="tester")
    session.add(job)
    session.commit()
    session.refresh(job)

    assert job.id > 0
    assert job.status == "pending"
    assert job.attempts == 0
    assert job.max_attempts == 2
    assert job.external_id == ""
    assert job.result_json == {}
    assert job.asset_id is None
    assert job.created_at is not None
    assert job.spec_json == {"image": "apache/spark:3.5.1"}


def test_engine_job_name_is_unique(session):
    name = _name("dup")
    session.add(EngineJob(project_id=1, engine="spark", name=name,
                          spec_json={}, submitted_by="tester"))
    session.commit()
    session.add(EngineJob(project_id=1, engine="flink", name=name,
                          spec_json={}, submitted_by="tester"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
