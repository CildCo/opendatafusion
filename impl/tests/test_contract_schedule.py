from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from odf.assets.service import create_asset
from odf.db import Base
from odf.models import ContractCheck, Datasource, Job
from odf.services.contracts import (checks, due_schedules, generate_contract,
                                    save_check)
from odf.services.crypto import encrypt_secret
from odf.services.governance import update_asset_governance
from odf.services.jobs import process_job, scheduler_tick


def _env(tmp_path):
    url = "sqlite:///" + str(tmp_path / "c.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table orders (id int, city text)"))
    raw.dispose()
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Datasource(id=1, project_id=1, name="local", kind="sqlite",
                     dsn_encrypted=encrypt_secret(url)))
    s.commit()
    return s


def _dataset(s):
    return create_asset(
        s, 1, "dataset", "orders",
        {"query": {"datasource_id": 1, "table": "orders"}}, "admin")


def test_schedule_validation():
    s = _env_empty()
    asset = create_asset(
        s, 1, "dataset", "d",
        {"query": {"datasource_id": 1, "table": "t"}}, "admin")
    with pytest.raises(ValueError):
        update_asset_governance(s, 1, asset.id,
                                contract={"schedule": "not a cron"})
    out = update_asset_governance(s, 1, asset.id,
                                  contract={"schedule": "0 0 6 * * *"})
    assert out["contract"]["schedule"] == "0 0 6 * * *"


def _env_empty():
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    return sessionmaker(bind=e)()


def test_due_schedules_and_scheduler_enqueue(tmp_path):
    s = _env(tmp_path)
    asset = _dataset(s)
    generate_contract(s, 1, asset.id)
    update_asset_governance(s, 1, asset.id,
                            contract={"schedule": "* * * * * *"})
    assert [row.id for row in due_schedules(s,
                                            datetime.now(timezone.utc))] \
        == [asset.id]
    scheduler_tick(s, now=datetime.now(timezone.utc))
    job = (s.query(Job).filter_by(asset_id=asset.id,
                                  asset_type="contract").first())
    assert job and job.status == "queued"


def test_contract_job_stores_result(tmp_path):
    s = _env(tmp_path)
    asset = _dataset(s)
    generate_contract(s, 1, asset.id)
    job = Job(project_id=1, asset_id=asset.id, asset_type="contract",
              status="running", payload_json={})
    s.add(job)
    s.commit()
    process_job(s, job, "worker")
    s.refresh(job)
    assert job.status == "success"
    rows = checks(s, 1, asset.id)
    assert rows[0]["status"] == "ok"


def test_failing_contract_job_is_recorded_and_raised(tmp_path):
    s = _env(tmp_path)
    asset = _dataset(s)
    update_asset_governance(
        s, 1, asset.id,
        contract={"schema": [{"name": "id"}, {"name": "ghost"}]})
    job = Job(project_id=1, asset_id=asset.id, asset_type="contract",
              status="running", payload_json={})
    s.add(job)
    s.commit()
    with pytest.raises(ValueError):
        process_job(s, job, "worker")
    rows = checks(s, 1, asset.id)
    assert rows[0]["status"] == "failed"
    assert rows[0]["issues"][0]["kind"] == "missing"


def test_save_check_roundtrip(tmp_path):
    s = _env(tmp_path)
    asset = _dataset(s)
    row = save_check(s, asset, {"ok": True, "issues": []})
    assert row.status == "ok"
    assert s.query(ContractCheck).count() == 1
