import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from odf.models import Job


def _now():
    return datetime.now(timezone.utc)


def _aware(dt):
    return dt if dt and dt.tzinfo else (dt.replace(tzinfo=timezone.utc) if dt else None)


def enqueue_skipped(session, reason: str,
                    asset_id: int | None = None,
                    asset_type: str | None = None) -> Job:
    job = Job(asset_id=asset_id, asset_type=asset_type,
              status="skipped", run_at=_now(), attempts=0,
              payload_json={}, last_error=(reason or "")[:500],
              finished_at=_now())
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def claim(session, worker_id: str) -> Job | None:
    if session.bind.dialect.name == "postgresql":
        row = session.execute(text(
            "select id from job where status='queued' and run_at <= now() "
            "order by run_at for update skip locked limit 1")).first()
        if not row:
            return None
        job = session.get(Job, row[0])
    else:
        job = (session.query(Job)
               .filter(Job.status == "queued", Job.run_at <= _now())
               .order_by(Job.run_at).first())
        if not job:
            return None
    job.status = "running"
    job.locked_by = worker_id
    job.locked_at = _now()
    job.heartbeat_at = _now()
    session.commit()
    return job


def heartbeat(session, job_id: int, worker_id: str) -> None:
    job = session.get(Job, job_id)
    if job and job.locked_by == worker_id and job.status == "running":
        job.heartbeat_at = _now()
        session.commit()


def _job_project(session, job):
    from odf.models import Asset
    if job.project_id:
        return job.project_id
    if job.asset_id:
        asset = session.get(Asset, job.asset_id)
        return asset.project_id if asset else None
    return None


def cancel_job(session, project_id: int, job_id: int) -> Job:
    job = session.get(Job, job_id)
    if not job or _job_project(session, job) != project_id:
        raise ValueError("job not found")
    if job.status in ("success", "failed", "cancelled", "skipped"):
        return job
    job.cancel_requested = True
    if job.status == "queued":
        job.status = "cancelled"
        job.finished_at = _now()
        job.locked_by = None
        job.cancel_requested = False
    session.commit()
    from odf.services.notifications import notify
    notify(session, project_id, "job", "任务已请求取消 #%d" % job.id,
           "运行中的任务会在当前批次结束后停止", "/ops")
    return job


def complete(session, job_id: int, success: bool,
             error: str | None = None) -> Job:
    job = session.get(Job, job_id)
    if not job:
        raise ValueError("job not found")
    if success:
        job.status = "success"
        job.finished_at = _now()
    elif job.cancel_requested:
        job.status = "cancelled"
        job.finished_at = _now()
        job.locked_by = None
        job.locked_at = None
        job.cancel_requested = False
    else:
        job.attempts += 1
        job.last_error = error
        job.locked_by = None
        job.locked_at = None
        if job.attempts < job.max_attempts:
            job.status = "queued"
            job.run_at = _now() + timedelta(seconds=30 * job.attempts)
        else:
            job.status = "failed"
            job.finished_at = _now()
    session.commit()
    from odf.api.metrics import inc
    inc("jobs_total", status=job.status)
    if not success and job.status == "failed":
        project_id = None
        if job.asset_id:
            from odf.models import Asset
            a = session.get(Asset, job.asset_id)
            project_id = a.project_id if a else None
        if project_id is not None:
            from odf.webhooks.service import emit_safe
            emit_safe(session, project_id, "job.failed",
                      {"job_id": job.id, "asset_id": job.asset_id})
            from odf.services.notifications import notify
            notify(session, project_id, "job",
                   "任务失败 #%d" % job.id,
                   (job.last_error or "")[:300], "/ops")
    return job


