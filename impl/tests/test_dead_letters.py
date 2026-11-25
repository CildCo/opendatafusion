from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.assets.service import create_asset
from odf.db import Base
from odf.models import Job, Project
from odf.ops.service import dead_letters, replay_jobs


def _env():
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Project(id=1, code="p", name="P", status=1))
    s.commit()
    return s


def _job(s, status="failed", asset_type="pipeline", name="p"):
    asset = create_asset(s, 1, asset_type, name,
                         {"nodes": [], "edges": []}, "admin")
    job = Job(project_id=1, asset_id=asset.id, asset_type=asset_type,
              status=status, finished_at=datetime.now(timezone.utc),
              last_error="boom", payload_json={})
    s.add(job)
    s.commit()
    return job, asset


def test_dead_letters_lists_failed_jobs():
    s = _env()
    failed, _ = _job(s)
    _job(s, status="success", name="ok")
    rows = dead_letters(s, 1)
    assert [row["id"] for row in rows] == [failed.id]
    assert rows[0]["last_error"] == "boom"


def test_dead_letters_filters_by_type_and_limit():
    s = _env()
    _job(s, asset_type="model", name="m")
    _job(s, asset_type="pipeline", name="p")
    assert len(dead_letters(s, 1, asset_type="model")) == 1
    assert len(dead_letters(s, 1, limit=1)) == 1


def test_replay_requeues_failed_jobs():
    s = _env()
    job, _ = _job(s)
    out = replay_jobs(s, 1, [job.id], "alice")
    assert out["replayed"] == [job.id]
    s.refresh(job)
    assert job.status == "queued"
    assert job.attempts == 0
    assert job.last_error is None


def test_replay_skips_non_failed_and_duplicates():
    s = _env()
    job, asset = _job(s)
    other = Job(project_id=1, asset_id=asset.id, asset_type="pipeline",
                status="failed", last_error="x", payload_json={})
    s.add(other)
    s.commit()
    out = replay_jobs(s, 1, [job.id, other.id, 999], "alice")
    assert out["replayed"] == [job.id]
    reasons = {item["id"]: item["reason"] for item in out["skipped"]}
    assert "already" in reasons[other.id]
    assert "not found" in reasons[999]


def test_replay_rejects_large_batches():
    s = _env()
    with pytest.raises(ValueError):
        replay_jobs(s, 1, list(range(101)), "alice")
