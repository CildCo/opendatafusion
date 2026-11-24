import hashlib
import json
import time

from odf.apistudio.catalog import table_columns
from odf.apistudio.compiler import OPS, compile_visual, quote_ident, render_sql
from odf.apistudio.params import ParamError, coerce_params
from odf.apistudio.sqlguard import ensure_read_only
from odf.assets.service import get_asset
from odf.dashboards.content import (structural_errors, validate_widget)
from odf.modelstudio import cache
from odf.modelstudio.content import (_published_dataset,
                                     dataset_output_columns,
                                     metric_dimensions)
from odf.modelstudio.service import preview_dataset, query_metric
from odf.modelstudio.timegrain import next_bucket
from odf.models import AssetVersion, Datasource
from odf.services.masking import apply_masks
from odf.services.policies import filters_for
from odf.services.query import execute_query
from odf.services.sqldialect import limited
from odf.settings import get_settings


def _resolve_filters(filters, values):
    out = []
    for f in filters or []:
        op = f.get("op")
        if op in ("is null", "is not null"):
            out.append({"column": f["column"], "op": op})
            continue
        value = values.get(f.get("param")) if f.get("param") else f.get("value")
        if value is None or value == "":
            continue
        out.append({"column": f["column"], "op": op, "value": value})
    return out


def _execute_widgets(session, content, limit, project_id=0, values=None,
                     role=None):
    values = values or {}
    out = {}
    for w in content.get("widgets") or []:
        wid = w.get("id")
        errs = validate_widget(session, content, w, project_id)
        if errs:
            out[wid] = {"columns": [], "rows": [], "row_count": 0, "ms": 0,
                        "error": "; ".join(e["message"] for e in errs)}
            continue
        filters = _resolve_filters(w.get("filters"), values)
        try:
            if w.get("type") == "text":
                out[wid] = {"columns": [], "rows": [], "row_count": 0,
                            "ms": 0, "text": w.get("text"), "error": None}
            elif w.get("type") == "table" and w.get("dataset_id"):
                r = preview_dataset(session, w["dataset_id"],
                                    limit=w.get("limit") or limit,
                                    published_only=True, params=values,
                                    extra_filters=filters, role=role)
                out[wid] = {**r, "error": None}
            else:
                r = query_metric(session, w["metric_id"],
                                 limit=w.get("limit") or limit,
                                 published_only=True,
                                 extra_filters=filters, role=role)
                out[wid] = {**r, "error": None}
        except Exception as e:
            out[wid] = {"columns": [], "rows": [], "row_count": 0,
                        "ms": 0, "error": str(e)}
    return out


def dashboard_data(session, asset_id, params=None, content=None, limit=100,
                   published_only=False, role=None):
    a = get_asset(session, asset_id)
    if not a or a.type != "dashboard":
        raise ValueError("dashboard not found")
    version_id = None
    if content is None:
        if published_only:
            version_id = a.published_version_id
        else:
            version_id = a.draft_version_id or a.published_version_id
        v = session.get(AssetVersion, version_id) if version_id else None
        if not v:
            raise ValueError("content not found")
        content = v.content_json
    errs = structural_errors(content)
    if errs:
        raise ValueError("invalid dashboard: %s" % errs)
    try:
        values = coerce_params(content.get("params") or [], params or {})
    except ParamError as e:
        raise ValueError(str(e))
    s = get_settings()
    ttl = int(s.dashboard_cache_ttl_s or 0)
    key = None
    if ttl > 0:
        raw = json.dumps({
            "asset": a.id, "version": version_id, "content": content,
            "params": values, "limit": limit, "role": role,
        }, sort_keys=True, default=str)
        key = hashlib.sha256(raw.encode()).hexdigest()
        hit = cache.get(key, "dashboard")
        if hit is not None:
            hit["cached"] = True
            return hit
    widgets = _execute_widgets(session, content, limit, a.project_id,
                               values, role)
    result = {"params": values, "widgets": widgets, "cached": False}
    if key is not None and not any(
            w.get("error") for w in widgets.values()):
        cache.put(key, result, ttl, int(s.dashboard_cache_size or 128))
    return result


def _dataset_base(session, ds_content, project_id):
    query = ds_content.get("query") or {}
    datasource = session.get(Datasource, query.get("datasource_id")) \
        if query.get("datasource_id") else None
    if not datasource or datasource.project_id != project_id:
        raise ValueError("dataset datasource not found")
    if ds_content.get("mode") == "sql":
        sql, binds = render_sql(ds_content.get("sql") or "", [], {})
        ensure_read_only(sql)
    else:
        columns = table_columns(session, datasource, query["table"])
        sql, binds = compile_visual(query, columns, {}, limit_override=0)
    return sql.strip().rstrip(";"), binds, datasource


