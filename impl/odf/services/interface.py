import re
import uuid

from sqlalchemy import create_engine, text

from odf.models import AuditLog, Datasource, Interface
from odf.services.datasource import connect_args_for, get_dsn, prepare_connection
from odf.settings import get_settings


def render_sql(sql: str, params: dict) -> tuple[str, dict]:
    binds = {}

    def repl(m):
        k = m.group(1)
        binds[k] = params[k]
        return ":" + k

    return re.sub(r"\$\{(\w+)\}", repl, sql), binds


def create_interface(session, project_id, datasource_id, name, sql_text, params):
    iface = Interface(project_id=project_id, datasource_id=datasource_id,
                      interface_key=uuid.uuid4().hex, name=name,
                      sql_text=sql_text, params_json=params, status=0)
    session.add(iface)
    session.commit()
    session.refresh(iface)
    return iface


def publish_interface(session, interface_id, actor="system"):
    iface = session.get(Interface, interface_id)
    iface.status = 1
    session.add(AuditLog(actor=actor, action="publish_interface",
                         target=str(interface_id), detail_json={}))
    session.commit()
    return iface


def execute_interface(session, interface_id, params, timeout_s=None,
                      max_rows=None):
    s = get_settings()
    iface = session.get(Interface, interface_id)
    if iface.status != 1:
        raise PermissionError("interface not published")
    ds = session.get(Datasource, iface.datasource_id)
    from odf.connectors.registry import supports
    if not supports(ds.kind, "query"):
        raise ValueError("%s is a pipeline connector; interfaces are not "
                         "supported" % ds.kind)
    from odf.services.masking import datasource_has_policies
    if datasource_has_policies(session, ds.id):
        raise PermissionError(
            "interfaces are disabled for governed datasources")
    sql, binds = render_sql(iface.sql_text, params)
    limit = max_rows or s.query_max_rows
    if ds.kind in ("file", "clickhouse"):
        from odf import clickhouse, filesource
        runner = filesource if ds.kind == "file" else clickhouse
        result = runner.execute(ds, sql, binds, limit)["rows"]
    else:
        dsn = get_dsn(ds)
        engine = create_engine(dsn,
                               connect_args=connect_args_for(ds.kind, dsn))
        ms = (timeout_s or s.query_timeout_s) * 1000
        with engine.connect() as c:
            prepare_connection(c, engine.dialect.name, ms)
            rows = c.execute(text(sql), binds).mappings().fetchmany(limit)
            result = [dict(r) for r in rows]
    session.add(AuditLog(actor="openapi", action="query",
                         target=iface.interface_key,
                         detail_json={"rows": len(result)}))
    session.commit()
    return result, len(result)


_IFACE_ACTIONS = ("query",)


def interface_history(session, project_id, interface_id, limit=50):
    iface = session.get(Interface, interface_id)
    if not iface or iface.project_id != project_id:
        return None
    try:
        size = max(1, min(int(limit or 50), 200))
    except (TypeError, ValueError):
        raise ValueError("limit must be a number")
    rows = (session.query(AuditLog)
            .filter(AuditLog.target.in_([iface.interface_key,
                                         str(interface_id)]),
                    AuditLog.action.in_(_IFACE_ACTIONS))
            .order_by(AuditLog.at.desc(), AuditLog.id.desc())
            .limit(size).all())
    return [{"id": r.id, "actor": r.actor, "action": r.action,
             "at": r.at.isoformat(), "detail": r.detail_json or {}}
            for r in rows]


def interface_stats(session, project_id, interface_id, days=30):
    from collections import defaultdict
    from datetime import datetime, timedelta, timezone
    iface = session.get(Interface, interface_id)
    if not iface or iface.project_id != project_id:
        return None
    days = max(1, min(int(days or 30), 365))
    since = (datetime.now(timezone.utc) - timedelta(days=days - 1)).date()
    rows = (session.query(AuditLog)
            .filter_by(action="query", target=iface.interface_key)
            .order_by(AuditLog.id.desc()).all())
    by_day = defaultdict(lambda: {"calls": 0, "rows": 0})
    total = {"calls": 0, "rows": 0}
    for row in rows:
        day = row.at.date()
        if day < since:
            continue
        count = int((row.detail_json or {}).get("rows") or 0)
        for target in (by_day[day.isoformat()], total):
            target["calls"] += 1
            target["rows"] += count
    return {"since": since.isoformat(),
            "days": [dict(v, day=k) for k, v in sorted(by_day.items())],
            "total": total}
