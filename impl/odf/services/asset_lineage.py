def _version_content(session, asset):
    from odf.models import AssetVersion
    version_id = asset.published_version_id or asset.draft_version_id
    version = session.get(AssetVersion, version_id) if version_id else None
    return (version.content_json or {}) if version else {}


def _asset_node_id(asset):
    return "%s:%d" % (asset.type, asset.id)


def _table_ref(content):
    query = content.get("query") or {}
    datasource_id = query.get("datasource_id")
    table = query.get("table")
    if not isinstance(datasource_id, int) or not table:
        return None, None
    return "%d:%s" % (datasource_id, table), table


def _parent_assets(session, asset, content):
    from odf.models import Asset
    ids = []
    if asset.type == "metric":
        dataset_id = content.get("dataset_id")
        if isinstance(dataset_id, int):
            ids.append(dataset_id)
    elif asset.type == "dashboard":
        for widget in content.get("widgets") or []:
            if not isinstance(widget, dict):
                continue
            for key in ("dataset_id", "metric_id"):
                value = widget.get(key)
                if isinstance(value, int) and value not in ids:
                    ids.append(value)
    parents = []
    for parent_id in ids:
        parent = session.get(Asset, parent_id)
        if parent and parent.project_id == asset.project_id:
            parents.append(parent)
    return parents


def _select_columns(content):
    query = content.get("query") or {}
    out = []
    for item in query.get("select") or []:
        if not isinstance(item, dict):
            continue
        column = item.get("column")
        if column and column != "*":
            out.append((column, item.get("as") or column))
    return out


def asset_lineage(session, project_id, asset_id):
    from odf.models import Asset, LineageEdge
    root = session.get(Asset, asset_id)
    if not root or root.project_id != project_id:
        return None

    nodes, node_ids, edges, edge_keys = [], set(), [], set()
    visited_assets, visited_tables = set(), set()

    def add_node(node_id, kind, name):
        if node_id in node_ids:
            return
        node_ids.add(node_id)
        nodes.append({"id": node_id, "type": kind, "name": name})

    def add_edge(source, target, source_type, target_type):
        key = (source, target)
        if key in edge_keys:
            return
        edge_keys.add(key)
        edges.append({"from": source, "to": target,
                      "from_type": source_type, "to_type": target_type})

    def walk_table(table_ref, table, depth=0):
        add_node(table_ref, "table", table)
        if table_ref in visited_tables or depth >= 6:
            return
        visited_tables.add(table_ref)
        rows = (session.query(LineageEdge)
                .filter(LineageEdge.project_id == project_id,
                        LineageEdge.to_ref == table_ref,
                        LineageEdge.from_column.is_(None)).all())
        for row in rows:
            add_node(row.from_ref, row.from_type or "table", row.from_ref)
            add_edge(row.from_ref, table_ref, row.from_type or "table",
                     "table")
            walk_table(row.from_ref, row.from_ref, depth + 1)

    def walk(asset):
        if asset.id in visited_assets:
            return
        visited_assets.add(asset.id)
        node_id = _asset_node_id(asset)
        add_node(node_id, asset.type, asset.name)
        content = _version_content(session, asset)
        if asset.type in ("dataset", "api", "pipeline"):
            table_ref, table = _table_ref(content)
            if table_ref:
                walk_table(table_ref, table)
                add_edge(table_ref, node_id, "table", asset.type)
        if asset.type == "pipeline":
            rows = (session.query(LineageEdge)
                    .filter(LineageEdge.project_id == project_id,
                            LineageEdge.to_type == "asset",
                            LineageEdge.to_id == str(asset.id),
                            LineageEdge.from_column.is_(None)).all())
            for row in rows:
                add_node(row.from_ref, row.from_type or "table", row.from_ref)
                add_edge(row.from_ref, node_id, row.from_type or "table",
                         asset.type)
                visited_tables.add(row.from_ref)
        for parent in _parent_assets(session, asset, content):
            walk(parent)
            add_edge(_asset_node_id(parent), node_id, parent.type, asset.type)

    walk(root)

    column_edges = []
    for asset_id_visited in visited_assets:
        asset = session.get(Asset, asset_id_visited)
        if not asset:
            continue
        content = _version_content(session, asset)
        node_id = _asset_node_id(asset)
        if asset.type in ("dataset", "api"):
            table_ref, _ = _table_ref(content)
            for column, alias in _select_columns(content):
                if table_ref:
                    column_edges.append({
                        "from": table_ref, "from_column": column,
                        "to": node_id, "to_column": alias})
        elif asset.type == "metric":
            dataset_id = content.get("dataset_id")
            parent = (session.get(Asset, dataset_id)
                      if isinstance(dataset_id, int) else None)
            if parent and parent.project_id == project_id:
                parent_id = _asset_node_id(parent)
                measure = content.get("measure") or {}
                column = measure.get("column")
                if column and column != "*":
                    column_edges.append({
                        "from": parent_id, "from_column": column,
                        "to": node_id,
                        "to_column": measure.get("as") or column})
                from odf.modelstudio.content import metric_dimensions
                for dimension in metric_dimensions(content):
                    column_edges.append({
                        "from": parent_id, "from_column": dimension,
                        "to": node_id, "to_column": dimension})

    if visited_tables:
        rows = (session.query(LineageEdge)
                .filter(LineageEdge.project_id == project_id,
                        LineageEdge.from_column.isnot(None)).all())
        for row in rows:
            if row.from_ref not in visited_tables \
                    and row.to_ref not in visited_tables:
                continue
            column_edges.append({
                "from": row.from_ref, "from_column": row.from_column,
                "to": row.to_ref, "to_column": row.to_column})

    deduped, seen = [], set()
    for row in column_edges:
        key = (row["from"], row["from_column"], row["to"], row["to_column"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)

    return {"asset_id": root.id, "asset_name": root.name, "type": root.type,
            "nodes": nodes, "edges": edges, "column_edges": deduped}
