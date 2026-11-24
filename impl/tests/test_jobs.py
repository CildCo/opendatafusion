from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.db import Base
from odf.models import Asset
from odf.services.jobs import (claim, complete, enqueue_asset,
                               requeue_stale)


def _session():
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    return sessionmaker(bind=e)()


def _pipeline(s):
    asset = Asset(project_id=1, type="pipeline", key="p1", name="copy",
                  owner="admin")
    s.add(asset)
    s.commit()
    s.refresh(asset)
    return asset


def test_enqueue_dedupes():
    s = _session()
    a = _pipeline(s)
    first = enqueue_asset(s, a.id, "pipeline")
    second = enqueue_asset(s, a.id, "pipeline")
    assert first.id == second.id


def test_claim_and_complete():
    s = _session()
    a = _pipeline(s)
    job = enqueue_asset(s, a.id, "pipeline")
    got = claim(s, "w1")
    assert got.id == job.id and got.status == "running"
    assert claim(s, "w2") is None
    assert complete(s, job.id, True).status == "success"


def test_retry_then_failed():
    s = _session()
    a = _pipeline(s)
    job = enqueue_asset(s, a.id, "pipeline")
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
    a = _pipeline(s)
    job = enqueue_asset(s, a.id, "pipeline")
    claim(s, "w1")
    job.heartbeat_at = datetime.now(timezone.utc) - timedelta(hours=1)
    s.commit()
    assert requeue_stale(s, 60) == 1
    s.refresh(job)
    assert job.status == "queued"
