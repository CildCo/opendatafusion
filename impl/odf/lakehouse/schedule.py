from datetime import datetime, timezone

from sqlalchemy import or_

from odf.lakehouse.maintenance import maintain
from odf.lakehouse.service import list_tables, project_schema
from odf.models import Datasource, Job, LakehouseMaintenance
from odf.services.scheduler import cron_to_trigger, project_timezone
from odf.trino.client import client_for_datasource


def _now():
    return datetime.now(timezone.utc)


def _aware(value):
    return value if value and value.tzinfo else (
        value.replace(tzinfo=timezone.utc) if value else None)


def _out(row):
    return {"id": row.id, "datasource_id": row.datasource_id,
            "schema_name": row.schema_name, "table_name": row.table_name,
            "cron": row.cron, "enabled": row.enabled,
            "optimize": row.optimize,
            "expire_snapshots": row.expire_snapshots,
            "retention": row.retention,
            "file_size_threshold": row.file_size_threshold,
            "last_run_at": _aware(row.last_run_at),
            "last_status": row.last_status, "last_error": row.last_error}


def _trino(session, project_id, datasource_id):
    ds = session.get(Datasource, datasource_id)
    if not ds or ds.project_id != project_id:
        raise ValueError("datasource not found")
    if ds.kind != "trino":
        raise ValueError("lakehouse maintenance requires a trino datasource")
    return ds


def _schema(ds, schema):
    return schema or getattr(client_for_datasource(ds), "schema", "") or ""


def list_schedules(session, project_id, datasource_id=None):
    q = session.query(LakehouseMaintenance).filter_by(
        project_id=project_id)
    if datasource_id:
        q = q.filter_by(datasource_id=datasource_id)
    return [_out(row) for row in q.order_by(LakehouseMaintenance.id).all()]


def upsert(session, project_id, datasource_id, schema_name, table_name,
           cron, enabled, optimize, expire_snapshots, retention,
           file_size_threshold, actor):
    ds = _trino(session, project_id, datasource_id)
    from odf.lakehouse.maintenance import _retention, _size
    _retention(retention)
    _size(file_size_threshold)
    try:
        cron_to_trigger(cron)
    except Exception:
        raise ValueError("invalid cron expression")
    schema = schema_name or _schema(ds, "")
    if not schema:
        raise ValueError("schema is required")
    table = table_name or ""
    row = (session.query(LakehouseMaintenance)
           .filter_by(project_id=project_id, datasource_id=datasource_id,
                      schema_name=schema, table_name=table).first())
    if not row:
        row = LakehouseMaintenance(project_id=project_id,
                                   datasource_id=datasource_id,
                                   schema_name=schema, table_name=table,
                                   created_by=actor)
        session.add(row)
    row.cron = cron
    row.enabled = bool(enabled)
    row.optimize = bool(optimize)
    row.expire_snapshots = bool(expire_snapshots)
    row.retention = retention
    row.file_size_threshold = file_size_threshold
    session.commit()
    session.refresh(row)
    return _out(row)


def delete(session, project_id, schedule_id):
    row = session.get(LakehouseMaintenance, schedule_id)
    if not row or row.project_id != project_id:
        raise ValueError("maintenance schedule not found")
    session.delete(row)
    session.commit()
    return {"deleted": True}


def due(session, now):
    out = []
    for row in (session.query(LakehouseMaintenance)
                .filter(LakehouseMaintenance.enabled.is_(True)).all()):
        try:
            trigger = cron_to_trigger(
                row.cron, project_timezone(session, row.project_id))
        except Exception:
            continue
        base = _aware(row.last_run_at or row.created_at)
        following = trigger.get_next_fire_time(None, base)
        if following is not None and _aware(following) <= now:
            out.append(row)
    return out


def enqueue(session, row):
    pending = (session.query(Job)
               .filter(Job.asset_type == "lakehouse_maintenance",
                       Job.status.in_(("queued", "running"))).all())
    for job in pending:
        if (job.payload_json or {}).get("schedule_id") == row.id:
            return job
    job = Job(project_id=row.project_id,
              asset_type="lakehouse_maintenance", status="queued",
              run_at=_now(), attempts=0,
              payload_json={"schedule_id": row.id})
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def run_schedule(session, schedule_id, actor="scheduler"):
    row = session.get(LakehouseMaintenance, schedule_id)
    if not row:
        raise ValueError("maintenance schedule not found")
    ds = _trino(session, row.project_id, row.datasource_id)
    client = client_for_datasource(ds)
    schema = row.schema_name or _schema(ds, "")
    tables = [row.table_name] if row.table_name else None
    try:
        results = maintain(client, schema, tables, row.optimize,
                           row.expire_snapshots, row.retention,
                           row.file_size_threshold)
        failed = [r for r in results
                  if r.get("optimize", "").startswith("failed")
                  or r.get("expire", "").startswith("failed")]
        row.last_run_at = _now()
        row.last_status = "failed" if failed else "ok"
        row.last_error = None
        session.commit()
        if failed:
            from odf.services.alerts import raise_alert
            raise_alert(session, row.project_id, "warning",
                        "lakehouse maintenance failed: %s.%s" % (
                            schema, row.table_name or "*"),
                        {"schedule_id": row.id, "results": failed})
        return {"schedule_id": row.id, "schema": schema,
                "results": results, "status": row.last_status}
    except Exception as error:
        row.last_run_at = _now()
        row.last_status = "failed"
        row.last_error = str(error)[:500]
        session.commit()
        raise
