import hashlib
import re
import time

import duckdb
import pyarrow as pa
from sqlalchemy import create_engine, select
from sqlalchemy.exc import SQLAlchemyError

from odf.apistudio.sqlguard import _scan, ensure_read_only
from odf.connectors.sql import table_for
from odf.models import Datasource
from odf.services.audit import write_audit
from odf.services.datasource import connect_args_for, get_dsn, prepare_connection
from odf.settings import get_settings

MAX_SOURCES = 4
MAX_SOURCE_ROWS = 20000
_ALIAS = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SQL_KINDS = {"postgres", "postgresql", "sqlite", "mysql", "mariadb"}
_FORBIDDEN = re.compile(
    r"\b(read_csv|read_csv_auto|read_parquet|read_json|read_json_auto|"
    r"read_text|read_blob|read_xlsx|parquet_scan|csv_scan|excel_scan|"
    r"iceberg_scan|delta_scan|st_read|glob|attach|install|load|copy|"
    r"export|import|httpfs|sqlite_scan|postgres_scan)\b",
    re.IGNORECASE)


def _validate(sources):
    if not isinstance(sources, list) or not 1 <= len(sources) <= MAX_SOURCES:
        raise ValueError("sources must contain 1..%d items" % MAX_SOURCES)
    aliases = set()
    for s in sources:
        if not isinstance(s, dict):
            raise ValueError("source must be an object")
        alias = s.get("alias")
        if not isinstance(alias, str) or not _ALIAS.fullmatch(alias):
            raise ValueError("invalid source alias: %s" % alias)
        if alias in aliases:
            raise ValueError("duplicate source alias: %s" % alias)
        aliases.add(alias)
        if not isinstance(s.get("datasource_id"), int):
            raise ValueError("datasource_id is required")
        if not isinstance(s.get("table"), str) or not s["table"]:
            raise ValueError("table is required")


def _check_sql(sql):
    ensure_read_only(sql)
    m = _FORBIDDEN.search(_scan(sql))
    if m:
        raise ValueError("forbidden federation keyword: %s" % m.group(1))


def _engine(ds):
    dsn = get_dsn(ds)
    return create_engine(dsn, connect_args=connect_args_for(ds.kind, dsn))


def _snapshot(session, project_id, source, settings):
    ds = session.get(Datasource, source["datasource_id"])
    if not ds or ds.project_id != project_id:
        raise ValueError("datasource not found")
    if ds.kind not in SQL_KINDS:
        raise ValueError("federation requires a SQL datasource")
    engine = _engine(ds)
    try:
        try:
            table = table_for(source["table"], engine)
        except Exception:
            raise ValueError("source table not found: %s" % source["alias"])
        try:
            with engine.connect() as c:
                prepare_connection(c, engine.dialect.name,
                                   settings.query_timeout_s * 1000)
                rows = [dict(r) for r in c.execute(
                    select(table).limit(MAX_SOURCE_ROWS + 1))
                    .mappings().fetchall()]
        except SQLAlchemyError as e:
            raise ValueError("source read failed: %s" % str(e)[:200])
    finally:
        engine.dispose()
    if len(rows) > MAX_SOURCE_ROWS:
        raise ValueError("source too large: %s" % source["alias"])
    if rows:
        return pa.Table.from_pylist(rows)
    return pa.table({name: [] for name in table.c.keys()})


def run_federated(session, project_id, sources, sql, limit=1000, actor=""):
    _validate(sources)
    _check_sql(sql)
    settings = get_settings()
    try:
        requested = int(limit or 1000)
    except (TypeError, ValueError):
        raise ValueError("limit must be a number")
    if requested < 1:
        raise ValueError("limit must be positive")
    max_rows = min(requested, settings.query_max_rows)
    started = time.time()
    con = duckdb.connect()
    try:
        try:
            con.execute("SET memory_limit = '512MB'")
            con.execute("SET threads = 2")
            con.execute("SET enable_external_access = false")
            con.execute("SET lock_configuration = true")
        except Exception:
            raise ValueError("federation is unavailable")
        for src in sources:
            con.register(src["alias"], _snapshot(session, project_id, src,
                                                 settings))
        try:
            result = con.execute(sql)
            columns = [d[0] for d in result.description]
            rows = [dict(zip(columns, r))
                    for r in result.fetchmany(max_rows + 1)]
        except Exception as e:
            raise ValueError("federated query failed: %s" % str(e)[:300])
    finally:
        con.close()
    truncated = len(rows) > max_rows
    rows = rows[:max_rows]
    elapsed = int((time.time() - started) * 1000)
    write_audit(session, actor, "federated_query", "workbench",
                {"sources": [{"alias": s["alias"],
                              "datasource_id": s["datasource_id"],
                              "table": s["table"]} for s in sources],
                 "sql_sha256": hashlib.sha256(
                     sql.encode("utf-8")).hexdigest(),
                 "sql_preview": sql[:300], "row_count": len(rows)})
    return {"columns": columns, "rows": rows, "row_count": len(rows),
            "ms": elapsed, "truncated": truncated}
