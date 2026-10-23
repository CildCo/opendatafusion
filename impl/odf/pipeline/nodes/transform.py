import re
import threading

import duckdb
import pyarrow as pa

from odf.pipeline.nodes.base import Column, NodeExecutor, register_node

_OPS = {">", ">=", "<", "<=", "=", "!="}
_ALIAS = re.compile(r"^\w+$", re.UNICODE)


def _ident(name):
    if not isinstance(name, str) or not name or "\x00" in name:
        raise ValueError("invalid column name")
    return '"%s"' % name.replace('"', '""')


def _alias(name):
    if not isinstance(name, str) or not _ALIAS.fullmatch(name):
        raise ValueError("invalid column alias: %s" % name)
    return '"%s"' % name


def _known(name, table):
    names = (table.column_names if hasattr(table, "column_names")
             else [c.name for c in table.schema])
    if name not in names:
        raise ValueError("unknown column: %s" % name)


def _connect():
    return duckdb.connect(config={"enable_external_access": False,
                                  "memory_limit": "512MB"})


def _duck(table):
    con = _connect()
    con.register("input", table)
    return con


def _run_query(con, sql, params, timeout):
    timer = None
    if timeout:
        timer = threading.Timer(timeout, con.interrupt)
        timer.daemon = True
        timer.start()
    try:
        return con.execute(sql, params).to_arrow_table()
    finally:
        if timer:
            timer.cancel()
        con.close()


def _query(table, sql, params=(), timeout=None):
    return _run_query(_duck(table), sql, params, timeout)


def _query_many(tables, sql, params=(), timeout=None):
    con = _connect()
    for name, table in tables.items():
        con.register(name, table)
    return _run_query(con, sql, params, timeout)


@register_node("filter")
class FilterExecutor(NodeExecutor):
    def schema(self, inputs, config):
        return [Column(c.name, str(c.type)) for c in inputs[0].schema]

    def run(self, inputs, config, ctx):
        conds = config.get("conditions") or []
        parts, params = [], []
        for c in conds:
            op = c.get("op")
            if op not in _OPS:
                raise ValueError("unsupported operator: %s" % op)
            _known(c.get("column"), inputs[0])
            parts.append("%s %s ?" % (_ident(c["column"]), op))
            params.append(c.get("value"))
        logic = " OR " if config.get("logic") == "or" else " AND "
        where = logic.join(parts) if parts else "TRUE"
        return _query(inputs[0],
                      "SELECT * FROM input WHERE " + where, params,
                      ctx.timeout_s)


@register_node("select")
class SelectExecutor(NodeExecutor):
    def schema(self, inputs, config):
        cols = {c.name: c for c in inputs[0].schema}
        out = []
        for x in config.get("columns") or []:
            src = cols.get(x["column"])
            if src:
                out.append(Column(x.get("as") or x["column"], str(src.type)))
        return out

    def run(self, inputs, config, ctx):
        exprs = []
        for x in config.get("columns") or []:
            src = x.get("column")
            _known(src, inputs[0])
            alias = x.get("as")
            target = _alias(alias) if alias else _ident(src)
            exprs.append("%s AS %s" % (_ident(src), target))
        if not exprs:
            raise ValueError("select requires at least one column")
        return _query(inputs[0], "SELECT %s FROM input" % ", ".join(exprs),
                      timeout=ctx.timeout_s)


@register_node("rename")
class RenameExecutor(NodeExecutor):
    def schema(self, inputs, config):
        mapping = config.get("mapping") or {}
        return [Column(mapping.get(c.name, c.name), str(c.type))
                for c in inputs[0].schema]

    def run(self, inputs, config, ctx):
        mapping = config.get("mapping") or {}
        for src in mapping:
            _known(src, inputs[0])
        exprs = []
        for c in inputs[0].column_names:
            target = mapping.get(c, c)
            exprs.append("%s AS %s" % (
                _ident(c), _alias(target) if c in mapping else _ident(c)))
        return _query(inputs[0], "SELECT %s FROM input" % ", ".join(exprs),
                      timeout=ctx.timeout_s)


@register_node("cast")
class CastExecutor(NodeExecutor):
    _SQL = {"text": "VARCHAR", "int": "BIGINT",
            "float": "DOUBLE", "bool": "BOOLEAN"}

    def schema(self, inputs, config):
        mapping = config.get("mapping") or {}
        return [Column(c.name, mapping.get(c.name, str(c.type)))
                for c in inputs[0].schema]

    def run(self, inputs, config, ctx):
        mapping = config.get("mapping") or {}
        for src, typ in mapping.items():
            _known(src, inputs[0])
            if typ not in self._SQL:
                raise ValueError("unsupported cast type: %s" % typ)
        parts = []
        for c in inputs[0].column_names:
            if c in mapping:
                parts.append("CAST(%s AS %s) AS %s"
                             % (_ident(c), self._SQL[mapping[c]], _ident(c)))
            else:
                parts.append(_ident(c))
        return _query(inputs[0], "SELECT %s FROM input" % ", ".join(parts),
                      timeout=ctx.timeout_s)


