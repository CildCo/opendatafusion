import hashlib
import time

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from odf.apistudio.sqlguard import ensure_read_only
from odf.models import Datasource
from odf.services.audit import write_audit
from odf.services.datasource import (connect_args_for, get_dsn,
                                     prepare_connection)
from odf.services.sqldialect import limited
from odf.settings import get_settings


def _datasource(session, project_id, datasource_id):
    ds = session.get(Datasource, datasource_id)
    if not ds or ds.project_id != project_id:
        raise ValueError("datasource not found")
    return ds


def _engine(ds):
    dsn = get_dsn(ds)
    args = connect_args_for(ds.kind, dsn)
    return create_engine(dsn, connect_args=args)


def _max_rows(limit):
    settings = get_settings()
    try:
        requested = int(limit or 1000)
    except (TypeError, ValueError):
        raise ValueError("limit must be a number")
    if requested < 1:
        raise ValueError("limit must be positive")
    return min(requested, settings.query_max_rows)


def run_query(session, project_id, datasource_id, sql, limit=1000,
              actor="", role=None):
    ds = _datasource(session, project_id, datasource_id)
    from odf.services.masking import datasource_has_policies
    if role != "admin" and datasource_has_policies(session, ds.id):
        raise ValueError(
            "workbench is disabled for governed datasources")
    ensure_read_only(sql)
    max_rows = _max_rows(limit)
    settings = get_settings()
    started = time.time()
    wrapped = limited(sql, ds.kind, max_rows + 1)
    try:
        if ds.kind == "file":
            from odf import filesource
            result = filesource.execute(ds, wrapped, {}, max_rows + 1)
            columns = result["columns"]
            rows = result["rows"]
        elif ds.kind == "clickhouse":
            from odf import clickhouse
            result = clickhouse.execute(ds, wrapped, {}, max_rows + 1)
            columns = result["columns"]
            rows = result["rows"]
        else:
            engine = _engine(ds)
            try:
                with engine.connect() as c:
                    if engine.dialect.name == "postgresql":
                        c.execute(text("set transaction read only"))
                    prepare_connection(c, engine.dialect.name,
                                       settings.query_timeout_s * 1000)
                    if engine.dialect.name in ("mysql", "mariadb"):
                        c.execute(text("START TRANSACTION READ ONLY"))
                    result = c.execute(text(wrapped))
                    columns = list(result.keys())
                    rows = [dict(r) for r in
                            result.mappings().fetchmany(max_rows + 1)]
            finally:
                engine.dispose()
    except (SQLAlchemyError, ValueError) as e:
        raise ValueError("query failed: %s" % str(e)[:300])
    truncated = len(rows) > max_rows
    rows = rows[:max_rows]
    elapsed = int((time.time() - started) * 1000)
    write_audit(session, actor, "workbench_query", str(ds.id),
                {"sql_sha256": hashlib.sha256(
                    sql.encode("utf-8")).hexdigest(),
                 "sql_preview": sql[:300], "row_count": len(rows)})
    return {"columns": columns, "rows": rows, "row_count": len(rows),
            "ms": elapsed, "truncated": truncated}
