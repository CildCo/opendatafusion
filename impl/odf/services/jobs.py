import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from odf.models import Flow, Job


def _now():
    return datetime.now(timezone.utc)


def _aware(dt):
    return dt if dt and dt.tzinfo else (dt.replace(tzinfo=timezone.utc) if dt else None)


def enqueue(session, flow_id: int, run_at: datetime | None = None) -> Job:
    existing = (session.query(Job)
                .filter(Job.flow_id == flow_id,
                        Job.status.in_(("queued", "running")))
                .first())
    if existing:
        return existing
    job = Job(flow_id=flow_id, status="queued",
              run_at=run_at or _now(), attempts=0)
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


def complete(session, job_id: int, success: bool,
             error: str | None = None) -> Job:
    job = session.get(Job, job_id)
    if not job:
        raise ValueError("job not found")
    if success:
        job.status = "success"
        job.finished_at = _now()
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
        if job.flow_id:
            f = session.get(Flow, job.flow_id)
            project_id = f.project_id if f else None
        elif job.asset_id:
            from odf.models import Asset
            a = session.get(Asset, job.asset_id)
            project_id = a.project_id if a else None
        if project_id is not None:
            from odf.webhooks.service import emit_safe
            emit_safe(session, project_id, "job.failed",
                      {"job_id": job.id, "flow_id": job.flow_id,
                       "asset_id": job.asset_id})
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
    if job.asset_type == "pipeline":
        from odf.pipeline.runner import execute_pipeline
        batches = MAX_DRAIN_BATCHES if _pipeline_drainable(
            session, job.asset_id) else 1
        for _ in range(batches):
            result = execute_pipeline(session, job.asset_id, job.id,
                                      worker_id)
            if not isinstance(result, dict) or not result:
                break
            if (result.get("exhausted")
                    or result.get("source_rows", 0) == 0):
                break
        complete(session, job.id, True)
        return
    if job.asset_type == "pipeline_backfill":
        from odf.pipeline.runner import execute_backfill
        payload = job.payload_json or {}
        execute_backfill(session, job.asset_id,
                         payload.get("start_cursor"),
                         end_cursor=payload.get("end_cursor"),
                         batch=payload.get("batch"),
                         max_batches=payload.get("max_batches", 100),
                         actor=worker_id, job_id=job.id,
                         resume_cursors=payload.get("resume_cursors"))
        complete(session, job.id, True)
        return
    from odf.workers.etl import run_flow
    run = run_flow(session, job.flow_id, worker_id)
    complete(session, job.id, run.status == 2,
             None if run.status == 2 else "flow run failed")


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


def flow_tick(session, now=None):
    from odf.services.scheduler import cron_to_trigger
    now = now or _now()
    for f in session.query(Flow).filter_by(status=1).all():
        if not f.cron:
            continue
        last = (session.query(Job).filter_by(flow_id=f.id)
                .order_by(Job.id.desc()).first())
        trigger = cron_to_trigger(f.cron)
        if last:
            next_at = trigger.get_next_fire_time(None, _aware(last.created_at))
            if next_at and _aware(next_at) > now:
                continue
        enqueue(session, f.id)


def scheduler_tick(session, now=None):
    from odf.models import Asset
    from odf.webhooks.service import deliver_due
    from odf.services.scheduler import cron_to_trigger
    now = now or _now()
    flow_tick(session, now)
    for a in (session.query(Asset)
              .filter(Asset.type == "pipeline", Asset.enabled == True,  # noqa: E712
                      Asset.published_version_id.isnot(None)).all()):
        if not a.cron:
            continue
        last = (session.query(Job)
                .filter(Job.asset_id == a.id,
                        Job.asset_type == "pipeline")
                .order_by(Job.id.desc()).first())
        try:
            trig = cron_to_trigger(a.cron)
        except Exception:
            continue
        if last:
            nxt = trig.get_next_fire_time(None, _aware(last.created_at))
            if nxt and _aware(nxt) > now:
                continue
        enqueue_asset(session, a.id, "pipeline")
    try:
        deliver_due(session)
    except Exception:
        pass


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
