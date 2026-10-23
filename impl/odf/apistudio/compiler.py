import re

AGGREGATES = {"sum", "count", "avg", "min", "max"}
OPS = {"=", "!=", ">", ">=", "<", "<=", "in", "like", "is null",
       "is not null"}
MAX_IN_VALUES = 100
_ALIAS = re.compile(r"^\w+$", re.UNICODE)


class CompileError(ValueError):
    pass


def quote_ident(name):
    if not isinstance(name, str) or not name or "\x00" in name:
        raise CompileError("invalid identifier")
    return '"%s"' % name.replace('"', '""')


def quote_table(name):
    if not isinstance(name, str) or not name:
        raise CompileError("table is required")
    parts = name.split(".", 1)
    return ".".join(quote_ident(p) for p in parts)


def _alias(name):
    if not isinstance(name, str) or not _ALIAS.fullmatch(name):
        raise CompileError("invalid alias: %s" % name)
    return quote_ident(name)


def _column(name, columns):
    if name not in columns:
        raise CompileError("unknown column: %s" % name)
    return quote_ident(name)


def _safe_key(name, binds):
    base = re.sub(r"\W", "_", str(name or "p"), flags=re.UNICODE)
    if not base or base[0].isdigit():
        base = "p_" + base
    key, i = base, 1
    while key in binds:
        key = "%s_%d" % (base, i)
        i += 1
    return key


def _select_expr(item, columns, aliases):
    if not isinstance(item, dict):
        raise CompileError("select item must be an object")
    col = item.get("column")
    agg = item.get("agg")
    if agg:
        if agg not in AGGREGATES:
            raise CompileError("unsupported aggregate: %s" % agg)
        if col == "*" and agg == "count":
            inner = "*"
        else:
            inner = _column(col, columns)
        expr = "%s(%s)" % (agg.upper(), inner)
    else:
        expr = _column(col, columns)
    alias = item.get("as")
    if alias:
        expr = "%s AS %s" % (expr, _alias(alias))
        aliases.add(alias)
    return expr


def _filter_expr(item, columns, params, binds):
    if not isinstance(item, dict):
        raise CompileError("filter must be an object")
    col = _column(item.get("column"), columns)
    op = item.get("op")
    if op not in OPS:
        raise CompileError("unsupported operator: %s" % op)
    if op in ("is null", "is not null"):
        return "%s %s" % (col, op.upper())
    from_param = bool(item.get("param"))
    if from_param:
        name = item["param"]
        if name not in params:
            raise CompileError("missing parameter: %s" % name)
        value = params[name]
        if value is None or value == "":
            return None
    else:
        name = item.get("column")
        value = item.get("value")
    if op == "in":
        values = value if isinstance(value, list) else [value]
        if not values:
            raise CompileError("in requires at least one value")
        if len(values) > MAX_IN_VALUES:
            raise CompileError("in accepts at most %d values"
                               % MAX_IN_VALUES)
        keys = []
        for i, v in enumerate(values):
            key = _safe_key("%s_%d" % (name, i), binds)
            binds[key] = v
            keys.append(":" + key)
        return "%s IN (%s)" % (col, ", ".join(keys))
    key = _safe_key(name, binds)
    binds[key] = value
    return "%s %s :%s" % (col, op.upper(), key)


def compile_visual(query, columns, params, limit_override=None):
    if not isinstance(query, dict):
        raise CompileError("query must be an object")
    if not query.get("table"):
        raise CompileError("table is required")
    columns = list(columns)
    aliases = set()
    select = query.get("select") or []
    if not select:
        raise CompileError("select requires at least one column")
    exprs = [_select_expr(x, columns, aliases) for x in select]

    binds = {}
    filters = []
    for f in query.get("filters") or []:
        expr = _filter_expr(f, columns, params, binds)
        if expr:
            filters.append(expr)

    group = query.get("group_by") or []
    selected_plain = {x.get("column") for x in select
                      if isinstance(x, dict) and not x.get("agg")}
    for col in group:
        if col not in columns:
            raise CompileError("unknown column: %s" % col)
        if col not in selected_plain:
            raise CompileError("group_by column must be selected: %s" % col)

    order = []
    for item in query.get("order_by") or []:
        if not isinstance(item, dict):
            raise CompileError("order_by item must be an object")
        col = item.get("column")
        if col not in aliases and col not in columns:
            raise CompileError("unknown order column: %s" % col)
        direction = (item.get("dir") or "asc").lower()
        if direction not in ("asc", "desc"):
            raise CompileError("invalid order direction")
        order.append("%s %s" % (quote_ident(col), direction.upper()))

    if limit_override is None:
        try:
            limit = int(query.get("limit", 1000))
        except (TypeError, ValueError):
            raise CompileError("limit must be a number")
        limit = max(1, min(limit, 10000))
        limit_sql = " LIMIT %d" % limit
    elif limit_override:
        limit = max(1, min(int(limit_override), 10000))
        limit_sql = " LIMIT %d" % limit
    else:
        limit_sql = ""

    sql = "SELECT %s FROM %s" % (", ".join(exprs),
                                 quote_table(query["table"]))
    if filters:
        sql += " WHERE " + " AND ".join(filters)
    if group:
        sql += " GROUP BY " + ", ".join(quote_ident(c) for c in group)
    if order:
        sql += " ORDER BY " + ", ".join(order)
    sql += limit_sql
    return sql, binds


def render_sql(sql, defs, params):
    if not isinstance(sql, str) or not sql.strip():
        raise CompileError("sql is required")
    names = {p["name"] for p in defs}
    used = set()

    def repl(m):
        name = m.group(1)
        if name not in names:
            raise CompileError("undeclared parameter: %s" % name)
        used.add(name)
        return ":" + name

    rendered = re.sub(r"\$\{(\w+)\}", repl, sql)
    return rendered, {k: params[k] for k in used}