def _filter_sql(filters, binds):
    where = []
    for index, item in enumerate(filters):
        column = quote_ident(item["column"])
        op = item.get("op")
        if op in ("is null", "is not null"):
            where.append("%s %s" % (column, op.upper()))
            continue
        if op not in OPS:
            raise ValueError("unsupported filter operator")
        if op == "in":
            values = item.get("value")
            values = values if isinstance(values, list) else [values]
            if not values:
                raise ValueError("in requires at least one value")
            keys = []
            for position, value in enumerate(values):
                key = "drill_%d_%d" % (index, position)
                binds[key] = value
                keys.append(":" + key)
            where.append("%s IN (%s)" % (column, ", ".join(keys)))
            continue
        key = "drill_%d" % index
        binds[key] = item.get("value")
        where.append("%s %s :%s" % (column, op, key))
    return where


def dashboard_drill(session, asset_id, widget_id, dimension=None, value=None,
                    params=None, limit=100, role=None):
    a = get_asset(session, asset_id)
    if not a or a.type != "dashboard":
        raise ValueError("dashboard not found")
    version_id = a.draft_version_id or a.published_version_id
    version = session.get(AssetVersion, version_id) if version_id else None
    if not version:
        raise ValueError("content not found")
    content = version.content_json
    errs = structural_errors(content)
    if errs:
        raise ValueError("invalid dashboard")
    widget = next((w for w in content.get("widgets") or []
                   if isinstance(w, dict) and w.get("id") == widget_id), None)
    if not widget:
        raise ValueError("widget not found")
    errs = validate_widget(session, content, widget, a.project_id)
    if errs:
        raise ValueError("; ".join(e["message"] for e in errs))
    metric_id = widget.get("metric_id")
    if not isinstance(metric_id, int):
        raise ValueError("widget has no metric")
    metric = get_asset(session, metric_id)
    if not metric or metric.type != "metric" \
            or metric.project_id != a.project_id \
            or not metric.published_version_id:
        raise ValueError("metric not found")
    metric_content = session.get(AssetVersion,
                                 metric.published_version_id).content_json
    dims = metric_dimensions(metric_content)
    if dimension is None:
        if widget.get("type") in ("line", "bar", "area", "pie"):
            dimension = widget.get("dimension")
        elif widget.get("type") == "pivot":
            dimension = widget.get("row_dimension")
        elif isinstance(widget.get("emit"), dict):
            dimension = widget["emit"].get("from")
    if dimension is not None and dimension not in dims:
        raise ValueError("dimension is not a metric dimension")
    values = params if isinstance(params, dict) else {}
    filters = list(metric_content.get("filters") or [])
    filters += _resolve_filters(widget.get("filters"), values)
    filters += filters_for(session, metric_content.get("dataset_id"), role)
    if dimension and value not in (None, ""):
        time_def = metric_content.get("time") or {}
        if dimension == time_def.get("column") and time_def.get("grain"):
            filters.append({"column": dimension, "op": ">=", "value": value})
            filters.append({"column": dimension, "op": "<",
                            "value": next_bucket(value,
                                                 time_def["grain"])})
        else:
            filters.append({"column": dimension, "op": "=", "value": value})
    ds_content, error = _published_dataset(
        session, metric_content.get("dataset_id"), a.project_id)
    if error:
        raise ValueError(error["message"])
    base_sql, binds, datasource = _dataset_base(session, ds_content,
                                                a.project_id)
    where = _filter_sql(filters, binds)
    sql = "SELECT * FROM (%s) AS base" % base_sql
    if where:
        sql += " WHERE " + " AND ".join(where)
    max_rows = max(1, min(int(limit), get_settings().query_max_rows))
    started = time.time()
    result = execute_query(session, datasource,
                           limited(sql, datasource.kind, max_rows),
                           binds, max_rows)
    rows = apply_masks(session, ds_content, result["rows"], role) \
        if ds_content.get("mode") == "visual" else result["rows"]
    return {"widget_id": widget_id, "dimension": dimension, "value": value,
            "columns": result["columns"], "rows": rows,
            "row_count": len(rows),
            "ms": int((time.time() - started) * 1000), "sql": sql}
