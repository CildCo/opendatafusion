import re

from odf.trino.client import client_for_datasource, literal

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


def project_schema(project_id: int) -> str:
    return "odf_p%d" % int(project_id)


def _catalog(client) -> str:
    catalog = getattr(client, "catalog", "") or ""
    if not _IDENT.match(catalog):
        raise ValueError("trino datasource needs a catalog in the dsn")
    return catalog


def ensure_schema(client, project_id: int) -> str:
    schema = project_schema(project_id)
    client.execute('CREATE SCHEMA IF NOT EXISTS "%s"."%s"'
                   % (_catalog(client), schema))
    return schema


def _column_rows(client, where: str) -> list:
    sql = ("select table_name, column_name, data_type "
           "from %s.information_schema.columns where %s "
           "order by table_name, ordinal_position"
           % (_catalog(client), where))
    return client.query(sql, max_rows=200000)["rows"]


def list_tables(client, schema: str) -> list:
    grouped = {}
    for row in _column_rows(client, "table_schema = %s" % literal(schema)):
        grouped.setdefault(row["table_name"], []).append(
            {"name": row["column_name"], "type": row["data_type"]})
    return [{"table": name, "columns": columns}
            for name, columns in grouped.items()]


def table_columns(client, schema: str, table: str) -> list:
    where = ("table_schema = %s and table_name = %s"
             % (literal(schema), literal(table)))
    return [{"name": row["column_name"], "type": row["data_type"]}
            for row in _column_rows(client, where)]


def _meta(client, schema, table, suffix, order=None, limit=200):
    from odf.connectors.trino import quote_ident
    name = "%s$%s" % (table, suffix)
    sql = "SELECT * FROM %s.%s.%s" % (
        quote_ident(_catalog(client)), quote_ident(schema),
        quote_ident(name))
    if order:
        sql += " ORDER BY %s DESC" % order
    sql += " LIMIT %d" % max(1, min(int(limit), 2000))
    return client.query(sql, max_rows=min(int(limit), 2000))


def snapshots(client, schema, table, limit=100):
    return _meta(client, schema, table, "snapshots",
                 "committed_at", limit)["rows"]


def files(client, schema, table, limit=500):
    return _meta(client, schema, table, "files", None, limit)["rows"]


def history(client, schema, table, limit=100):
    return _meta(client, schema, table, "history",
                 "made_current_at", limit)["rows"]


def partitions(client, schema, table, limit=500):
    return _meta(client, schema, table, "partitions", None, limit)["rows"]


def time_travel(client, schema, table, snapshot_id=None, timestamp=None,
                limit=100):
    from odf.connectors.trino import quote_ident
    name = "%s.%s.%s" % (quote_ident(_catalog(client)),
                         quote_ident(schema), quote_ident(table))
    if snapshot_id is not None:
        clause = " FOR VERSION AS OF %d" % int(snapshot_id)
    elif timestamp:
        import re
        value = str(timestamp).strip()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}:\d{2})?",
                            value):
            raise ValueError("invalid timestamp")
        clause = " FOR TIMESTAMP AS OF TIMESTAMP '%s'" % value
    else:
        raise ValueError("snapshot_id or timestamp is required")
    result = client.query("SELECT * FROM %s%s" % (name, clause),
                          max_rows=max(1, min(int(limit), 1000)))
    return {"columns": result.get("columns") or [],
            "rows": result.get("rows") or [],
            "row_count": result.get("row_count") or 0}


def health(client, schema, table, small_file_bytes=16 * 1024 * 1024,
           max_snapshots=20):
    file_rows = files(client, schema, table, 2000)
    snap_rows = snapshots(client, schema, table, 500)
    partition_rows = partitions(client, schema, table, 500)
    total_size = sum(int(row.get("file_size_in_bytes") or 0)
                     for row in file_rows)
    small = sum(1 for row in file_rows
                if int(row.get("file_size_in_bytes") or 0) < small_file_bytes)
    issues = []
    status = "ok"
    if len(file_rows) > 0 and small / len(file_rows) > 0.5:
        issues.append("more than half of the files are small")
        status = "warning"
    if len(snap_rows) > max_snapshots:
        issues.append("too many snapshots")
        status = "warning"
    if len(file_rows) >= 2000:
        issues.append("file listing reached the limit")
        status = "warning"
    if any(int(row.get("file_count") or 0) > 200 for row in partition_rows):
        issues.append("partition skew")
        if status == "ok":
            status = "warning"
    return {"status": status, "issues": issues,
            "files": len(file_rows), "size_bytes": total_size,
            "small_files": small, "snapshots": len(snap_rows),
            "partitions": len(partition_rows)}
