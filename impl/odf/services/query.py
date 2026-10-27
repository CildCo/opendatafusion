from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from odf.services.datasource import (connect_args_for, get_dsn,
                                     prepare_connection)
from odf.settings import get_settings
from odf.trino.client import (TrinoError, client_for_datasource,
                              render_params)


def _sql_backend(ds, sql, params, max_rows, read_only, timeout_ms):
    dsn = get_dsn(ds)
    engine = create_engine(dsn, connect_args=connect_args_for(ds.kind, dsn))
    try:
        with engine.connect() as conn:
            if read_only and engine.dialect.name == "postgresql":
                conn.execute(text("set transaction read only"))
            prepare_connection(conn, engine.dialect.name, timeout_ms)
            if read_only and engine.dialect.name in ("mysql", "mariadb"):
                conn.execute(text("START TRANSACTION READ ONLY"))
            result = conn.execute(text(sql), params or {})
            columns = list(result.keys())
            rows = [dict(row) for row in
                    result.mappings().fetchmany(max_rows)]
    finally:
        engine.dispose()
    return {"columns": columns, "rows": rows, "row_count": len(rows),
            "truncated": False}


def execute_query(session, ds, sql, params=None, max_rows=1000,
                  read_only=False, timeout_ms=None):
    settings = get_settings()
    if timeout_ms is None:
        timeout_ms = settings.query_timeout_s * 1000
    try:
        if ds.kind == "file":
            from odf import filesource
            return filesource.execute(ds, sql, params or {}, max_rows)
        if ds.kind == "clickhouse":
            from odf import clickhouse
            return clickhouse.execute(ds, sql, params or {}, max_rows)
        if ds.kind == "trino":
            client = client_for_datasource(ds)
            return client.query(render_params(sql, params or {}),
                                max_rows=max_rows)
        return _sql_backend(ds, sql, params, max_rows, read_only, timeout_ms)
    except (SQLAlchemyError, TrinoError, ValueError) as error:
        raise ValueError("query failed: %s" % str(error)[:300])
