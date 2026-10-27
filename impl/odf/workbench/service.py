import hashlib
import time

from odf.apistudio.sqlguard import ensure_read_only
from odf.models import Datasource
from odf.services.audit import write_audit
from odf.services.query import execute_query
from odf.services.sqldialect import limited
from odf.settings import get_settings


def _datasource(session, project_id, datasource_id):
    ds = session.get(Datasource, datasource_id)
    if not ds or ds.project_id != project_id:
        raise ValueError("datasource not found")
    return ds


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
    started = time.time()
    wrapped = limited(sql, ds.kind, max_rows + 1)
    result = execute_query(session, ds, wrapped, None, max_rows + 1,
                           read_only=True)
    columns = result["columns"]
    rows = result["rows"]
    truncated = len(rows) > max_rows
    rows = rows[:max_rows]
    elapsed = int((time.time() - started) * 1000)
    write_audit(session, actor, "workbench_query", str(ds.id),
                {"sql_sha256": hashlib.sha256(
                    sql.encode("utf-8")).hexdigest(),
                 "sql_preview": sql[:300], "row_count": len(rows)})
    return {"columns": columns, "rows": rows, "row_count": len(rows),
            "ms": elapsed, "truncated": truncated}
