from urllib.parse import parse_qs, unquote, urlparse


def options(dsn):
    parsed = urlparse(dsn or "")
    if parsed.scheme not in ("dm", "dm8"):
        raise ValueError("dm datasource needs a dm://user:pass@host:5236/schema dsn")
    query = parse_qs(parsed.query)
    schema = unquote((parsed.path or "").lstrip("/")) or \
        unquote(parsed.username or "")
    return {"host": parsed.hostname or "", "port": parsed.port or 5236,
            "username": unquote(parsed.username or ""),
            "password": unquote(parsed.password or ""),
            "schema": (query.get("schema") or [schema])[0].upper()}


def connect(dsn):
    import dmPython
    opts = options(dsn)
    return dmPython.connect(user=opts["username"],
                            password=opts["password"],
                            server=opts["host"], port=opts["port"],
                            autoCommit=True)


def ping(dsn):
    conn = connect(dsn)
    try:
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT 1 FROM DUAL")
            cursor.fetchall()
        finally:
            cursor.close()
    finally:
        conn.close()
    return True


def query(dsn, sql, max_rows=1000):
    conn = connect(dsn)
    try:
        cursor = conn.cursor()
        try:
            cursor.execute(sql)
            columns = [c[0] for c in (cursor.description or [])]
            rows = [dict(zip(columns, row))
                    for row in cursor.fetchmany(max_rows)]
        finally:
            cursor.close()
    finally:
        conn.close()
    return {"columns": columns, "rows": rows, "row_count": len(rows)}


def tables(dsn):
    opts = options(dsn)
    owner = opts["schema"].replace("'", "''")
    conn = connect(dsn)
    try:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT OWNER, TABLE_NAME FROM ALL_TABLES "
                "WHERE OWNER = '%s' AND TABLE_NAME NOT LIKE '##%%' "
                "ORDER BY TABLE_NAME" % owner)
            names = [(row[0], row[1]) for row in cursor.fetchall()]
            out = []
            for schema, table in names:
                cursor.execute(
                    "SELECT COLUMN_NAME, DATA_TYPE FROM ALL_TAB_COLUMNS "
                    "WHERE OWNER = '%s' AND TABLE_NAME = '%s' "
                    "ORDER BY COLUMN_ID"
                    % (schema.replace("'", "''"),
                       table.replace("'", "''")))
                columns = [{"name": row[0], "type": str(row[1] or "VARCHAR")}
                           for row in cursor.fetchall()]
                out.append({"schema": schema, "table": table,
                            "columns": columns})
            return out
        finally:
            cursor.close()
    finally:
        conn.close()


class DmSource:
    def __init__(self, ds, dag):
        from odf.services.datasource import get_dsn
        self.dsn = get_dsn(ds)
        self.dag = dag

    def read(self, cursor, limit):
        from odf.apistudio.compiler import quote_ident
        from odf.connectors.sql import format_cursor, parse_cursor
        table = (self.dag.get("source_table") or "").strip()
        if not table:
            raise ValueError("dm source needs a table")
        parts = [quote_ident(p) for p in table.split(".") if p]
        sql = "SELECT * FROM %s" % ".".join(parts)
        col = self.dag.get("cursor_column")
        pk = self.dag.get("pk") or "id"
        current = parse_cursor(cursor)
        if col and current:
            if len(current) > 1 and current[1] is not None:
                sql += (" WHERE (%s > ? OR (%s = ? AND %s > ?))"
                        % (quote_ident(col), quote_ident(col),
                           quote_ident(pk)))
                sql += ""
                sql = sql.replace("?", _literal(current[0]), 1)
                sql = sql.replace("?", _literal(current[0]), 1)
                sql = sql.replace("?", _literal(current[1]), 1)
            else:
                sql += " WHERE %s > " % quote_ident(col) + _literal(
                    current[0])
        if col:
            sql += " ORDER BY %s, %s" % (quote_ident(col), quote_ident(pk))
        sql += " LIMIT %d" % max(1, int(limit))
        result = query(self.dsn, sql, limit)
        rows = result["rows"]
        new_cursor = cursor
        if col and rows:
            last = rows[-1]
            new_cursor = format_cursor(last.get(col), last.get(pk))
        return rows, new_cursor


def _literal(value):
    if value is None:
        return "NULL"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"
