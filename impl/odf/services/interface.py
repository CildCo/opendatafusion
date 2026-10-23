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
