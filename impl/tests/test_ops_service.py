from datetime import datetime, timezone

from odf.db import SessionLocal
from odf.models import Alert, Asset, Flow, HealthEvent, Job, Project
from odf.ops.service import (ack_alert, list_alerts, list_health, list_jobs,
                             retry_job, summary, timeline)


def _fixture():
    now = datetime.now(timezone.utc)
    with SessionLocal() as s:
        for pid, code in ((901, "ops901"), (902, "ops902")):
            if not s.get(Project, pid):
                s.add(Project(id=pid, code=code, name=code))
        s.flush()
        s.query(HealthEvent).filter(HealthEvent.id.in_([9501])).delete(
            synchronize_session=False)
        s.query(Alert).filter(Alert.id.in_([9401, 9402])).delete(
            synchronize_session=False)
        s.query(Job).filter(Job.id.in_([9301, 9302, 9303, 9304, 9305])).delete(
            synchronize_session=False)
        s.query(Flow).filter(Flow.id.in_([9101, 9102])).delete(
            synchronize_session=False)
        s.query(Asset).filter(Asset.id.in_([9201, 9202])).delete(
            synchronize_session=False)
        s.add_all([
            Flow(id=9101, project_id=901, name="p1-flow", cron="*/5 * * * *"),
            Flow(id=9102, project_id=902, name="p2-flow", cron="*/5 * * * *"),
            Asset(id=9201, project_id=901, type="pipeline", key="ops-a1",
                  name="p1-asset", owner="ops"),
            Asset(id=9202, project_id=902, type="pipeline", key="ops-a2",
                  name="p2-asset", owner="ops"),
        ])
        s.flush()
        s.add_all([
            Job(id=9301, flow_id=9101, status="failed", attempts=3,
                last_error="boom", finished_at=now),
            Job(id=9302, asset_id=9201, asset_type="pipeline",
                status="queued", run_at=now),
            Job(id=9303, flow_id=9102, status="failed", attempts=3,
                last_error="other"),
            Job(id=9304, asset_id=9202, asset_type="pipeline",
                status="queued"),
            Alert(id=9401, project_id=901, severity="critical", title="p1",
                  status="open"),
            Alert(id=9402, project_id=902, severity="critical", title="p2",
                  status="open"),
            HealthEvent(id=9501, flow_id=9101, kind="lag",
                        severity="warning", evidence_json={}),
        ])
        s.commit()


def test_summary_and_jobs_are_project_scoped():
    _fixture()
    with SessionLocal() as s:
        out = summary(s, 901)
        assert out["jobs"]["failed"] == 1
        assert out["jobs"]["queued"] == 1
        assert out["alerts"]["open"] == 1
        assert out["health"]["flows"] == 1
        ids = [j["id"] for j in list_jobs(s, 901)]
        assert 9301 in ids and 9302 in ids
        assert 9303 not in ids and 9304 not in ids


def test_retry_job_resets_state_and_rejects_others():
    _fixture()
    with SessionLocal() as s:
        try:
            retry_job(s, 901, 9302, "ops")
        except ValueError as e:
            assert "failed" in str(e)
        else:
            raise AssertionError("queued job must not retry")
        try:
            retry_job(s, 901, 9303, "ops")
        except ValueError:
            pass
        else:
            raise AssertionError("other-project job must not retry")
        out = retry_job(s, 901, 9301, "ops")
        assert out["status"] == "queued" and out["attempts"] == 0
        j = s.get(Job, 9301)
        assert j.locked_by is None and j.finished_at is None
        assert j.run_at is not None


def test_alert_actions_are_project_scoped():
    _fixture()
    with SessionLocal() as s:
        try:
            ack_alert(s, 901, 9402, "ops")
        except ValueError:
            pass
        else:
            raise AssertionError("other-project alert must not ack")
        ack_alert(s, 901, 9401, "ops")
        assert s.get(Alert, 9401).status == "acked"
        assert [a["id"] for a in list_alerts(s, 901)] == [9401]


def test_health_and_timeline():
    _fixture()
    with SessionLocal() as s:
        h = list_health(s, 901)
        assert h["flows"][0]["flow_id"] == 9101
        assert h["counts"]["unknown"] == 1
        assert h["events"][0]["severity"] == "warning"
        t = timeline(s, 901)
        assert any(x["kind"] in ("health", "alert") for x in t)
        assert all("p2" not in str(x) for x in t)


def test_job_limit_is_clamped():
    _fixture()
    with SessionLocal() as s:
        assert len(list_jobs(s, 901, limit=0)) == 1
        assert len(list_jobs(s, 901, limit=-1)) >= 1


def test_retry_refuses_when_target_already_queued():
    _fixture()
    with SessionLocal() as s:
        s.add(Job(id=9305, flow_id=9101, status="queued"))
        s.commit()
        try:
            retry_job(s, 901, 9301, "ops")
        except ValueError as e:
            assert "already" in str(e)
        else:
            raise AssertionError("duplicate queue entry must be rejected")
