from urllib.parse import parse_qs, unquote, urlparse


def options(dsn):
    parsed = urlparse(dsn or "")
    if parsed.scheme not in ("hive", "hive2"):
        raise ValueError("hive datasource needs a hive://host:port/db dsn")
    query = parse_qs(parsed.query)
    return {"host": parsed.hostname or "", "port": parsed.port or 10000,
            "database": unquote((parsed.path or "").lstrip("/")) or "default",
            "username": unquote(parsed.username or ""),
            "password": unquote(parsed.password or ""),
            "auth": (query.get("auth") or ["NOSASL"])[0]}


def connection(dsn):
    from pyhive import hive
    opts = options(dsn)
    kwargs = {"host": opts["host"], "port": opts["port"],
              "username": opts["username"] or None,
              "database": opts["database"]}
    if opts["password"]:
        kwargs["password"] = opts["password"]
    if opts["auth"]:
        kwargs["auth"] = opts["auth"]
    return hive.Connection(**kwargs)


def ping(dsn):
    conn = connection(dsn)
    try:
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT 1")
            cursor.fetchall()
        finally:
            cursor.close()
    finally:
        conn.close()
    return True


def query(dsn, sql, max_rows=1000):
    conn = connection(dsn)
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
    conn = connection(dsn)
    try:
        cursor = conn.cursor()
        try:
            cursor.execute("SHOW TABLES")
            rows = cursor.fetchall()
            entries = []
            for row in rows:
                if len(row) >= 2:
                    entries.append((str(row[0]), str(row[1])))
                else:
                    entries.append((opts["database"], str(row[0])))
            out = []
            for schema, name in entries:
                cursor.execute("DESCRIBE `%s`" % name.replace("`", "``"))
                columns = []
                for row in cursor.fetchall():
                    column = (row[0] or "").strip()
                    if not column or column.startswith("#"):
                        continue
                    columns.append({"name": column,
                                    "type": str(row[1] or "string")})
                out.append({"schema": schema, "table": name,
                            "columns": columns})
            return out
        finally:
            cursor.close()
    finally:
        conn.close()
