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