def requeue_stale(session, timeout_s: int = 300) -> int:
    cutoff = _now() - timedelta(seconds=timeout_s)
    rows = (session.query(Job)
            .filter(Job.status == "running",
                    Job.heartbeat_at != None,  # noqa: E711
                    Job.heartbeat_at < cutoff).all())
    for j in rows:
        j.status = "queued"
        j.attempts += 1
        j.locked_by = None
        j.locked_at = None
        j.last_error = "worker heartbeat timeout"
    session.commit()
    return len(rows)


def enqueue_asset(session, asset_id, asset_type="pipeline", payload=None):
    from odf.models import Asset
    from odf.services.quota import check_job
    asset = session.get(Asset, asset_id)
    if asset:
        check_job(session, asset.project_id)
    existing = (session.query(Job)
                .filter(Job.asset_id == asset_id, Job.asset_type == asset_type,
                        Job.status.in_(("queued", "running"))).first())
    if existing:
        if asset_type == "pipeline_backfill" and                 (existing.payload_json or {}) != (payload or {}):
            raise ValueError("another backfill is already queued")
        return existing
    job = Job(asset_id=asset_id, asset_type=asset_type, status="queued",
              run_at=_now(), attempts=0, payload_json=payload or {})
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


MAX_DRAIN_BATCHES = 100


def _pipeline_drainable(session, asset_id: int) -> bool:
    from odf.models import Asset, AssetVersion
    asset = session.get(Asset, asset_id)
    if not asset or not asset.published_version_id:
        return False
    version = session.get(AssetVersion, asset.published_version_id)
    if not version:
        return False
    sources = [n for n in (version.content_json or {}).get("nodes") or []
               if n.get("type") == "source"]
    return bool(sources) and all(
        (n.get("config") or {}).get("cursor_column") for n in sources)


def process_job(session, job, worker_id):
    if job.cancel_requested:
        complete(session, job.id, False, "cancelled by user")
        return
    if job.asset_type in ("model", "lakehouse_maintenance"):
        from odf.services.limits import job_datasource, job_slot_ok
        datasource_id = job_datasource(session, job)
        if datasource_id and not job_slot_ok(session, datasource_id,
                                             job.id):
            payload = dict(job.payload_json or {})
            waits = int(payload.get("slot_waits") or 0) + 1
            payload["slot_waits"] = waits
            job.payload_json = payload
            if waits > 120:
                job.status = "failed"
                job.finished_at = _now()
                job.last_error = "datasource concurrency limit reached"
                job.locked_by = None
                job.locked_at = None
                job.heartbeat_at = None
                session.commit()
                return
            job.status = "queued"
            job.locked_by = None
            job.locked_at = None
            job.heartbeat_at = None
            job.run_at = _now() + timedelta(seconds=30)
            session.commit()
            return
    if job.asset_type == "pipeline":
        from odf.lineage import openlineage
        from odf.pipeline.runner import execute_pipeline
        openlineage.emit(session, "START", job)
        try:
            batches = MAX_DRAIN_BATCHES if _pipeline_drainable(
                session, job.asset_id) else 1
            for _ in range(batches):
                result = execute_pipeline(session, job.asset_id, job.id,
                                          worker_id)
                if not isinstance(result, dict) or not result:
                    break
                session.refresh(job)
                if job.cancel_requested:
                    complete(session, job.id, False, "cancelled by user")
                    return
                if (result.get("exhausted")
                        or result.get("source_rows", 0) == 0):
                    break
        except Exception as error:
            openlineage.emit(session, "FAIL", job, error)
            raise
        complete(session, job.id, True)
        openlineage.emit(session, "COMPLETE", job)
        return
    if job.asset_type == "pipeline_backfill":
        from odf.lineage import openlineage
        from odf.pipeline.runner import execute_backfill
        payload = job.payload_json or {}
        openlineage.emit(session, "START", job)
        try:
            execute_backfill(session, job.asset_id,
                             payload.get("start_cursor"),
                             end_cursor=payload.get("end_cursor"),
                             batch=payload.get("batch"),
                             max_batches=payload.get("max_batches", 100),
                             actor=worker_id, job_id=job.id,
                             resume_cursors=payload.get("resume_cursors"))
        except Exception as error:
            openlineage.emit(session, "FAIL", job, error)
            raise
        complete(session, job.id, True)
        openlineage.emit(session, "COMPLETE", job)
        return
    if job.asset_type == "model":
        from odf.transform.service import materialize_model
        materialize_model(session, job.asset_id, job)
        complete(session, job.id, True)
        return
    if job.asset_type == "lakehouse_maintenance":
        from odf.lakehouse.schedule import run_schedule
        payload = job.payload_json or {}
        run_schedule(session, payload.get("schedule_id"), worker_id)
        complete(session, job.id, True)
        return
    if job.asset_type == "contract":
        from odf.models import Asset
        from odf.services.contracts import check_asset, save_check
        asset = session.get(Asset, job.asset_id) if job.asset_id else None
        if not asset:
            raise ValueError("contract asset not found")
        result = check_asset(session, asset.project_id, asset.id)
        save_check(session, asset, result)
        if not result["ok"]:
            failed = ", ".join(
                item["column"] for item in result["issues"]
                if item["kind"] == "missing") or "schema mismatch"
            raise ValueError("data contract check failed: %s" % failed)
        complete(session, job.id, True)
        return
    if job.asset_type == "dashboard_report":
        from odf.dashboards.report import run_report
        payload = job.payload_json or {}
        run_report(session, payload.get("schedule_id"), worker_id)
        complete(session, job.id, True)
        return
    raise ValueError("unsupported job type: %s" % (job.asset_type or ""))


