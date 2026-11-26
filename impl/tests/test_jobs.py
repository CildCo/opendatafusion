import pytest
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


def test_asset_run_policy_sets_job_attempts_and_backoff():
    s = _session()
    a = _pipeline(s)
    a.max_attempts = 5
    a.retry_backoff_seconds = 12
    s.commit()
    job = enqueue_asset(s, a.id, "pipeline")
    assert job.max_attempts == 5
    assert job.payload_json["retry_backoff_seconds"] == 12
    claim(s, "w1")
    before = datetime.now(timezone.utc)
    job = complete(s, job.id, False, "boom")
    assert job.status == "queued"
    delay = (job.run_at.replace(tzinfo=timezone.utc) - before).total_seconds()
    assert 8 <= delay <= 20


def test_ops_run_policy_detail_compare_and_schedules():
    from odf.models import PipelineNodeRun
    from odf.ops.service import (job_compare, job_detail, run_policies,
                                 schedules, update_run_policy)

    s = _session()
    a = _pipeline(s)
    a.cron = "0 0 2 * * *"
    s.commit()
    updated = update_run_policy(s, 1, a.id, 4, 15, "admin")
    assert updated["max_attempts"] == 4
    assert run_policies(s, 1)[0]["retry_backoff_seconds"] == 15
    with pytest.raises(ValueError):
        update_run_policy(s, 1, a.id, 0, 15, "admin")
    with pytest.raises(ValueError):
        update_run_policy(s, 1, a.id, 4, -1, "admin")

    first = enqueue_asset(s, a.id, "pipeline")
    claim(s, "w1")
    s.add(PipelineNodeRun(job_id=first.id, asset_id=a.id, node_id="src",
                          status="ok", in_num=10, out_num=10, ms=100))
    complete(s, first.id, True)
    second = enqueue_asset(s, a.id, "pipeline")
    claim(s, "w1")
    s.add(PipelineNodeRun(job_id=second.id, asset_id=a.id, node_id="src",
                          status="ok", in_num=50, out_num=50, ms=80))
    complete(s, second.id, True)

    detail = job_detail(s, 1, second.id)
    assert detail["nodes"][0]["node_id"] == "src"
    assert detail["payload"]["retry_backoff_seconds"] == 15
    diff = job_compare(s, 1, second.id)
    assert diff["previous"]["id"] == first.id
    assert diff["nodes"][0]["ms_delta"] == -20
    assert diff["nodes"][0]["out_delta"] == 40
    schedule = schedules(s, 1)[0]
    assert schedule["cron"] == "0 0 2 * * *"
    assert schedule["next_run"]
