import re
from urllib.parse import parse_qs, unquote, urlparse

from odf.services.datasource import get_dsn

IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def parse_dsn(dsn: str) -> dict:
    raw = (dsn or "").strip()
    secure = False
    native = False
    if raw.startswith("clickhouse+https://"):
        raw, secure = "https://" + raw[len("clickhouse+https://"):], True
    elif raw.startswith("clickhouse+http://"):
        raw = "http://" + raw[len("clickhouse+http://"):]
    elif raw.startswith("clickhouse://"):
        raw, native = "http://" + raw[len("clickhouse://"):], True
    elif raw.startswith("http://"):
        pass
    elif raw.startswith("https://"):
        secure = True
    else:
        raise ValueError("clickhouse DSN must use clickhouse://, "
                         "clickhouse+http:// or clickhouse+https://")
    parsed = urlparse(raw)
    if not parsed.hostname:
        raise ValueError("clickhouse host is required")
    query = parse_qs(parsed.query)
    if (query.get("secure") or ["0"])[0].lower() in ("1", "true", "yes"):
        secure = True
    port = parsed.port
    if port == 8443:
        secure = True
    if port == 9000 and native:
        raise ValueError("native port 9000 is not supported; use HTTP 8123 "
                         "or HTTPS 8443")
    if port is None:
        port = 8443 if secure else 8123
    database = unquote(parsed.path.lstrip("/")) or "default"
    return {"host": parsed.hostname, "port": port,
            "username": unquote(parsed.username or "default"),
            "password": unquote(parsed.password or ""),
            "database": database, "secure": secure}


def client_from_dsn(dsn: str):
    import clickhouse_connect
    opts = parse_dsn(dsn)
    return clickhouse_connect.get_client(
        host=opts["host"], port=opts["port"], username=opts["username"],
        password=opts["password"], database=opts["database"],
        secure=opts["secure"], connect_timeout=5)


def client_for(ds):
    return client_from_dsn(get_dsn(ds))


def _literal(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return repr(value)
    return "'%s'" % str(value).replace("\\", "\\\\").replace("'", "\\'")


def render(sql: str, params: dict | None = None) -> str:
    if not isinstance(sql, str) or not sql.strip():
        raise ValueError("sql is required")
    binds = dict(params or {})

    def repl(match):
        key = match.group(1)
        if key not in binds:
            raise ValueError("missing parameter: %s" % key)
        return _literal(binds[key])

    return re.sub(r"(?<!:):([A-Za-z_]\w*)", repl, sql)


def _quote(name: str) -> str:
    if not IDENT.match(name or ""):
        raise ValueError("invalid identifier: %s" % name)
    return "`%s`" % name


def _table_sql(ds, table: str) -> tuple[str, str]:
    parts = (table or "").split(".")
    if not 1 <= len(parts) <= 2:
        raise ValueError("invalid table: %s" % table)
    db = parts[0] if len(parts) == 2 else parse_dsn(get_dsn(ds))["database"]
    name = parts[-1]
    return _quote(db), _quote(name)


def execute(ds, sql: str, params: dict | None = None,
            max_rows: int = 1000) -> dict:
    from odf.settings import get_settings
    body = sql.strip().rstrip(";")
    wrapped = "SELECT * FROM (%s) AS _odf LIMIT %d" % (
        body, max(1, int(max_rows)))
    client = client_for(ds)
    try:
        result = client.query(
            render(wrapped, params),
            settings={"max_execution_time": get_settings().query_timeout_s})
        columns = list(result.column_names or [])
        rows = [dict(zip(columns, row))
                for row in (result.result_rows or [])[:max_rows]]
    except Exception as e:
        raise ValueError(str(e))
    finally:
        client.close()
    return {"columns": columns, "rows": rows}


def tables(ds) -> list[dict]:
    db = parse_dsn(get_dsn(ds))["database"]
    client = client_for(ds)
    try:
        names = client.query("SHOW TABLES FROM %s" % _quote(db))
        out = []
        for row in names.result_rows:
            name = row[0]
            desc = client.query("DESCRIBE TABLE %s.%s"
                                % (_quote(db), _quote(name)))
            out.append({"schema": db, "table": name,
                        "columns": [{"name": r[0], "type": r[1]}
                                    for r in desc.result_rows]})
        return out
    except Exception as e:
        raise ValueError(str(e))
    finally:
        client.close()


def columns(ds, table: str) -> list[dict]:
    db, name = _table_sql(ds, table)
    client = client_for(ds)
    try:
        desc = client.query("DESCRIBE TABLE %s.%s" % (db, name))
        cols = [{"name": r[0], "type": r[1]} for r in desc.result_rows]
    except Exception as e:
        raise ValueError(str(e))
    finally:
        client.close()
    if not cols:
        raise ValueError("table not found: %s" % table)
    return cols


def read_rows(ds, table: str, cursor_column: str | None, pk: str,
              cursor: str | None, limit: int):
    from odf.connectors.sql import format_cursor, parse_cursor
    db, name = _table_sql(ds, table)
    cols = {c["name"]: c["type"] for c in columns(ds, table)}
    cur = parse_cursor(cursor)
    params = {}
    where = ""
    if cursor_column and cur:
        ctype = cols.get(cursor_column, "String")
        ptype = cols.get(pk, "String")
        if len(cur) > 1 and cur[1] is not None:
            where = (" WHERE (%s > {c:%s} OR (%s = {c:%s} AND %s > {p:%s}))"
                     % (_quote(cursor_column), ctype, _quote(cursor_column),
                        ctype, _quote(pk), ptype))
            params = {"c": cur[0], "p": cur[1]}
        else:
            where = " WHERE %s > {c:%s}" % (_quote(cursor_column), ctype)
            params = {"c": cur[0]}
    order = ""
    if cursor_column:
        order = " ORDER BY %s, %s" % (_quote(cursor_column), _quote(pk))
    sql = ("SELECT * FROM %s.%s%s%s LIMIT %d"
           % (db, name, where, order, max(1, int(limit))))
    client = client_for(ds)
    try:
        result = client.query(sql, parameters=params or None)
        columns_ = list(result.column_names or [])
        rows = [dict(zip(columns_, r)) for r in result.result_rows]
    finally:
        client.close()
    new_cursor = cursor
    if cursor_column and rows:
        new_cursor = format_cursor(rows[-1][cursor_column], rows[-1][pk])
    return rows, new_cursor
