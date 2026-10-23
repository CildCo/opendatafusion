import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.assets.service import create_asset
from odf.db import Base
from odf.services.jobs import enqueue_asset, process_job


@pytest.fixture()
def s():
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    with sessionmaker(bind=e)() as sess:
        yield sess


def test_enqueue_asset_dedupes(s):
    a = create_asset(s, 1, "pipeline", "p", {}, "admin")
    j1 = enqueue_asset(s, a.id)
    j2 = enqueue_asset(s, a.id)
    assert j1.id == j2.id
    assert j1.asset_type == "pipeline"


def test_process_job_dispatches_pipeline(s, monkeypatch):
    called = {}
    monkeypatch.setattr(
        "odf.pipeline.runner.execute_pipeline",
        lambda *a, **k: called.setdefault("hit", True))
    a = create_asset(s, 1, "pipeline", "p", {}, "admin")
    job = enqueue_asset(s, a.id)
    process_job(s, job, "w1")
    assert called.get("hit") is True
    s.refresh(job)
    assert job.status == "success"
