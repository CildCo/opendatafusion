import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select

from odf.models import Alert, Asset, Job, PipelineNodeRun
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
            "created_at": _iso(job.created_at),
            "finished_at": _iso(job.finished_at),
            "last_error": job.last_error, "locked_by": job.locked_by,
            "cancel_requested": bool(job.cancel_requested),
            "retry_backoff_seconds": (job.payload_json or {}).get(
                "retry_backoff_seconds", 30),
            "priority": job.priority or 0,
            "max_duration_seconds": (job.payload_json or {}).get(
                "max_duration_seconds"),
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


def run_health(session, project_id, days=30):
    try:
        days = max(1, min(int(days or 30), 90))
    except (TypeError, ValueError):
        days = 30
    since = datetime.now(timezone.utc) - timedelta(days=days)
    assets = (session.query(Asset).filter(Asset.project_id == project_id)
              .order_by(Asset.type, Asset.name).all())
    items = []
    for asset in assets:
        jobs = (_job_query(session, project_id)
                .filter(Job.asset_id == asset.id,
                        Job.created_at >= since)
                .order_by(Job.id.desc()).limit(50).all())
        if not jobs and not asset.cron:
            continue
        finished = [job for job in jobs if job.status in ("success", "failed")]
        success = sum(1 for job in finished if job.status == "success")
        failed = len(finished) - success
        durations = []
        breaches = 0
        limit = asset.max_duration_seconds
        for job in finished:
            started = _aware(job.created_at)
            ended = _aware(job.finished_at)
            if not started or not ended:
                continue
            duration = max(0.0, (ended - started).total_seconds())
            durations.append(duration)
            if limit and duration > limit:
                breaches += 1
        success_rate = round(success * 100.0 / len(finished), 1)             if finished else None
        durations.sort()
        p95 = durations[min(len(durations) - 1,
                            max(0, math.ceil(len(durations) * 0.95) - 1))]             if durations else None
        avg = round(sum(durations) / len(durations), 1) if durations else None
        score = 100.0
        if success_rate is not None:
            score = success_rate
        if breaches and finished:
            score -= min(30.0, breaches * 100.0 / len(finished))
        last = jobs[0] if jobs else None
        items.append({
            "id": asset.id, "name": asset.name, "type": asset.type,
            "cron": asset.cron, "enabled": bool(asset.enabled),
            "priority": asset.priority or 0,
            "max_duration_seconds": asset.max_duration_seconds,
            "total": len(finished), "success": success, "failed": failed,
            "success_rate": success_rate,
            "avg_duration_seconds": avg,
            "p95_duration_seconds": round(p95, 1) if p95 is not None else None,
            "sla_breaches": breaches,
            "health_score": round(max(0.0, score), 1),
            "last_status": last.status if last else None,
            "last_run_at": _iso(last.finished_at or last.created_at)
            if last else None,
        })
    items.sort(key=lambda item: (item["health_score"],
                                 item["last_run_at"] or ""))
    return {"days": days, "items": items}


def _asset_job(asset):
    return {"max_attempts": asset.max_attempts or 3,
            "retry_backoff_seconds": asset.retry_backoff_seconds or 0,
            "priority": asset.priority or 0,
            "max_duration_seconds": asset.max_duration_seconds}


def run_policies(session, project_id):
    assets = (session.query(Asset).filter_by(project_id=project_id)
              .order_by(Asset.type, Asset.name).all())
    out = []
    for asset in assets:
        last = (session.query(Job).filter_by(asset_id=asset.id)
                .order_by(Job.id.desc()).first())
        out.append({"id": asset.id, "asset_id": asset.id,
                    "name": asset.name, "type": asset.type,
                    "cron": asset.cron, "enabled": bool(asset.enabled),
                    **_asset_job(asset),
                    "last_status": last.status if last else None,
                    "last_run_at": _iso(last.finished_at
                                        or last.created_at) if last else None})
    return out


