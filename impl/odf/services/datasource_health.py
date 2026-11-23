from datetime import datetime, timezone

from odf.models import DatasourceHealth


def record(session, datasource_id, action, ok, error="", duration_ms=0):
    row = DatasourceHealth(datasource_id=datasource_id, action=action,
                           status="ok" if ok else "failed",
                           error=(error or "")[:1000] or None,
                           duration_ms=max(0, int(duration_ms)))
    session.add(row)
    session.commit()
    return row


def recent(session, datasource_id, limit=20):
    rows = (session.query(DatasourceHealth)
            .filter_by(datasource_id=datasource_id)
            .order_by(DatasourceHealth.id.desc()).limit(limit).all())
    return [{"id": r.id, "action": r.action, "status": r.status,
             "error": r.error, "duration_ms": r.duration_ms,
             "at": r.at.isoformat() if r.at else None} for r in rows]


def due_syncs(session, now=None):
    from odf.models import Datasource
    now = now or datetime.now(timezone.utc)
    rows = (session.query(Datasource)
            .filter(Datasource.auto_sync_minutes > 0).all())
    out = []
    for ds in rows:
        if not ds.last_sync_at:
            out.append(ds)
            continue
        last = ds.last_sync_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if (now - last).total_seconds() >= ds.auto_sync_minutes * 60:
            out.append(ds)
    return out