def tick(session, worker_id):
    requeue_stale(session)
    try:
        from odf.services.engine_jobs import sync_due
        sync_due(session, 20)
    except Exception:
        session.rollback()
    job = claim(session, worker_id)
    if not job:
        return None
    try:
        process_job(session, job, worker_id)
    except Exception as e:
        complete(session, job.id, False, str(e))
    return job


def worker_loop(worker_id: str, poll_s: int = 2) -> None:
    from odf.db import SessionLocal
    while True:
        with SessionLocal() as s:
            job = tick(s, worker_id)
        if not job:
            time.sleep(poll_s)


def scheduler_tick(session, now=None):
    from odf.models import Asset
    from odf.webhooks.service import deliver_due
    from odf.services.scheduler import cron_to_trigger
    now = now or _now()
    for a in (session.query(Asset)
              .filter(Asset.type.in_(("pipeline", "model")),
                      Asset.enabled == True,  # noqa: E712
                      Asset.published_version_id.isnot(None)).all()):
        if not a.cron:
            continue
        last = (session.query(Job)
                .filter(Job.asset_id == a.id,
                        Job.asset_type == a.type)
                .order_by(Job.id.desc()).first())
        try:
            trig = cron_to_trigger(a.cron)
        except Exception:
            continue
        if last:
            nxt = trig.get_next_fire_time(None, _aware(last.created_at))
            if nxt and _aware(nxt) > now:
                continue
        from odf.services.dependencies import dependencies_satisfied
        state = dependencies_satisfied(session, a.project_id, a.type,
                                       a.id, now=now)
        if not state["satisfied"]:
            enqueue_skipped(session, "waiting for upstream: " + ", ".join(
                item["name"] for item in state["blocked"]),
                asset_id=a.id, asset_type=a.type)
            continue
        enqueue_asset(session, a.id, a.type)
    try:
        deliver_due(session)
    except Exception:
        pass
    _auto_sync_datasources(session, now)
    _scheduled_quality(session, now)
    _scheduled_reports(session, now)
    _lakehouse_schedules(session, now)
    _contract_schedules(session, now)
    _catalog_sync(session)
    try:
        from odf.services.retention import run_daily
        run_daily(session, now)
    except Exception:
        pass
    try:
        from odf.services.audit_ops import maintenance
        maintenance(session, now)
    except Exception:
        pass


