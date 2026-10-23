from datetime import datetime, timezone

from sqlalchemy import or_, select

from odf.models import (Alert, Asset, AuditLog, Flow, FlowRun, HealthEvent,
                        Job)
from odf.services.audit import write_audit
from odf.services.health import compute_health, cron_period_seconds


def _aware(dt):
    return dt if dt and dt.tzinfo else (
        dt.replace(tzinfo=timezone.utc) if dt else None)


def _iso(dt):
    dt = _aware(dt)
    return dt.isoformat() if dt else None


def _limit(value, cap):
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = cap
    return max(1, min(n, cap))


def _job_query(session, project_id):
    flow_ids = select(Flow.id).where(Flow.project_id == project_id)
    asset_ids = select(Asset.id).where(Asset.project_id == project_id)
    return session.query(Job).filter(or_(
        Job.flow_id.in_(flow_ids), Job.asset_id.in_(asset_ids)))


def _target(session, job):
    if job.flow_id:
        f = session.get(Flow, job.flow_id)
        return {"target_type": "flow", "target_id": job.flow_id,
                "target_name": f.name if f else "", "asset_type": None}
    a = session.get(Asset, job.asset_id) if job.asset_id else None
    return {"target_type": "asset", "target_id": job.asset_id,
            "target_name": a.name if a else "",
            "asset_type": job.asset_type or (a.type if a else None)}


def _job_dict(session, job):
    return {"id": job.id, "status": job.status, "attempts": job.attempts,
            "max_attempts": job.max_attempts, "run_at": _iso(job.run_at),
            "finished_at": _iso(job.finished_at),
            "last_error": job.last_error, "locked_by": job.locked_by,
            **_target(session, job)}


def list_jobs(session, project_id, status=None, limit=50):
    q = _job_query(session, project_id)
    if status:
        q = q.filter(Job.status == status)
    return [_job_dict(session, j) for j in
            q.order_by(Job.id.desc()).limit(_limit(limit, 200)).all()]


def retry_job(session, project_id, job_id, actor):
    job = _job_query(session, project_id).filter(Job.id == job_id).first()
    if not job:
        raise ValueError("job not found")
    if job.status != "failed":
        raise ValueError("only failed jobs can be retried")
    dup = session.query(Job).filter(
        Job.id != job.id, Job.status.in_(("queued", "running")))
    if job.flow_id:
        dup = dup.filter(Job.flow_id == job.flow_id)
    else:
        dup = dup.filter(Job.asset_id == job.asset_id)
    if dup.first():
        raise ValueError("target already has a queued or running job")
    old_error = job.last_error
    job.status = "queued"
    job.attempts = 0
    job.run_at = datetime.now(timezone.utc)
    job.locked_by = None
    job.locked_at = None
    job.heartbeat_at = None
    job.finished_at = None
    job.last_error = None
    session.commit()
    write_audit(session, actor, "retry_job", str(job.id),
                {"previous_error": (old_error or "")[:300]})
    session.refresh(job)
    return _job_dict(session, job)


def _flow_health(session, project_id, limit=20):
    now = datetime.now(timezone.utc)
    rows = []
    for f in session.query(Flow).filter_by(project_id=project_id).all():
        runs = (session.query(FlowRun).filter_by(flow_id=f.id)
                .order_by(FlowRun.id.desc()).limit(_limit(limit, 200)).all())
        h = compute_health(runs, now, cron_period_seconds(f.cron))
        rows.append({"flow_id": f.id, "name": f.name, **h})
    return rows


def list_health(session, project_id, event_limit=20):
    flows = _flow_health(session, project_id)
    counts = {"ok": 0, "warning": 0, "critical": 0, "unknown": 0}
    for f in flows:
        counts[f["status"]] = counts.get(f["status"], 0) + 1
    flow_ids = [f["flow_id"] for f in flows]
    events = (session.query(HealthEvent)
              .filter(HealthEvent.flow_id.in_(flow_ids))
              .order_by(HealthEvent.id.desc())
              .limit(_limit(event_limit, 200)).all()
              ) if flow_ids else []
    return {"flows": flows, "counts": counts,
            "events": [{"id": e.id, "flow_id": e.flow_id, "kind": e.kind,
                        "severity": e.severity, "evidence": e.evidence_json,
                        "at": _iso(e.at)} for e in events]}


