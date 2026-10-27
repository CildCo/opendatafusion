import re
from datetime import date, datetime

from odf.connectors.base import Source
from odf.connectors.sql import format_cursor, parse_cursor
from odf.trino.client import client_for_datasource, literal

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


def _quote(part: str) -> str:
    if not isinstance(part, str) or not _IDENT.match(part):
        raise ValueError("invalid identifier: %s" % part)
    return '"%s"' % part


def quote_ident(name: str) -> str:
    return _quote(name)


def quote_table(name: str) -> str:
    if not isinstance(name, str) or not name:
        raise ValueError("invalid identifier: %s" % name)
    return ".".join(_quote(part) for part in name.split("."))


def _cursor_value(raw, kind: str):
    if raw is None:
        return None
    if kind == "varchar":
        return str(raw)
    if kind == "timestamp":
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    if kind == "date":
        return date.fromisoformat(str(raw)[:10])
    if kind in ("bigint", "integer", "double"):
        return float(raw) if kind == "double" else int(raw)
    try:
        return int(raw)
    except (TypeError, ValueError):
        pass
    try:
        return float(raw)
    except (TypeError, ValueError):
        pass
    return str(raw)


class TrinoSource(Source):
    def __init__(self, ds, dag):
        self.ds, self.dag = ds, dag

    def read(self, cursor, limit):
        table = quote_table(self.dag["source_table"])
        column = self.dag.get("cursor_column")
        pk = self.dag.get("pk")
        if isinstance(pk, list):
            pk = pk[0] if pk else None
        column_sql = _quote(column) if column else ""
        pk_sql = _quote(pk) if pk else ""
        cursor_kind = self.dag.get("cursor_type") or "auto"

        sql = "SELECT * FROM %s" % table
        current = parse_cursor(cursor)
        if column and current:
            value = _cursor_value(current[0], cursor_kind)
            if len(current) > 1 and current[1] is not None and pk:
                previous = _cursor_value(current[1], cursor_kind)
                sql += (' WHERE ((%s > %s) OR (%s = %s AND %s > %s))'
                        % (column_sql, literal(value), column_sql,
                           literal(value), pk_sql, literal(previous)))
            else:
                sql += " WHERE %s > %s" % (column_sql, literal(value))
        if column:
            sql += " ORDER BY %s" % column_sql
            if pk and pk != column:
                sql += ", %s" % pk_sql
        sql += " LIMIT %d" % max(1, int(limit))

        result = client_for_datasource(self.ds).query(sql, max_rows=limit)
        rows = result["rows"]
        new_cursor = cursor
        if column and rows:
            last = rows[-1]
            if column in last and (not pk or pk in last):
                new_cursor = format_cursor(last[column],
                                           last[pk] if pk else last[column])
        return rows, new_cursor
