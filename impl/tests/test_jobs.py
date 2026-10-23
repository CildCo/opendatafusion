from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.db import Base
from odf.models import Flow
from odf.services.jobs import (claim, complete, enqueue, requeue_stale)


def _session():
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    return sessionmaker(bind=e)()


def _flow(s):
    f = Flow(project_id=1, name="copy", cron="0 */5 * * * ?", status=1)
    s.add(f)
    s.commit()
    s.refresh(f)
    return f


def test_enqueue_dedupes():
    s = _session()
    f = _flow(s)
    a = enqueue(s, f.id)
    b = enqueue(s, f.id)
    assert a.id == b.id


def test_claim_and_complete():
    s = _session()
    f = _flow(s)
    job = enqueue(s, f.id)
    got = claim(s, "w1")
    assert got.id == job.id and got.status == "running"
    assert claim(s, "w2") is None
    assert complete(s, job.id, True).status == "success"


def test_retry_then_failed():
    s = _session()
    f = _flow(s)
    job = enqueue(s, f.id)
    claim(s, "w1")
    j = complete(s, job.id, False, "boom")
    assert j.status == "queued" and j.attempts == 1
    j.run_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    s.commit()
    claim(s, "w1")
    j = complete(s, job.id, False, "boom2")
    assert j.status == "queued" and j.attempts == 2
    j.run_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    s.commit()
    claim(s, "w1")
    j = complete(s, job.id, False, "boom3")
    assert j.status == "failed" and j.attempts == 3


def test_requeue_stale():
    s = _session()
    f = _flow(s)
    job = enqueue(s, f.id)
    claim(s, "w1")
    job.heartbeat_at = datetime.now(timezone.utc) - timedelta(hours=1)
    s.commit()
    assert requeue_stale(s, 60) == 1
    s.refresh(job)
    assert job.status == "queued"
