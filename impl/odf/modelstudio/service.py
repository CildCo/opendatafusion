import hashlib
import json
import time

from odf.apistudio.catalog import table_column_info
from odf.apistudio.compiler import compile_visual, quote_ident
from odf.apistudio.content import validate_content
from odf.apistudio.service import run_content
from odf.assets.service import get_asset
from odf.modelstudio import cache
from odf.modelstudio.content import (_published_dataset,
                                     dataset_output_columns, validate_metric)
from odf.models import AssetVersion, Datasource
from odf.services.query import execute_query
from odf.settings import get_settings


def _version(session, asset, published):
    if published:
        vid = asset.published_version_id
    else:
        vid = asset.draft_version_id or asset.published_version_id
    v = session.get(AssetVersion, vid) if vid else None
    if not v:
        raise ValueError("published version not found" if published
                         else "content not found")
    return v


def dataset_schema(session, asset_id, published=True):
    a = get_asset(session, asset_id)
    if not a or a.type != "dataset":
        raise ValueError("dataset not found")
    from odf.modelstudio.content import validate_dataset
    v = _version(session, a, published)
    errs = validate_dataset(session, v.content_json, a.project_id)
    if errs:
        raise ValueError("invalid dataset: %s" % errs)
    q = v.content_json["query"]
    ds = session.get(Datasource, q["datasource_id"])
    info = {c["name"]: c["type"] for c in
            table_column_info(session, ds, q["table"])}
    cols = []
    for item in q.get("select") or []:
        src = item.get("column")
        out = item.get("as") or src
        cols.append({"name": out, "type": info.get(src, "unknown")})
    return {"asset_id": asset_id, "columns": cols,
            "datasource_id": q["datasource_id"], "table": q["table"]}


def preview_dataset(session, asset_id, content=None, limit=100,
                    published_only=False, params=None, extra_filters=None,
                    role=None):
    from odf.modelstudio.content import validate_dataset
    a = get_asset(session, asset_id)
    if not a or a.type != "dataset":
        raise ValueError("dataset not found")
    if content is None:
        content = _version(session, a, published_only).content_json
    from odf.services.policies import filters_for
    all_extra = list(extra_filters or []) + filters_for(session, a.id, role)
    if all_extra:
        q = content.get("query") or {}
        content = {**content, "query": {
            **q, "filters": [*(q.get("filters") or []), *all_extra]}}
    errs = validate_dataset(session, content, a.project_id)
    if errs:
        raise ValueError("invalid dataset: %s" % errs)
    s = get_settings()
    ttl = int(s.preview_cache_ttl_s or 0)
    key = None
    if ttl > 0:
        raw = json.dumps({
            "asset": a.id,
            "version": (a.published_version_id if published_only
                        else (a.draft_version_id or a.published_version_id)),
            "content": content, "params": params or {}, "limit": limit,
            "role": role,
        }, sort_keys=True, default=str)
        key = hashlib.sha256(raw.encode()).hexdigest()
        hit = cache.get(key, "preview")
        if hit is not None:
            hit["cached"] = True
            return hit
    result = run_content(session, a, content, params or {}, limit=limit,
                         include_sql=True, role=role)
    result["cached"] = False
    if key is not None:
        cache.put(key, result, ttl, int(s.preview_cache_size or 128))
    return result


def _metric_content(session, asset, content, published_only=False):
    if content is None:
        content = _version(session, asset, published_only).content_json
    errs = validate_metric(session, content, asset.project_id)
    if errs:
        raise ValueError("invalid metric: %s" % errs)
    return content


