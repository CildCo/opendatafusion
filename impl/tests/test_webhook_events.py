from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.assets.service import create_asset, publish_asset
from odf.db import Base
from odf.models import Flow, Job, Project, WebhookDelivery
from odf.services.alerts import raise_alert
from odf.services.jobs import complete, scheduler_tick
from odf.webhooks import service


def _env(monkeypatch):
    monkeypatch.setattr(
        service, "get_settings",
        lambda: SimpleNamespace(webhook_allow_private=True,
                                webhook_max_payload=65536))
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Project(id=1, code="e1", name="e1", status=1))
    s.commit()
    service.create_subscription(s, 1, "all", "http://127.0.0.1:9/h", [],
                                True, "u")
    return s


def test_publish_and_alert_emit(monkeypatch):
    s = _env(monkeypatch)
    a = create_asset(s, 1, "dashboard", "D", {"widgets": []}, "u",
                     enabled=False)
    publish_asset(s, a.id, "u")
    events = [d.event for d in s.query(WebhookDelivery).all()]
    assert events == ["asset.published"]
    raise_alert(s, 1, "warning", "test alert")
    events = [d.event for d in s.query(WebhookDelivery).all()]
    assert events == ["asset.published", "alert.raised"]


def test_failed_job_emits(monkeypatch):
    s = _env(monkeypatch)
    f = Flow(id=801, project_id=1, name="f", cron="")
    s.add(f)
    s.commit()
    job = Job(id=802, flow_id=801, status="running", attempts=0,
              max_attempts=1)
    s.add(job)
    s.commit()
    complete(s, 802, False, "boom")
    s.refresh(job)
    assert job.status == "failed"
    events = [d.event for d in s.query(WebhookDelivery).all()]
    assert events == ["job.failed"]


def test_scheduler_tick_delivers(monkeypatch):
    s = _env(monkeypatch)
    called = []
    monkeypatch.setattr(service, "deliver_due",
                        lambda sess: called.append(True) or 0)
    scheduler_tick(s)
    assert called
