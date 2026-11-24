from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from odf.assets.service import create_asset, publish_asset
from odf.dashboards.report import (due_schedules, run_report,
                                   schedule_for, upsert_schedule)
from odf.db import Base
from odf.models import (Datasource, FileObject, Job, Notification,
                        ReportSchedule, WebhookDelivery,
                        WebhookSubscription)
from odf.services.crypto import encrypt_secret

DATASET = {"mode": "visual", "query": {
    "datasource_id": 1, "table": "t",
    "select": [{"column": "city"}, {"column": "amount"}],
    "limit": 100}, "params": []}


def _env(tmp_path):
    url = "sqlite:///" + str(tmp_path / "rep.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table t (city text, amount int)"))
        c.execute(text("insert into t values ('a',10),('a',5),('b',7)"))
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                     dsn_encrypted=encrypt_secret(url)))
    s.commit()
    return s


def _dashboard(s, widgets=None):
    d = create_asset(s, 1, "dataset", "D", DATASET, "admin", enabled=False)
    publish_asset(s, d.id, "admin")
    content = {"columns": 12, "widgets": widgets or [
        {"id": "t", "type": "table", "dataset_id": d.id,
         "x": 0, "y": 0, "w": 6, "h": 4}]}
    dash = create_asset(s, 1, "dashboard", "Dash", content, "admin",
                        enabled=False)
    publish_asset(s, dash.id, "admin")
    return dash.id


def test_schedule_is_created_and_returned(tmp_path):
    s = _env(tmp_path)
    dash = _dashboard(s)
    row = upsert_schedule(s, 1, dash, "0 0 8 * * *", True, "admin")
    assert row["cron"] == "0 0 8 * * *"
    assert schedule_for(s, 1, dash)["enabled"] is True
    with pytest.raises(ValueError):
        upsert_schedule(s, 1, dash, "not a cron", True, "admin")


def test_report_writes_file_notification_and_webhook(tmp_path):
    s = _env(tmp_path)
    dash = _dashboard(s)
    s.add(WebhookSubscription(
        project_id=1, name="hook", url="https://example.com/hook",
        secret_encrypted=encrypt_secret("secret-value"), events_json=[],
        enabled=True, created_by="admin"))
    s.commit()
    schedule = upsert_schedule(s, 1, dash, "0 0 8 * * *", True, "admin")
    out = run_report(s, schedule["id"], "scheduler")
    assert out["file_id"]
    assert s.get(FileObject, out["file_id"]).size > 0
    assert s.query(Notification).filter_by(
        project_id=1, kind="report").count() == 1
    delivery = s.query(WebhookDelivery).one()
    assert delivery.event == "report.ready"
    assert delivery.payload_json["dashboard_id"] == dash
    row = schedule_for(s, 1, dash)
    assert row["last_status"] == "ok"
    assert row["last_run_at"] is not None


def test_report_without_tabular_data_fails(tmp_path):
    s = _env(tmp_path)
    dash = _dashboard(s, widgets=[
        {"id": "x", "type": "text", "text": "hello",
         "x": 0, "y": 0, "w": 3, "h": 2}])
    schedule = upsert_schedule(s, 1, dash, "0 0 8 * * *", True, "admin")
    try:
        run_report(s, schedule["id"], "scheduler")
    except ValueError as error:
        assert "tabular" in str(error)
    else:
        raise AssertionError("empty report must fail")


def _past_run(s, dash):
    row = (s.query(ReportSchedule)
           .filter_by(asset_id=dash).one())
    row.last_run_at = datetime(2026, 11, 22, 8, 0, tzinfo=timezone.utc)
    s.commit()


def test_due_schedule_fires_after_cron(tmp_path):
    s = _env(tmp_path)
    dash = _dashboard(s)
    upsert_schedule(s, 1, dash, "0 0 8 * * *", True, "admin")
    _past_run(s, dash)
    now = datetime(2026, 11, 24, 9, 0, tzinfo=timezone.utc)
    assert [row.asset_id for row in due_schedules(s, now)] == [dash]


def test_scheduler_enqueues_report_job(tmp_path):
    s = _env(tmp_path)
    dash = _dashboard(s)
    upsert_schedule(s, 1, dash, "0 0 8 * * *", True, "admin")
    _past_run(s, dash)
    from odf.services.jobs import process_job, scheduler_tick
    scheduler_tick(s, datetime(2026, 11, 24, 9, 0, tzinfo=timezone.utc))
    job = (s.query(Job)
           .filter_by(asset_id=dash, asset_type="dashboard_report").one())
    assert job.status == "queued"
    process_job(s, job, "worker")
    assert s.get(Job, job.id).status == "success"
