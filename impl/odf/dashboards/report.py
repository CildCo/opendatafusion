from datetime import datetime, timezone

from odf.assets.service import get_asset
from odf.dashboards.render import dashboard_csv
from odf.dashboards.service import dashboard_data
from odf.files.service import store_bytes
from odf.models import ReportSchedule
from odf.services.audit import write_audit
from odf.services.notifications import notify
from odf.services.scheduler import cron_to_trigger
from odf.webhooks.service import emit_safe


def _now():
    return datetime.now(timezone.utc)


def _aware(value):
    return value if value and value.tzinfo else (
        value.replace(tzinfo=timezone.utc) if value else None)


def _asset(session, project_id, asset_id):
    asset = get_asset(session, asset_id)
    if not asset or asset.type != "dashboard" \
            or asset.project_id != project_id:
        raise ValueError("dashboard not found")
    return asset


def _out(row):
    return {"id": row.id, "asset_id": row.asset_id, "cron": row.cron,
            "enabled": row.enabled, "created_by": row.created_by,
            "last_run_at": _aware(row.last_run_at),
            "last_status": row.last_status, "last_error": row.last_error,
            "last_file_id": row.last_file_id,
            "created_at": _aware(row.created_at)}


def schedule_for(session, project_id, asset_id):
    _asset(session, project_id, asset_id)
    row = (session.query(ReportSchedule)
           .filter_by(asset_id=asset_id, project_id=project_id).first())
    return _out(row) if row else None


def upsert_schedule(session, project_id, asset_id, cron, enabled, actor):
    asset = _asset(session, project_id, asset_id)
    if not asset.published_version_id:
        raise ValueError("dashboard is not published")
    try:
        cron_to_trigger(cron)
    except Exception:
        raise ValueError("invalid cron expression")
    row = (session.query(ReportSchedule)
           .filter_by(asset_id=asset_id, project_id=project_id).first())
    if not row:
        row = ReportSchedule(project_id=project_id, asset_id=asset_id,
                             created_by=actor)
        session.add(row)
    row.cron = cron
    row.enabled = bool(enabled)
    session.commit()
    session.refresh(row)
    write_audit(session, actor, "schedule_dashboard_report", str(asset_id),
                {"cron": cron, "enabled": bool(enabled)})
    return _out(row)


def delete_schedule(session, project_id, asset_id, actor):
    _asset(session, project_id, asset_id)
    row = (session.query(ReportSchedule)
           .filter_by(asset_id=asset_id, project_id=project_id).first())
    if not row:
        raise ValueError("report schedule not found")
    session.delete(row)
    session.commit()
    write_audit(session, actor, "delete_dashboard_report", str(asset_id), {})
    return {"deleted": True}


def due_schedules(session, now):
    out = []
    for row in (session.query(ReportSchedule)
                .filter(ReportSchedule.enabled.is_(True)).all()):
        try:
            trigger = cron_to_trigger(row.cron)
        except Exception:
            continue
        base = _aware(row.last_run_at or row.created_at)
        following = trigger.get_next_fire_time(None, base)
        if following is not None and _aware(following) <= now:
            out.append(row)
    return out


def _run(session, row, actor):
    asset = _asset(session, row.project_id, row.asset_id)
    if not asset.published_version_id:
        raise ValueError("dashboard is not published")
    result = dashboard_data(session, asset.id, None, None, 10000,
                            published_only=True, role="viewer")
    content, widgets = dashboard_csv(result)
    stamp = _now().strftime("%Y%m%d-%H%M")
    name = "%s-report-%s.csv" % (asset.key, stamp)
    stored = store_bytes(session, row.project_id, name, "text/csv",
                         content.encode("utf-8"), actor)
    row.last_file_id = stored["id"]
    emit_safe(session, row.project_id, "report.ready", {
        "dashboard_id": asset.id, "dashboard_name": asset.name,
        "file_id": stored["id"], "file_name": stored["name"],
        "widgets": widgets})
    notify(session, row.project_id, "report",
           "报表已生成：%s" % asset.name,
           "文件：%s" % stored["name"],
           "/dashboards/%d/run" % asset.id)
    write_audit(session, actor, "run_dashboard_report", str(asset.id),
                {"schedule_id": row.id, "file_id": stored["id"]})
    return {"schedule_id": row.id, "dashboard_id": asset.id,
            "file_id": stored["id"], "file_name": stored["name"],
            "widgets": widgets}


def run_report(session, schedule_id, actor):
    row = session.get(ReportSchedule, schedule_id)
    if not row:
        raise ValueError("report schedule not found")
    try:
        out = _run(session, row, actor)
    except Exception as error:
        row.last_run_at = _now()
        row.last_status = "failed"
        row.last_error = str(error)[:500]
        session.commit()
        raise
    row.last_run_at = _now()
    row.last_status = "ok"
    row.last_error = None
    session.commit()
    return out