def _join_plan(left, right, config):
    on = config.get("on") or []
    right_keys = {x.get("right") for x in on}
    suffix = config.get("suffix") or "_right"
    out = [("left", c.name, c.name, str(c.type)) for c in left.schema]
    used = {c.name for c in left.schema}
    for c in right.schema:
        if c.name in right_keys:
            continue
        name = c.name
        if name in used:
            name = c.name + suffix
            while name in used:
                name += "_"
        used.add(name)
        out.append(("right", c.name, name, str(c.type)))
    return out


@register_node("join")
class JoinExecutor(NodeExecutor):
    _HOW = {"inner": "JOIN", "left": "LEFT JOIN",
            "right": "RIGHT JOIN", "full": "FULL OUTER JOIN"}

    def schema(self, inputs, config):
        if len(inputs) != 2:
            raise ValueError("join requires two inputs")
        how = config.get("how") or "inner"
        if how not in self._HOW:
            raise ValueError("unsupported join type: %s" % how)
        on = config.get("on") or []
        if not on:
            raise ValueError("join requires at least one key")
        for pair in on:
            _known(pair.get("left"), inputs[0])
            _known(pair.get("right"), inputs[1])
        return [Column(name, typ) for _, _, name, typ
                in _join_plan(inputs[0], inputs[1], config)]

    def run(self, inputs, config, ctx):
        if len(inputs) != 2:
            raise ValueError("join requires two inputs")
        left, right = inputs
        how = config.get("how") or "inner"
        if how not in self._HOW:
            raise ValueError("unsupported join type: %s" % how)
        on = config.get("on") or []
        if not on:
            raise ValueError("join requires at least one key")
        conds = []
        for pair in on:
            lk, rk = pair.get("left"), pair.get("right")
            _known(lk, left)
            _known(rk, right)
            conds.append("l.%s = r.%s" % (_ident(lk), _ident(rk)))
        exprs = []
        for side, col, name, _ in _join_plan(left, right, config):
            exprs.append("%s.%s AS %s"
                         % ("l" if side == "left" else "r",
                            _ident(col), _ident(name)))
        sql = ("SELECT %s FROM input_left l %s input_right r ON %s"
               % (", ".join(exprs), self._HOW[how], " AND ".join(conds)))
        return _query_many({"input_left": left, "input_right": right},
                           sql, timeout=ctx.timeout_s)


_AGGS = {"sum": "SUM", "count": "COUNT", "avg": "AVG",
         "min": "MIN", "max": "MAX"}


@register_node("aggregate")
class AggregateExecutor(NodeExecutor):
    def schema(self, inputs, config):
        table = inputs[0]
        cols = {c.name: c for c in table.schema}
        out = []
        for g in config.get("group_by") or []:
            _known(g, table)
            out.append(Column(g, str(cols[g].type), False))
        for a in config.get("aggregates") or []:
            agg = a.get("agg")
            if agg not in _AGGS:
                raise ValueError("unsupported aggregate: %s" % agg)
            col = a.get("column", "")
            if not (col == "*" and agg == "count"):
                _known(col, table)
            explicit = a.get("as")
            alias = explicit or ("count" if col == "*" else col)
            if explicit:
                _alias(explicit)
            out.append(Column(alias, "double"))
        names = [c.name for c in out]
        if len(names) != len(set(names)):
            raise ValueError("aggregate output names must be unique")
        return out

    def run(self, inputs, config, ctx):
        table = inputs[0]
        group = config.get("group_by") or []
        aggs = config.get("aggregates") or []
        if not group and not aggs:
            raise ValueError("aggregate requires group_by or aggregates")
        for g in group:
            _known(g, table)
        exprs = [_ident(g) for g in group]
        for a in aggs:
            agg = a.get("agg")
            if agg not in _AGGS:
                raise ValueError("unsupported aggregate: %s" % agg)
            col = a.get("column")
            if col == "*" and agg == "count":
                inner = "*"
            else:
                _known(col, table)
                inner = _ident(col)
            explicit = a.get("as")
            alias = explicit or ("count" if col == "*" else col)
            alias_sql = _alias(alias) if explicit else _ident(alias)
            exprs.append("%s(%s) AS %s"
                         % (_AGGS[agg], inner, alias_sql))
        names = list(group) + [
            (a.get("as") or ("count" if a.get("column") == "*"
                             else a.get("column")))
            for a in aggs]
        if len(names) != len(set(names)):
            raise ValueError("aggregate output names must be unique")
        sql = "SELECT %s FROM input" % ", ".join(exprs)
        if group:
            sql += " GROUP BY " + ", ".join(_ident(g) for g in group)
        return _query(table, sql, timeout=ctx.timeout_s)


