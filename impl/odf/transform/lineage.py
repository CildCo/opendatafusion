import sqlglot
from sqlglot import exp

from odf.transform.content import REF, IDENT, ref_assets


def _parse(sql):
    try:
        return sqlglot.parse_one(sql)
    except Exception:
        raise ValueError("could not parse SQL for column inference")


def _quoted_key(asset):
    return asset.key


def _projections(expression):
    if not isinstance(expression, exp.Select):
        raise ValueError("column inference needs a single SELECT statement")
    return expression.expressions


def infer_columns(session, asset, content):
    parents = ref_assets(session, content, asset.project_id, asset.id)
    by_name = {}
    for parent in parents:
        by_name[parent.key] = parent
        by_name[parent.name] = parent

    def replace(match):
        name = match.group(1).strip()
        parent = by_name.get(name)
        if parent is None:
            raise ValueError("unknown model reference: %s" % name)
        return _quoted_key(parent)

    sql = REF.sub(replace, content.get("sql") or "")
    expression = _parse(sql)
    parents_by_key = {parent.key: parent for parent in parents}
    table_parents = {}
    for table in expression.find_all(exp.Table):
        parent = parents_by_key.get(table.name)
        if parent is None:
            continue
        table_parents[table.name] = parent
        if table.alias_or_name:
            table_parents[table.alias_or_name] = parent
    single = parents[0] if len(parents) == 1 else None

    inferred = {}
    for item in _projections(expression):
        if isinstance(item, exp.Star):
            continue
        name = item.alias_or_name
        if not isinstance(name, str) or not IDENT.match(name):
            continue
        columns = [column for column in item.find_all(exp.Column)
                   if column.name and column.name != "*"]
        source = ""
        if len(columns) == 1:
            column = columns[0]
            parent = table_parents.get(column.table) if column.table else None
            if parent is None and single is not None:
                parent = single
            if parent is not None:
                source = "%s.%s" % (parent.key, column.name)
        if name not in inferred:
            inferred[name] = {"name": name, "type": "", "source": source,
                              "description": ""}

    existing = {}
    for column in content.get("columns") or []:
        if isinstance(column, dict) and \
                isinstance(column.get("name"), str):
            existing[column["name"]] = dict(column)

    out, used = [], set()
    for name, found in inferred.items():
        current = existing.get(name)
        if current:
            merged = dict(current)
            if not merged.get("source") and found["source"]:
                merged["source"] = found["source"]
            out.append(merged)
        else:
            out.append(found)
        used.add(name)
    for name, current in existing.items():
        if name not in used:
            out.append(current)
    return out
