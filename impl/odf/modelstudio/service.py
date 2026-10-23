import hashlib
import json
import time

from sqlalchemy import create_engine, text

from odf.apistudio.catalog import table_column_info
from odf.apistudio.compiler import compile_visual, quote_ident
from odf.apistudio.content import validate_content
from odf.apistudio.service import run_content
from odf.assets.service import get_asset
from odf.modelstudio import cache
from odf.modelstudio.content import (_published_dataset,
                                     dataset_output_columns, validate_metric)
from odf.models import AssetVersion, Datasource
from odf.services.datasource import (connect_args_for, get_dsn,
                                     prepare_connection)
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
    dsn = get_dsn(ds)
    s = get_settings()
    started = time.time()
    from sqlalchemy.exc import SQLAlchemyError
    try:
        if ds.kind == "file":
            from odf import filesource
            result = filesource.execute(ds, sql, params, max_rows)
            columns = result["columns"]
            rows = result["rows"]
        elif ds.kind == "clickhouse":
            from odf import clickhouse
            result = clickhouse.execute(ds, sql, params, max_rows)
            columns = result["columns"]
            rows = result["rows"]
        else:
            args = connect_args_for(ds.kind, dsn)
            engine = create_engine(dsn, connect_args=args)
            with engine.connect() as c:
                prepare_connection(c, engine.dialect.name,
                                   s.query_timeout_s * 1000)
                result = c.execute(text(sql), params)
                columns = list(result.keys())
                rows = [dict(r) for r in
                        result.mappings().fetchmany(max_rows)]
    except (SQLAlchemyError, ValueError) as e:
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