def summary(session, project_id):
    jobs = {}
    for status in ("queued", "running", "failed", "success"):
        jobs[status] = _job_query(session, project_id) \
            .filter(Job.status == status).count()
    alerts = session.query(Alert).filter_by(project_id=project_id).all()
    by_sev = {"critical": 0, "warning": 0, "info": 0}
    for a in alerts:
        if a.status == "open":
            by_sev[a.severity] = by_sev.get(a.severity, 0) + 1
    health = list_health(session, project_id)
    assets = {}
    for a in session.query(Asset).filter_by(project_id=project_id).all():
        assets[a.type] = assets.get(a.type, 0) + 1
    failures = list_jobs(session, project_id, "failed", 5)
    return {"assets": assets, "jobs": jobs,
            "alerts": {"open": sum(by_sev.values()),
                       "by_severity": by_sev},
            "health": {"flows": len(health["flows"]), **health["counts"]},
            "recent_failures": failures}


def list_alerts(session, project_id, status=None, severity=None):
    q = session.query(Alert).filter_by(project_id=project_id)
    if status:
        q = q.filter_by(status=status)
    if severity:
        q = q.filter_by(severity=severity)
    return [{"id": a.id, "severity": a.severity, "title": a.title,
             "status": a.status, "detail": a.detail_json,
             "created_at": _iso(a.created_at),
             "acked_at": _iso(a.acked_at),
             "closed_at": _iso(a.closed_at)} for a in
            q.order_by(Alert.id.desc()).limit(200).all()]


def _alert(session, project_id, alert_id):
    a = session.get(Alert, alert_id)
    if not a or a.project_id != project_id:
        raise ValueError("alert not found")
    return a


def ack_alert(session, project_id, alert_id, actor):
    a = _alert(session, project_id, alert_id)
    if a.status != "closed":
        a.status = "acked"
        a.acked_at = datetime.now(timezone.utc)
    session.commit()
    write_audit(session, actor, "ack_alert", str(a.id), {})
    return {"id": a.id, "status": a.status}


def close_alert(session, project_id, alert_id, actor):
    a = _alert(session, project_id, alert_id)
    a.status = "closed"
    a.closed_at = datetime.now(timezone.utc)
    session.commit()
    write_audit(session, actor, "close_alert", str(a.id), {})
    return {"id": a.id, "status": a.status}


def timeline(session, project_id, limit=50):
    n = _limit(limit, 200)
    items = []
    flow_ids = select(Flow.id).where(Flow.project_id == project_id)
    for e in (session.query(HealthEvent)
              .filter(HealthEvent.flow_id.in_(flow_ids))
              .order_by(HealthEvent.id.desc()).limit(n).all()):
        items.append({"kind": "health", "severity": e.severity,
                      "title": e.kind, "target": "flow:%s" % e.flow_id,
                      "at": _iso(e.at)})
    for a in (session.query(Alert).filter_by(project_id=project_id)
              .order_by(Alert.id.desc()).limit(n).all()):
        items.append({"kind": "alert", "severity": a.severity,
                      "title": a.title, "target": "alert:%s" % a.id,
                      "at": _iso(a.created_at)})
    items.sort(key=lambda x: x["at"] or "", reverse=True)
    return items[:n]


def search_audit(session, actor=None, action=None, q=None, limit=100):
    query = session.query(AuditLog)
    if actor:
        query = query.filter(AuditLog.actor == actor)
    if action:
        query = query.filter(AuditLog.action == action)
    if q:
        like = "%%%s%%" % q
        query = query.filter(or_(AuditLog.action.ilike(like),
                                 AuditLog.target.ilike(like),
                                 AuditLog.actor.ilike(like)))
    return [{"id": r.id, "actor": r.actor, "action": r.action,
             "target": r.target, "detail": r.detail_json,
             "at": _iso(r.at)} for r in
            query.order_by(AuditLog.id.desc())
            .limit(_limit(limit, 500)).all()]