def metric_sql(session, content, extra_filters=None,
               base_filters=None):
    ds_content, err = _published_dataset(
        session, content["dataset_id"], content.get("project_id", 0))
    if err:
        raise ValueError(err["message"])
    q = ds_content["query"]
    ds = session.get(Datasource, q["datasource_id"])
    cols = [c["name"] for c in table_column_info(session, ds, q["table"])]
    if base_filters:
        q = {**q, "filters": [*(q.get("filters") or []), *base_filters]}
    base_sql, base_binds = compile_visual(q, cols, {}, limit_override=0)
    measure = content["measure"]
    agg = measure["agg"].upper()
    col = measure["column"]
    expr = "COUNT(*)" if col == "*" else "%s(%s)" % (agg, quote_ident(col))
    alias = measure.get("as") or "value"
    dims = content.get("dimensions") or []
    selects = [quote_ident(d) for d in dims] + [
        "%s AS %s" % (expr, quote_ident(alias))]
    params = dict(base_binds)
    where = []

    def bind_key(base):
        key, n = base, 1
        while key in params:
            key = "%s_%d" % (base, n)
            n += 1
        return key

    filters = list(content.get("filters") or []) + list(extra_filters or [])
    for i, f in enumerate(filters):
        col_sql = quote_ident(f["column"])
        op = f["op"]
        if op in ("is null", "is not null"):
            where.append("%s %s" % (col_sql, op.upper()))
            continue
        value = f.get("value")
        if op == "in":
            values = value if isinstance(value, list) else [value]
            if not values:
                raise ValueError("in requires at least one value")
            keys = []
            for j, item in enumerate(values):
                key = bind_key("m%d_%d" % (i, j))
                params[key] = item
                keys.append(":" + key)
            where.append("%s IN (%s)" % (col_sql, ", ".join(keys)))
            continue
        key = bind_key("m%d" % i)
        params[key] = value
        where.append("%s %s :%s" % (col_sql, op, key))
    sql = "SELECT %s FROM (%s) AS base" % (", ".join(selects), base_sql)
    if where:
        sql += " WHERE " + " AND ".join(where)
    if dims:
        sql += " GROUP BY " + ", ".join(quote_ident(d) for d in dims)
    return sql, params


def _execute_metric(session, content, ds_content, ds, sql, params,
                    max_rows, role):
    started = time.time()
    try:
        result = execute_query(session, ds, sql, params, max_rows)
        columns = result["columns"]
        rows = result["rows"]
    except ValueError as e:
        raise ValueError(str(e))
    from odf.services.masking import apply_metric_masks
    rows = apply_metric_masks(session, ds_content, rows,
                              content.get("dimensions") or [],
                              content["measure"].get("as") or "value",
                              content["measure"].get("column"), role)
    return {"columns": columns, "rows": rows, "row_count": len(rows),
            "ms": int((time.time() - started) * 1000), "sql": sql}


def query_metric(session, asset_id, content=None, limit=100,
                 published_only=False, extra_filters=None, role=None):
    a = get_asset(session, asset_id)
    if not a or a.type != "metric":
        raise ValueError("metric not found")
    content = _metric_content(session, a, content, published_only)
    content = {**content, "project_id": a.project_id}
    from odf.services.policies import filters_for
    base_filters = filters_for(session, content["dataset_id"], role)
    sql, params = metric_sql(session, content, extra_filters, base_filters)
    ds_content, _ = _published_dataset(session, content["dataset_id"],
                                       a.project_id)
    ds = session.get(Datasource, ds_content["query"]["datasource_id"])
    s = get_settings()
    max_rows = max(1, min(int(limit), s.query_max_rows))
    ttl = int(s.metric_cache_ttl_s or 0)
    key = None
    if ttl > 0:
        raw = json.dumps({
            "asset": a.id, "version": a.published_version_id,
            "sql": sql, "params": params, "role": role,
            "max_rows": max_rows,
        }, sort_keys=True, default=str)
        key = hashlib.sha256(raw.encode()).hexdigest()
        hit = cache.get(key, "metric")
        if hit is not None:
            hit["cached"] = True
            return hit
    result = _execute_metric(session, content, ds_content, ds, sql, params,
                             max_rows, role)
    result["cached"] = False
    if key is not None:
        cache.put(key, result, ttl, int(s.metric_cache_size or 128))
    return result


def _metric_usage(session, project_id, metric_id):
    from odf.models import Asset
    out = []
    assets = (session.query(Asset)
              .filter(Asset.project_id == project_id,
                      Asset.type.in_(("dashboard", "app"))).all())
    for asset in assets:
        published = False
        content = None
        if asset.published_version_id:
            version = session.get(AssetVersion, asset.published_version_id)
            if version:
                content = version.content_json
                published = True
        if content is None and asset.draft_version_id:
            version = session.get(AssetVersion, asset.draft_version_id)
            if version:
                content = version.content_json
        if content is None:
            continue
        if _mentions_metric(content, metric_id):
            out.append({"id": asset.id, "name": asset.name,
                        "type": asset.type, "published": published})
    return out


