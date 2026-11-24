import hashlib
from datetime import datetime, timedelta, timezone

from odf.models import Datasource, QueryRun
from odf.services.pagination import envelope, limits

SOURCES = {"workbench", "federated", "model", "dataset", "api", "other"}
PREVIEW_CHARS = 200
TEXT_CAP = 20000
SUMMARY_CAP = 20000


def record(session, project_id, datasource_id, actor, source, ms,
           rows=0, error=None, sql=""):
    text = (sql or "").strip()
    row = QueryRun(
        project_id=project_id,
        datasource_id=datasource_id,
        actor=actor or "",
        source=source if source in SOURCES else "other",
        status="error" if error else "ok",
        sql_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        sql_preview=text[:PREVIEW_CHARS],
        sql_text=text[:TEXT_CAP],
        rows=max(0, int(rows or 0)),
        ms=max(0, int(ms or 0)),
        error=str(error)[:500] if error else None)
    session.add(row)
    session.commit()
    return row


def _out(row, datasource_name=None):
    return {"id": row.id, "datasource_id": row.datasource_id,
            "datasource_name": datasource_name, "actor": row.actor,
            "source": row.source, "status": row.status,
            "sql_preview": row.sql_preview, "rows": row.rows, "ms": row.ms,
            "error": row.error, "created_at": row.created_at}


def list_runs(session, project_id, datasource_id=None, status=None,
              source=None, page=1, page_size=50):
    page, page_size = limits(page, page_size)
    query = session.query(QueryRun).filter_by(project_id=project_id)
    if datasource_id is not None:
        query = query.filter_by(datasource_id=datasource_id)
    if status:
        query = query.filter_by(status=status)
    if source:
        query = query.filter_by(source=source)
    total = query.count()
    rows = (query.order_by(QueryRun.id.desc())
            .offset((page - 1) * page_size).limit(page_size).all())
    names = {}
    ids = {row.datasource_id for row in rows if row.datasource_id}
    if ids:
        names = {ds.id: ds.name for ds in
                 session.query(Datasource).filter(Datasource.id.in_(ids))}
    return envelope([_out(row, names.get(row.datasource_id))
                     for row in rows], total, page, page_size)


def get_run(session, project_id, run_id):
    row = session.get(QueryRun, run_id)
    if not row or row.project_id != project_id:
        raise ValueError("query run not found")
    datasource = (session.get(Datasource, row.datasource_id)
                  if row.datasource_id else None)
    out = _out(row, datasource.name if datasource else None)
    out["sql"] = row.sql_text
    return out


def _percentile(sorted_values, fraction):
    if not sorted_values:
        return 0
    import math
    index = max(0, math.ceil(fraction * len(sorted_values)) - 1)
    return sorted_values[min(index, len(sorted_values) - 1)]


def summary(session, project_id, days=7):
    days = max(1, min(int(days or 7), 90))
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (session.query(QueryRun)
            .filter(QueryRun.project_id == project_id,
                    QueryRun.created_at >= since)
            .order_by(QueryRun.id.desc()).limit(SUMMARY_CAP).all())
    ok = [row for row in rows if row.status == "ok"]
    durations = sorted(row.ms for row in ok)
    by_source, by_datasource, daily = {}, {}, {}
    for row in rows:
        source = by_source.setdefault(
            row.source, {"source": row.source, "count": 0, "errors": 0,
                         "total_ms": 0})
        source["count"] += 1
        source["total_ms"] += row.ms
        if row.status != "ok":
            source["errors"] += 1
        key = row.datasource_id
        datasource = by_datasource.setdefault(
            key, {"datasource_id": key, "count": 0, "errors": 0,
                  "total_ms": 0})
        datasource["count"] += 1
        datasource["total_ms"] += row.ms
        if row.status != "ok":
            datasource["errors"] += 1
        day = row.created_at.date().isoformat() if row.created_at else ""
        bucket = daily.setdefault(day, {"day": day, "count": 0,
                                        "errors": 0, "total_ms": 0})
        bucket["count"] += 1
        bucket["total_ms"] += row.ms
        if row.status != "ok":
            bucket["errors"] += 1
    names = {}
    ids = {row.datasource_id for row in rows if row.datasource_id}
    if ids:
        names = {ds.id: ds.name for ds in
                 session.query(Datasource).filter(Datasource.id.in_(ids))}
    for item in by_datasource.values():
        item["datasource_name"] = names.get(item["datasource_id"])
        item["avg_ms"] = round(item["total_ms"] / item["count"]) \
            if item["count"] else 0
    for item in by_source.values():
        item["avg_ms"] = round(item["total_ms"] / item["count"]) \
            if item["count"] else 0
    slowest = sorted(rows, key=lambda row: row.ms, reverse=True)[:10]
    return {
        "days": days, "total": len(rows), "ok": len(ok),
        "errors": len(rows) - len(ok),
        "avg_ms": round(sum(durations) / len(durations)) if durations else 0,
        "p50_ms": _percentile(durations, 0.50),
        "p95_ms": _percentile(durations, 0.95),
        "by_source": sorted(by_source.values(),
                            key=lambda item: item["count"], reverse=True),
        "by_datasource": sorted(by_datasource.values(),
                                key=lambda item: item["count"],
                                reverse=True),
        "daily": [daily[key] for key in sorted(daily)],
        "slowest": [_out(row, names.get(row.datasource_id))
                    for row in slowest],
    }
