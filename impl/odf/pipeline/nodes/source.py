import re
from datetime import date, datetime

import pyarrow as pa

from odf.apistudio.catalog import table_column_info
from odf.connectors.factory import source_for
from odf.models import Datasource
from odf.pipeline.nodes.base import Column, NodeExecutor, register_node


def _norm(value) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


_DATE_ONLY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _within(value, until) -> bool:
    if value is None or until is None:
        return False
    boundary = str(until).strip()
    if _DATE_ONLY.match(boundary):
        bound = date.fromisoformat(boundary)
        if isinstance(value, datetime):
            return value.date() <= bound
        if isinstance(value, date):
            return value <= bound
        try:
            return date.fromisoformat(str(value)[:10]) <= bound
        except ValueError:
            pass
    try:
        return float(value) <= float(boundary)
    except (TypeError, ValueError):
        pass
    try:
        left = value if isinstance(value, datetime) else datetime.fromisoformat(
            str(value).replace("Z", "+00:00"))
        right = datetime.fromisoformat(boundary.replace("Z", "+00:00"))
        try:
            return left <= right
        except TypeError:
            return left.replace(tzinfo=None) <= right.replace(tzinfo=None)
    except (TypeError, ValueError):
        pass
    return _norm(value) <= boundary


def _arrow_type(sqltype):
    text = str(sqltype).lower()
    if "bool" in text:
        return pa.bool_()
    if any(x in text for x in ("int", "serial")):
        return pa.int64()
    if any(x in text for x in ("numeric", "decimal", "real", "double",
                               "float")):
        return pa.float64()
    if "timestamp" in text or "datetime" in text:
        return pa.timestamp("us")
    if "date" in text:
        return pa.date32()
    return pa.string()


@register_node("source")
class SourceExecutor(NodeExecutor):
    def schema(self, inputs, config):
        return []

    def run(self, inputs, config, ctx):
        from odf.connectors.sql import format_cursor
        ds = ctx.session.get(Datasource, config["datasource_id"])
        nid = ctx.current_node
        col = config.get("cursor_column")
        dag = {"source_table": config["table"],
               "pk": config.get("pk", "id"), "cursor_column": col}
        src = source_for(ds, dag)
        start = ctx.cursor_override.get(nid, ctx.cursors.get(nid))
        rows, cursor = src.read(start, ctx.batch)
        if ctx.until_cursor and col:
            keep = [r for r in rows
                    if r.get(col) is not None
                    and _within(r[col], ctx.until_cursor)]
            if len(keep) != len(rows):
                ctx.exhausted_nodes.add(nid)
            if keep:
                last = keep[-1]
                cursor = format_cursor(last[col], last.get(
                    config.get("pk", "id")))
            else:
                cursor = start
                ctx.exhausted_nodes.add(nid)
            rows = keep
        if not rows:
            ctx.exhausted_nodes.add(nid)
        if nid:
            ctx.new_cursors[nid] = cursor
        if not rows:
            try:
                info = table_column_info(ctx.session, ds, config["table"])
                return pa.table({
                    c["name"]: pa.array([], type=_arrow_type(c["type"]))
                    for c in info})
            except Exception:
                return pa.table({})
        return pa.Table.from_pylist(rows)