def _mentions_metric(node, metric_id):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "metric_id" and value == metric_id:
                return True
            if _mentions_metric(value, metric_id):
                return True
    elif isinstance(node, list):
        for item in node:
            if _mentions_metric(item, metric_id):
                return True
    return False


def metric_catalog(session, project_id):
    from odf.models import Asset
    metrics = (session.query(Asset)
               .filter_by(project_id=project_id, type="metric")
               .order_by(Asset.id).all())
    rows = []
    for metric in metrics:
        content = {}
        if metric.published_version_id:
            version = session.get(AssetVersion, metric.published_version_id)
            if version:
                content = version.content_json or {}
        if not content and metric.draft_version_id:
            version = session.get(AssetVersion, metric.draft_version_id)
            if version:
                content = version.content_json or {}
        dataset_id = content.get("dataset_id")
        dataset = (session.get(Asset, dataset_id)
                   if isinstance(dataset_id, int) else None)
        usage = _metric_usage(session, project_id, metric.id)
        owner = metric.owner
        if (owner or "").isdigit():
            from odf.models import User
            user = session.get(User, int(owner))
            if user:
                owner = user.username
        rows.append({
            "id": metric.id, "key": metric.key, "name": metric.name,
            "published": metric.published_version_id is not None,
            "enabled": metric.enabled, "owner": owner,
            "description": metric.description,
            "dataset_id": dataset_id,
            "dataset_name": dataset.name if dataset and
            dataset.project_id == project_id else None,
            "measure": content.get("measure") or {},
            "dimensions": content.get("dimensions") or [],
            "format": content.get("format") or {},
            "usage_count": len(usage), "usage": usage,
            "has_draft": metric.draft_version_id is not None,
            "updated_at": metric.updated_at.isoformat()
            if metric.updated_at else None,
        })
    return rows


def metric_lineage(session, project_id, metric_id):
    from odf.models import Asset, Datasource, LineageEdge
    metric = session.get(Asset, metric_id)
    if not metric or metric.project_id != project_id \
            or metric.type != "metric":
        return None
    content = {}
    if metric.published_version_id:
        version = session.get(AssetVersion, metric.published_version_id)
        if version:
            content = version.content_json or {}
    if not content and metric.draft_version_id:
        version = session.get(AssetVersion, metric.draft_version_id)
        if version:
            content = version.content_json or {}
    dataset = session.get(Asset, content.get("dataset_id")) \
        if isinstance(content.get("dataset_id"), int) else None
    dataset_content = {}
    if dataset and dataset.project_id == project_id:
        if dataset.published_version_id:
            version = session.get(AssetVersion, dataset.published_version_id)
            if version:
                dataset_content = version.content_json or {}
        if not dataset_content and dataset.draft_version_id:
            version = session.get(AssetVersion, dataset.draft_version_id)
            if version:
                dataset_content = version.content_json or {}
    query = dataset_content.get("query") or {}
    datasource_id = query.get("datasource_id")
    table = query.get("table") or ""
    datasource = session.get(Datasource, datasource_id) \
        if isinstance(datasource_id, int) else None
    ref = "%d:%s" % (datasource_id, table) if datasource_id and table else ""

    edges, nodes, seen = [], [], set()

    def add_node(node_id, kind, name):
        if node_id in seen:
            return
        seen.add(node_id)
        nodes.append({"id": node_id, "type": kind, "name": name})

    queue = [(ref, 0)]
    visited = {ref}
    while ref and queue:
        current, depth = queue.pop(0)
        if depth >= 5:
            continue
        rows = (session.query(LineageEdge)
                .filter(LineageEdge.project_id == project_id,
                        LineageEdge.to_ref == current,
                        LineageEdge.from_column.is_(None)).all())
        for row in rows:
            edges.append({"from": row.from_ref, "to": row.to_ref,
                          "from_type": row.from_type,
                          "to_type": row.to_type})
            add_node(row.from_ref, row.from_type or "table", row.from_ref)
            if row.from_ref not in visited:
                visited.add(row.from_ref)
                queue.append((row.from_ref, depth + 1))

    if ref:
        add_node(ref, "table", table)
    if dataset and dataset.project_id == project_id:
        dataset_ref = "dataset:%d" % dataset.id
        add_node(dataset_ref, "dataset", dataset.name)
        if ref:
            edges.append({"from": ref, "to": dataset_ref,
                          "from_type": "table", "to_type": "dataset"})
        metric_ref = "metric:%d" % metric.id
        add_node(metric_ref, "metric", metric.name)
        edges.append({"from": dataset_ref, "to": metric_ref,
                      "from_type": "dataset", "to_type": "metric"})

    column_edges = []
    if ref:
        rows = (session.query(LineageEdge)
                .filter(LineageEdge.project_id == project_id,
                        LineageEdge.to_ref.in_(visited),
                        LineageEdge.from_column.isnot(None)).all())
        for row in rows:
            column_edges.append({
                "from": row.from_ref, "from_column": row.from_column,
                "to": row.to_ref, "to_column": row.to_column})

    return {"metric_id": metric.id, "metric_name": metric.name,
            "dataset_id": dataset.id if dataset else None,
            "dataset_name": dataset.name if dataset else None,
            "datasource_name": datasource.name if datasource else None,
            "table": table, "nodes": nodes, "edges": edges,
            "column_edges": column_edges}