@register_node("union")
class UnionExecutor(NodeExecutor):
    def schema(self, inputs, config):
        if len(inputs) != 2:
            raise ValueError("union requires two inputs")
        left, right = inputs
        cols = config.get("columns") or [
            {"name": c.name, "left": c.name, "right": c.name}
            for c in left.schema]
        by_left = {c.name: c for c in left.schema}
        out = []
        for c in cols:
            lk, rk = c.get("left"), c.get("right")
            _known(lk, left)
            _known(rk, right)
            src = by_left.get(lk)
            out.append(Column(c["name"], str(src.type) if src else "unknown"))
        names = [c["name"] for c in cols]
        if len(names) != len(set(names)):
            raise ValueError("union output names must be unique")
        return out

    def run(self, inputs, config, ctx):
        if len(inputs) != 2:
            raise ValueError("union requires two inputs")
        left, right = inputs
        cols = config.get("columns") or [
            {"name": c, "left": c, "right": c} for c in left.column_names]
        names = [c["name"] for c in cols]
        if len(names) != len(set(names)):
            raise ValueError("union output names must be unique")
        left_exprs, right_exprs = [], []
        for c in cols:
            lk, rk = c.get("left"), c.get("right")
            _known(lk, left)
            _known(rk, right)
            left_exprs.append("%s AS %s" % (_ident(lk), _ident(c["name"])))
            right_exprs.append("%s AS %s" % (_ident(rk), _ident(c["name"])))
        op = "UNION ALL" if config.get("all", True) else "UNION"
        sql = ("SELECT %s FROM input_left %s SELECT %s FROM input_right"
               % (", ".join(left_exprs), op, ", ".join(right_exprs)))
        return _query_many({"input_left": left, "input_right": right},
                           sql, timeout=ctx.timeout_s)


@register_node("dedupe")
class DedupeExecutor(NodeExecutor):
    def schema(self, inputs, config):
        keys = config.get("keys") or []
        if not keys:
            raise ValueError("dedupe requires keys")
        for k in keys:
            _known(k, inputs[0])
        order = config.get("order_by") or {}
        if order.get("column"):
            _known(order["column"], inputs[0])
            if (order.get("dir") or "asc").lower() not in ("asc", "desc"):
                raise ValueError("invalid order direction")
        return [Column(c.name, str(c.type), c.nullable)
                for c in inputs[0].schema]

    def run(self, inputs, config, ctx):
        table = inputs[0]
        keys = config.get("keys") or []
        if not keys:
            raise ValueError("dedupe requires keys")
        for k in keys:
            _known(k, table)
        order = config.get("order_by") or {}
        exclude = "__rn"
        if order.get("column"):
            _known(order["column"], table)
            direction = (order.get("dir") or "asc").upper()
            if direction not in ("ASC", "DESC"):
                raise ValueError("invalid order direction")
            if config.get("keep") == "last":
                direction = "DESC" if direction == "ASC" else "ASC"
            order_sql = "%s %s" % (_ident(order["column"]), direction)
        else:
            table = table.append_column(
                "__odf_ord", pa.array(range(table.num_rows), type=pa.int64()))
            order_sql = "\"__odf_ord\" " + (
                "DESC" if config.get("keep") == "last" else "ASC")
            exclude += '", "__odf_ord'
        partition = ", ".join(_ident(k) for k in keys)
        sql = ("SELECT * EXCLUDE (\"%s\") FROM ("
               "SELECT *, ROW_NUMBER() OVER (PARTITION BY %s ORDER BY %s) "
               "AS \"__rn\" FROM input) WHERE \"__rn\" = 1"
               % (exclude, partition, order_sql))
        return _query(table, sql, timeout=ctx.timeout_s)


@register_node("quality")
class QualityExecutor(NodeExecutor):
    def schema(self, inputs, config):
        rules = config.get("rules") or []
        if not rules:
            raise ValueError("quality requires rules")
        for r in rules:
            if r.get("op") not in _OPS:
                raise ValueError("unsupported operator: %s" % r.get("op"))
            _known(r.get("column"), inputs[0])
        return [Column(c.name, str(c.type), c.nullable)
                for c in inputs[0].schema]

    def run(self, inputs, config, ctx):
        table = inputs[0]
        rules = config.get("rules") or []
        if not rules:
            raise ValueError("quality requires rules")
        parts, params = [], []
        for r in rules:
            if r.get("op") not in _OPS:
                raise ValueError("unsupported operator: %s" % r.get("op"))
            _known(r.get("column"), table)
            parts.append("%s %s ?" % (_ident(r["column"]), r["op"]))
            params.append(r.get("value"))
        logic = " OR " if config.get("logic") == "or" else " AND "
        passing = _query(table,
                         "SELECT * FROM input WHERE " + logic.join(parts),
                         params, ctx.timeout_s)
        failed = table.num_rows - passing.num_rows
        if failed and (config.get("on_fail") or "fail") == "fail":
            raise ValueError("quality failed: %d rows" % failed)
        return passing
