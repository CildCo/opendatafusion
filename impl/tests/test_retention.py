from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.db import Base
from odf.models import (Alert, Job, Notification, NotificationRead,
                        PipelineNodeRun, QueryRun, WebhookDelivery)
from odf.services.retention import counts, prune, policies


def _env():
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    return sessionmaker(bind=e)()


def _old(days):
    return datetime.now(timezone.utc) - timedelta(days=days)


def _seed(s):
    s.add(QueryRun(project_id=1, actor="a", source="workbench",
                   status="ok", sql_hash="h", sql_preview="select 1",
                   sql_text="select 1", created_at=_old(60)))
    s.add(QueryRun(project_id=1, actor="a", source="workbench",
                   status="ok", sql_hash="h", sql_preview="select 2",
                   sql_text="select 2", created_at=_old(1)))
    old_job = Job(project_id=1, status="success", run_at=_old(100),
                  created_at=_old(100), finished_at=_old(100))
    running = Job(project_id=1, status="running", run_at=_old(100),
                  created_at=_old(100))
    recent = Job(project_id=1, status="success", run_at=_old(1),
                 created_at=_old(1), finished_at=_old(1))
    s.add_all([old_job, running, recent])
    s.flush()
    s.add(PipelineNodeRun(job_id=old_job.id, asset_id=1, node_id="n",
                          status="success", created_at=_old(100)))
    note = Notification(project_id=1, title="old", created_at=_old(60))
    s.add(note)
    s.flush()
    s.add(NotificationRead(user_id=1, notification_id=note.id))
    s.add(Notification(project_id=1, title="new", created_at=_old(1)))
    s.add(Alert(project_id=1, severity="info", title="closed",
                status="closed", created_at=_old(200)))
    s.add(Alert(project_id=1, severity="info", title="open",
                status="open", created_at=_old(200)))
    s.add(WebhookDelivery(subscription_id=1, project_id=1, event="x",
                          status="delivered", created_at=_old(60)))
    s.add(WebhookDelivery(subscription_id=1, project_id=1, event="x",
                          status="pending", created_at=_old(60)))
    s.commit()


def test_policies_defaults():
    out = policies()
    assert out["query_run"] == 30
    assert out["job"] == 90
    assert out["alert"] == 180


def test_counts_and_dry_run():
    s = _env()
    _seed(s)
    before = counts(s)
    assert before["query_run"] == 1
    assert before["job"] == 1
    assert before["notification"] == 1
    assert before["alert"] == 1
    assert before["webhook_delivery"] == 1
    result = prune(s, apply=False)
    assert result["query_run"]["removed"] == 0
    assert counts(s) == before


def test_prune_removes_only_eligible_rows():
    s = _env()
    _seed(s)
    result = prune(s, apply=True)
    assert result["query_run"]["removed"] == 1
    assert result["job"]["removed"] == 1
    assert result["notification"]["removed"] == 1
    assert result["alert"]["removed"] == 1
    assert result["webhook_delivery"]["removed"] == 1
    assert s.query(QueryRun).count() == 1
    assert s.query(Job).count() == 2
    assert s.query(Job).filter_by(status="running").count() == 1
    assert s.query(Notification).count() == 1
    assert s.query(NotificationRead).count() == 0
    assert s.query(PipelineNodeRun).count() == 0
    assert s.query(Alert).count() == 1
    assert s.query(WebhookDelivery).count() == 1


def test_zero_days_disables_a_policy():
    s = _env()
    _seed(s)
    result = prune(s, overrides={"query_run": 0}, apply=True)
    assert result["query_run"]["removed"] == 0
    assert s.query(QueryRun).count() == 2
    assert result["job"]["removed"] == 1


def test_custom_days_are_validated():
    s = _env()
    with pytest.raises(ValueError):
        prune(s, overrides={"job": -3}, apply=False)