def _flatten(value, prefix="", out=None):
    out = out if out is not None else {}
    if isinstance(value, dict):
        for key, item in value.items():
            _flatten(item, "%s.%s" % (prefix, key) if prefix else key, out)
    elif isinstance(value, list):
        out[prefix] = json.dumps(value, sort_keys=True)
    else:
        out[prefix] = value
    return out


def metric_diff(session, project_id, metric_id):
    from odf.models import Asset
    metric = session.get(Asset, metric_id)
    if not metric or metric.project_id != project_id \
            or metric.type != "metric":
        return None
    published = (session.get(AssetVersion, metric.published_version_id)
                 if metric.published_version_id else None)
    draft = (session.get(AssetVersion, metric.draft_version_id)
             if metric.draft_version_id else None)
    published_content = published.content_json if published else {}
    draft_content = draft.content_json if draft else published_content
    left = _flatten(published_content or {})
    right = _flatten(draft_content or {})
    keys = sorted(set(left) | set(right))
    changes = [{"key": key, "published": left.get(key),
                "draft": right.get(key)}
               for key in keys
               if json.dumps(left.get(key), sort_keys=True)
               != json.dumps(right.get(key), sort_keys=True)]
    return {"published_version": published.version if published else None,
            "draft_version": draft.version if draft else None,
            "changes": changes}


def metrics_for_dataset(session, project_id, dataset_id):
    from odf.models import Asset, Dataset, Datasource
    dataset = session.get(Dataset, dataset_id)
    if not dataset:
        return []
    datasource = session.get(Datasource, dataset.datasource_id)
    if not datasource or datasource.project_id != project_id:
        return []
    metrics = (session.query(Asset)
               .filter_by(project_id=project_id, type="metric")
               .order_by(Asset.name).all())
    out = []
    for metric in metrics:
        content = {}
        if metric.published_version_id:
            version = session.get(AssetVersion, metric.published_version_id)
            if version:
                content = version.content_json or {}
        if not content and metric.draft_version_id:
            version = session.get(AssetVersion, metric.draft_version_id)
            if version:
                content = version.content_json or {}
        source = session.get(Asset, content.get("dataset_id"))             if isinstance(content.get("dataset_id"), int) else None
        if not source or source.project_id != project_id:
            continue
        source_content = {}
        if source.published_version_id:
            version = session.get(AssetVersion, source.published_version_id)
            if version:
                source_content = version.content_json or {}
        if not source_content and source.draft_version_id:
            version = session.get(AssetVersion, source.draft_version_id)
            if version:
                source_content = version.content_json or {}
        query = source_content.get("query") or {}
        table = (query.get("table") or "").split(".")[-1]
        if (query.get("datasource_id") == dataset.datasource_id
                and table == dataset.table_name):
            out.append({"id": metric.id, "name": metric.name,
                        "key": metric.key,
                        "published": metric.published_version_id is not None})
    return out
