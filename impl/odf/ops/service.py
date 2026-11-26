from datetime import datetime, timezone

from sqlalchemy import or_, select

from odf.models import Alert, Asset, Job
from odf.services.audit import write_audit


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
    asset_ids = select(Asset.id).where(Asset.project_id == project_id)
    return session.query(Job).filter(or_(
        Job.asset_id.in_(asset_ids), Job.project_id == project_id))


def _target(session, job):
    if job.asset_type == "lakehouse_maintenance":
        return {"target_type": "lakehouse",
                "target_id": job.project_id,
                "target_name": "lakehouse maintenance",
                "asset_type": job.asset_type}
    a = session.get(Asset, job.asset_id) if job.asset_id else None
    return {"target_type": "asset", "target_id": job.asset_id,
            "target_name": a.name if a else "",
            "asset_type": job.asset_type or (a.type if a else None)}


def _job_dict(session, job):
    return {"id": job.id, "status": job.status, "attempts": job.attempts,
            "max_attempts": job.max_attempts, "run_at": _iso(job.run_at),
            "finished_at": _iso(job.finished_at),
            "last_error": job.last_error, "locked_by": job.locked_by,
            "cancel_requested": bool(job.cancel_requested),
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
        Job.id != job.id, Job.status.in_(("queued", "running")),
        Job.asset_id == job.asset_id)
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


def cancel_job(session, project_id, job_id, actor):
    from odf.services.jobs import cancel_job as cancel
    job = cancel(session, project_id, job_id)
    write_audit(session, actor, "cancel_job", str(job.id), {})
    session.refresh(job)
    return _job_dict(session, job)


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
    assets = {}
    for a in session.query(Asset).filter_by(project_id=project_id).all():
        assets[a.type] = assets.get(a.type, 0) + 1
    failures = list_jobs(session, project_id, "failed", 5)
    return {"assets": assets, "jobs": jobs,
            "alerts": {"open": sum(by_sev.values()),
                       "by_severity": by_sev},
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
        a.acked_by = actor
    session.commit()
    write_audit(session, actor, "ack_alert", str(a.id), {})
    return {"id": a.id, "status": a.status}


def close_alert(session, project_id, alert_id, actor):
    a = _alert(session, project_id, alert_id)
    a.status = "closed"
    a.closed_at = datetime.now(timezone.utc)
    a.closed_by = actor
    session.commit()
    write_audit(session, actor, "close_alert", str(a.id), {})
    return {"id": a.id, "status": a.status}


def timeline(session, project_id, limit=50):
    n = _limit(limit, 200)
    items = []
    for a in (session.query(Alert).filter_by(project_id=project_id)
              .order_by(Alert.id.desc()).limit(n).all()):
        items.append({"kind": "alert", "severity": a.severity,
                      "title": a.title, "target": "alert:%s" % a.id,
                      "at": _iso(a.created_at)})
    items.sort(key=lambda x: x["at"] or "", reverse=True)
    return items[:n]


def search_audit(session, actor=None, action=None, q=None, limit=100):
    from odf.services.audit import list_audit
    return list_audit(session, limit, actor, action, q)


def dead_letters(session, project_id, asset_type=None, since=None,
                 limit=100):
    q = _job_query(session, project_id).filter(Job.status == "failed")
    if asset_type:
        q = q.filter(Job.asset_type == asset_type)
    if since is not None:
        q = q.filter(Job.finished_at >= since)
    return [_job_dict(session, j) for j in
            q.order_by(Job.finished_at.desc(), Job.id.desc())
            .limit(_limit(limit, 500)).all()]


def replay_jobs(session, project_id, job_ids, actor):
    if not isinstance(job_ids, list) or not job_ids:
        raise ValueError("job_ids must be a non-empty list")
    if len(job_ids) > 100:
        raise ValueError("at most 100 jobs can be replayed at once")
    replayed, skipped = [], []
    reasons = {
        "job not found": "job not found",
        "only failed jobs can be retried": "job is not failed",
        "target already has a queued or running job":
            "target already has a queued or running job",
    }
    for job_id in job_ids:
        try:
            replayed.append(retry_job(session, project_id, int(job_id),
                                      actor)["id"])
        except ValueError as error:
            reason = reasons.get(str(error).strip(), "replay failed")
            skipped.append({"id": job_id, "reason": reason})
        except TypeError:
            skipped.append({"id": job_id, "reason": "invalid job id"})
    write_audit(session, actor, "replay_dead_letters", "ops",
                {"replayed": replayed, "skipped": skipped})
    return {"replayed": replayed, "skipped": skipped}


def run_matrix(session, project_id, days=7):
    from datetime import datetime, timedelta, timezone
    days = max(1, min(int(days if days is not None else 7), 30))
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days - 1)
    since = since.replace(hour=0, minute=0, second=0, microsecond=0)
    job_rows = (_job_query(session, project_id)
                .filter(Job.created_at >= since)
                .order_by(Job.id).limit(5000).all())
    day_keys = [(since + timedelta(days=index)).date().isoformat()
                for index in range(days)]
    assets = {}
    priority = ["failed", "running", "queued", "success", "skipped",
                "cancelled"]
    for job in job_rows:
        target = _target(session, job)
        key = (target.get("asset_type") or "job",
               target.get("target_id"))
        row = assets.setdefault(key, {
            "asset_id": target.get("target_id"),
            "asset_type": target.get("asset_type") or "job",
            "name": target.get("target_name") or "-",
            "cells": {}, "total": 0})
        stamp = job.created_at.date().isoformat() if job.created_at else ""
        cell = row["cells"].setdefault(stamp, {"count": 0, "statuses": {}})
        cell["count"] += 1
        cell["statuses"][job.status] = \
            cell["statuses"].get(job.status, 0) + 1
        row["total"] += 1
    rows = []
    for row in assets.values():
        cells = {}
        for day, cell in row["cells"].items():
            counts = cell["statuses"]
            status = next((name for name in priority if counts.get(name)),
                          "success")
            cells[day] = {"count": cell["count"], "status": status}
        rows.append({**row, "cells": cells})
    rows.sort(key=lambda item: item["name"].lower())
    return {"days": day_keys, "rows": rows[:50],
            "truncated": len(assets) > 50}