def _auto_sync_datasources(session, now):
    from odf.connectors.registry import supports
    from odf.services.datasource_health import due_syncs, record
    from odf.services.metadata import sync_datasource
    from time import monotonic
    try:
        due = due_syncs(session, now)
    except Exception:
        return
    for ds in due:
        if not supports(ds.kind, "metadata"):
            continue
        ds.last_sync_at = now
        ds.last_sync_status = "running"
        session.commit()
        started = monotonic()
        try:
            sync_datasource(session, ds.id)
            ds = session.get(type(ds), ds.id)
            ds.last_sync_status = "ok"
            session.commit()
            record(session, ds.id, "auto_sync", True, "",
                   (monotonic() - started) * 1000)
        except Exception as error:
            session.rollback()
            ds = session.get(type(ds), ds.id)
            if ds:
                ds.last_sync_status = "failed"
                session.commit()
                record(session, ds.id, "auto_sync", False, str(error),
                       (monotonic() - started) * 1000)


def _scheduled_quality(session, now):
    from odf.models import QualityRule
    from odf.services.alerts import raise_alert
    from odf.services.quality import run_rule
    from odf.services.scheduler import cron_to_trigger
    rules = (session.query(QualityRule)
             .filter(QualityRule.enabled.is_(True),
                     QualityRule.schedule_cron.isnot(None)).all())
    for rule in rules:
        try:
            trigger = cron_to_trigger(rule.schedule_cron)
        except Exception:
            continue
        last = rule.last_run_at
        if last is not None:
            if last.tzinfo is None:
                last = last.replace(tzinfo=now.tzinfo)
            nxt = trigger.get_next_fire_time(None, last)
            if nxt is not None and nxt > now:
                continue
        rule.last_run_at = now
        session.commit()
        try:
            result = run_rule(session, rule.id)
        except Exception as error:
            result = None
            session.rollback()
            if rule.alert_on_fail:
                raise_alert(session, rule.project_id, "warning",
                            "quality check error: %s" % rule.name,
                            {"rule_id": rule.id, "error": str(error)[:300]})
            continue
        if result is not None and result.status != "pass" and rule.alert_on_fail:
            raise_alert(session, rule.project_id, "warning",
                        "quality check failed: %s" % rule.name,
                        {"rule_id": rule.id, "status": result.status,
                         "detail": result.detail_json})
        from odf.services.quality import check_sla
        try:
            check_sla(session, rule)
        except Exception:
            pass


def _lakehouse_schedules(session, now):
    try:
        from odf.lakehouse.schedule import due, enqueue
        for row in due(session, now):
            enqueue(session, row)
    except Exception:
        pass


def _contract_schedules(session, now):
    try:
        from odf.services.contracts import due_schedules
        for asset in due_schedules(session, now):
            enqueue_asset(session, asset.id, "contract")
    except Exception:
        pass


def _catalog_sync(session):
    try:
        from odf.lineage import catalog_sync
        if catalog_sync.due(session):
            catalog_sync.push(session)
    except Exception:
        pass


def _scheduled_reports(session, now):
    from odf.dashboards.report import due_schedules
    try:
        due = due_schedules(session, now)
    except Exception:
        return
    for row in due:
        enqueue_asset(session, row.asset_id, "dashboard_report",
                      {"schedule_id": row.id})


def scheduler_loop(poll_s: int = 5) -> None:
    from odf.db import SessionLocal
    while True:
        with SessionLocal() as s:
            scheduler_tick(s)
        time.sleep(poll_s)


def scheduler_main() -> None:
    from odf.db import engine
    if engine.dialect.name == "postgresql":
        conn = engine.connect()
        got = conn.execute(text("select pg_try_advisory_lock(999999)")).scalar()
        if not got:
            conn.close()
            raise SystemExit("another scheduler is already leader")
        try:
            scheduler_loop()
        finally:
            conn.close()
    else:
        scheduler_loop()
