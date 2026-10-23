from sqlalchemy import and_, or_

from odf.apistudio.catalog import table_column_info


def _ensure(session, project_id, from_type, from_id, from_ref,
            to_type, to_id, to_ref, from_column=None, to_column=None,
            asset_id=None):
    from odf.models import LineageEdge
    row = (session.query(LineageEdge)
           .filter_by(project_id=project_id, from_type=from_type,
                      from_id=from_id, to_type=to_type, to_id=to_id,
                      from_column=from_column, to_column=to_column,
                      asset_id=asset_id)
           .first())
    if row:
        return False
    session.add(LineageEdge(project_id=project_id, asset_id=asset_id,
                            from_type=from_type,
                            from_id=from_id, from_ref=from_ref,
                            to_type=to_type, to_id=to_id, to_ref=to_ref,
                            from_column=from_column, to_column=to_column))
    return True


def _table(asset, node, session):
    from odf.models import Datasource
    config = node.get("config") or {}
    ds_id = config.get("datasource_id")
    table = config.get("table")
    ds = session.get(Datasource, ds_id) if ds_id else None
    if not ds or not table or ds.project_id != asset.project_id:
        return None
    return ds, "%s:%s" % (ds.id, table)


def _pass(mapping):
    return {name: set(origins) for name, origins in mapping.items()}


def _union_map(left, right, config):
    cols = config.get("columns")
    if cols:
        return {c["name"]: set(left.get(c.get("left"), set()))
                | set(right.get(c.get("right"), set())) for c in cols}
    return {name: set(left.get(name, set())) | set(right.get(name, set()))
            for name in set(left) | set(right)}


def _derive_columns(session, asset, content):
    from odf.pipeline.schema import input_edges, topo_order
    from odf.pipeline.schema_service import content_schemas
    nodes = {n["id"]: n for n in content.get("nodes") or []
             if isinstance(n, dict) and isinstance(n.get("id"), str)}
    schema_rows = content_schemas(session, content, asset.project_id)
    schemas = {n["node_id"]: [c["name"] for c in n["columns"]]
               for n in schema_rows}
    maps, edges = {}, set()
    for nid in topo_order(content):
        node = nodes[nid]
        typ = node["type"]
        config = node.get("config") or {}
        incoming = [e["from"] for e in input_edges(content, nid)
                    if e["from"] in maps]
        inmap = maps[incoming[0]] if incoming else {}
        if typ == "source":
            got = _table(asset, node, session)
            if not got:
                maps[nid] = {}
                continue
            ds, ref = got
            cols = table_column_info(session, ds, config.get("table"))
            maps[nid] = {c["name"]: {(ref, c["name"])} for c in cols}
        elif typ == "select":
            out = {}
            for item in config.get("columns") or []:
                src = item.get("column")
                name = item.get("as") or src
                out[name] = set(inmap.get(src, set()))
            maps[nid] = out
        elif typ == "rename":
            mapping = config.get("mapping") or {}
            maps[nid] = {mapping.get(name, name): set(origins)
                         for name, origins in inmap.items()}
        elif typ == "join" and len(incoming) == 2:
            left, right = maps[incoming[0]], maps[incoming[1]]
            right_keys = {x.get("right") for x in config.get("on") or []}
            suffix = config.get("suffix") or "_right"
            out = _pass(left)
            used = set(out)
            for name, origins in right.items():
                if name in right_keys:
                    continue
                target = name
                if target in used:
                    target = name + suffix
                    while target in used:
                        target += "_"
                used.add(target)
                out[target] = set(origins)
            maps[nid] = out
        elif typ == "union" and len(incoming) == 2:
            maps[nid] = _union_map(maps[incoming[0]], maps[incoming[1]],
                                   config)
        elif typ == "aggregate":
            out = {}
            for group in config.get("group_by") or []:
                out[group] = set(inmap.get(group, set()))
            for item in config.get("aggregates") or []:
                col = item.get("column")
                alias = item.get("as") or (
                    "count" if col == "*" else col)
                out[alias] = set(inmap.get(col, set())) if col != "*" else set()
            maps[nid] = out
        elif typ == "sink":
            got = _table(asset, node, session)
            maps[nid] = _pass(inmap)
            if got:
                _, ref = got
                for name, origins in inmap.items():
                    for from_ref, from_col in origins:
                        edges.add((from_ref, from_col, ref, name))
        else:
            maps[nid] = _pass(inmap)
    return sorted(edges)


def record_lineage(session, asset, content):
    from odf.models import LineageEdge
    session.query(LineageEdge).filter(or_(
        LineageEdge.asset_id == asset.id,
        and_(LineageEdge.from_type == "asset",
             LineageEdge.from_id == str(asset.id)),
        and_(LineageEdge.to_type == "asset",
             LineageEdge.to_id == str(asset.id)),
    )).delete(synchronize_session=False)
    session.flush()
    count = 0
    for node in content.get("nodes") or []:
        if not isinstance(node, dict) or node.get("type") not in (
                "source", "sink"):
            continue
        got = _table(asset, node, session)
        if not got:
            continue
        _, ref = got
        if node["type"] == "source":
            count += _ensure(session, asset.project_id, "table", ref, ref,
                             "asset", str(asset.id), asset.key,
                             asset_id=asset.id)
        else:
            count += _ensure(session, asset.project_id, "asset",
                             str(asset.id), asset.key,
                             "table", ref, ref, asset_id=asset.id)
    try:
        derived = _derive_columns(session, asset, content)
    except Exception:
        derived = []
    for from_ref, from_col, to_ref, to_col in derived:
        count += _ensure(session, asset.project_id, "table", from_ref,
                         from_ref, "table", to_ref, to_ref,
                         from_column=from_col, to_column=to_col,
                         asset_id=asset.id)
    return count
