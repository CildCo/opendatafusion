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


class HiveSource:
    def __init__(self, ds, dag):
        from odf.services.datasource import get_dsn
        self.dsn = get_dsn(ds)
        self.dag = dag

    def read(self, cursor, limit):
        from odf.apistudio.compiler import quote_ident
        from odf.connectors.sql import format_cursor, parse_cursor
        table = (self.dag.get("source_table") or "").strip()
        if not table:
            raise ValueError("hive source needs a table")
        parts = [quote_ident(p) for p in table.split(".") if p]
        sql = "SELECT * FROM %s" % ".".join(parts)
        col = self.dag.get("cursor_column")
        pk = self.dag.get("pk") or "id"
        binds = []
        current = parse_cursor(cursor)
        if col and current:
            if len(current) > 1 and current[1] is not None:
                sql += (" WHERE (%s > ? OR (%s = ? AND %s > ?))"
                        % (quote_ident(col), quote_ident(col),
                           quote_ident(pk)))
                binds += [current[0], current[0], current[1]]
            else:
                sql += " WHERE %s > ?" % quote_ident(col)
                binds.append(current[0])
        if col:
            sql += " ORDER BY %s, %s" % (quote_ident(col), quote_ident(pk))
        sql += " LIMIT %d" % max(1, int(limit))
        # HiveServer2 does not accept bound parameters here.
        from odf.trino.client import render_params
        rendered = sql
        for index, value in enumerate(binds, 1):
            rendered = rendered.replace("?", _literal(value), 1)
        result = query(self.dsn, rendered, limit)
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