def update_run_policy(session, project_id, asset_id, max_attempts,
                      retry_backoff_seconds, actor, priority=0,
                      max_duration_seconds=0):
    asset = session.get(Asset, asset_id)
    if not asset or asset.project_id != project_id:
        raise ValueError("asset not found")
    try:
        attempts = int(max_attempts)
        backoff = int(retry_backoff_seconds)
    except (TypeError, ValueError):
        raise ValueError("run policy values must be numbers")
    if not 1 <= attempts <= 10:
        raise ValueError("max attempts must be between 1 and 10")
    if not 0 <= backoff <= 3600:
        raise ValueError("retry backoff must be between 0 and 3600 seconds")
    try:
        priority = int(priority or 0)
        duration = int(max_duration_seconds or 0)
    except (TypeError, ValueError):
        raise ValueError("priority and duration must be numbers")
    if not 0 <= priority <= 100:
        raise ValueError("priority must be between 0 and 100")
    if not 0 <= duration <= 86400:
        raise ValueError("max duration must be between 0 and 86400 seconds")
    asset.max_attempts = attempts
    asset.retry_backoff_seconds = backoff
    asset.priority = priority
    asset.max_duration_seconds = duration or None
    session.commit()
    write_audit(session, actor, "update_run_policy", str(asset.id),
                {"max_attempts": attempts,
                 "retry_backoff_seconds": backoff, "priority": priority,
                 "max_duration_seconds": duration or None})
    session.refresh(asset)
    return {"id": asset.id, "name": asset.name, "type": asset.type,
            **_asset_job(asset)}


def job_detail(session, project_id, job_id):
    job = _job_query(session, project_id).filter(Job.id == job_id).first()
    if not job:
        raise ValueError("job not found")
    nodes = (session.query(PipelineNodeRun)
             .filter_by(job_id=job.id)
             .order_by(PipelineNodeRun.id).all())
    return {**_job_dict(session, job), "payload": job.payload_json or {},
            "nodes": [{"node_id": n.node_id, "status": n.status,
                       "in_num": n.in_num, "out_num": n.out_num,
                       "ms": n.ms, "error": n.error} for n in nodes]}


def job_compare(session, project_id, job_id):
    job = _job_query(session, project_id).filter(Job.id == job_id).first()
    if not job:
        raise ValueError("job not found")
    previous = None
    if job.asset_id:
        previous = (session.query(Job)
                    .filter(Job.asset_id == job.asset_id, Job.id < job.id,
                            Job.status.notin_(("skipped", "queued",
                                               "running")))
                    .order_by(Job.id.desc()).first())
    if not previous:
        return {"current": _job_dict(session, job), "previous": None,
                "nodes": [], "totals": None}
    previous_nodes = {n.node_id: n for n in
                      session.query(PipelineNodeRun)
                      .filter_by(job_id=previous.id).all()}
    current_nodes = (session.query(PipelineNodeRun)
                     .filter_by(job_id=job.id)
                     .order_by(PipelineNodeRun.id).all())
    nodes = []
    for node in current_nodes:
        old = previous_nodes.get(node.node_id)
        nodes.append({
            "node_id": node.node_id, "status": node.status,
            "out_num": node.out_num,
            "previous_out_num": old.out_num if old else None,
            "ms": node.ms, "previous_ms": old.ms if old else None,
            "ms_delta": node.ms - old.ms if old else None,
            "out_delta": node.out_num - old.out_num if old else None,
        })
    return {
        "current": _job_dict(session, job),
        "previous": _job_dict(session, previous),
        "nodes": nodes,
        "totals": {
            "ms": sum(n.ms or 0 for n in current_nodes),
            "previous_ms": sum(n.ms or 0 for n in previous_nodes.values()),
            "out_num": sum(n.out_num or 0 for n in current_nodes),
            "previous_out_num": sum(n.out_num or 0
                                    for n in previous_nodes.values()),
        },
    }


def schedules(session, project_id):
    from odf.services.scheduler import cron_to_trigger
    now = datetime.now(timezone.utc)
    out = []
    for asset in (session.query(Asset)
                  .filter(Asset.project_id == project_id,
                          Asset.cron.isnot(None)).all()):
        try:
            trigger = cron_to_trigger(asset.cron)
            nxt = trigger.get_next_fire_time(None, now)
            next_run = _iso(nxt)
        except Exception:
            next_run = None
        last = (session.query(Job).filter_by(asset_id=asset.id)
                .order_by(Job.id.desc()).first())
        out.append({"id": asset.id, "asset_id": asset.id,
                    "name": asset.name, "type": asset.type,
                    "cron": asset.cron, "enabled": bool(asset.enabled),
                    "next_run": next_run,
                    "last_status": last.status if last else None,
                    "last_run_at": _iso(last.finished_at
                                        or last.created_at) if last else None,
                    "last_error": last.last_error if last else None})
    return sorted(out, key=lambda row: (row["next_run"] or "", row["name"]))
