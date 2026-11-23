import re

from odf.apistudio.compiler import AGGREGATES, OPS
from odf.apistudio.content import validate_content
from odf.models import Asset, AssetVersion

_ALIAS = re.compile(r"^\w+$", re.UNICODE)
METRIC_AGGS = AGGREGATES | {"count_distinct"}


def empty_dataset():
    return {"mode": "visual", "query": None, "sql": None,
            "params": [], "auth": None}


def empty_metric():
    return {"dataset_id": None,
            "measure": {"agg": "sum", "column": "", "as": "value"},
            "dimensions": [], "filters": [],
            "format": {"type": "number", "unit": "", "decimals": 2}}


def _err(field, message):
    return {"field": field, "message": message}


def _published_dataset(session, dataset_id, project_id):
    a = session.get(Asset, dataset_id) if dataset_id else None
    if not a or a.type != "dataset":
        return None, _err("dataset_id", "dataset not found")
    if a.project_id != project_id:
        return None, _err("dataset_id", "dataset is outside the project")
    if not a.published_version_id:
        return None, _err("dataset_id", "dataset is not published")
    v = session.get(AssetVersion, a.published_version_id)
    if not v:
        return None, _err("dataset_id", "dataset version not found")
    return v.content_json, None


def validate_dataset(session, content, project_id):
    if not isinstance(content, dict):
        return [_err("content", "content must be an object")]
    mode = content.get("mode")
    if mode == "sql":
        errs = validate_content(session, content, project_id)
        if errs:
            return errs
        if content.get("params"):
            return [_err("params",
                         "SQL datasets do not support parameters; use an API")]
        try:
            content["columns"] = derive_sql_columns(session, content,
                                                    project_id)
        except ValueError as exc:
            return [_err("sql", str(exc)[:300])]
        if not content["columns"]:
            return [_err("sql", "SQL dataset returned no columns")]
        return []
    if mode != "visual":
        return [_err("mode", "dataset mode must be visual or sql")]
    errs = validate_content(session, content, project_id)
    if errs:
        return errs
    query = content.get("query")
    if not isinstance(query, dict):
        return [_err("query", "visual mode requires query")]
    names = []
    for item in query.get("select") or []:
        if not isinstance(item, dict):
            return [_err("query.select", "select item must be an object")]
        if item.get("agg"):
            return [_err("query.select",
                         "dataset select does not support aggregates")]
        names.append(item.get("as") or item.get("column"))
    if len(names) != len(set(names)):
        return [_err("query.select", "duplicate output column")]
    return []


def derive_sql_columns(session, content, project_id):
    from odf.apistudio.compiler import render_sql
    from odf.models import Datasource
    from odf.services.query import execute_query
    from odf.services.sqldialect import limited
    ds_id = (content.get("query") or {}).get("datasource_id")
    ds = session.get(Datasource, ds_id) if ds_id else None
    if not ds or ds.project_id != project_id:
        raise ValueError("datasource does not belong to project")
    sql, binds = render_sql(content.get("sql") or "", [], {})
    result = execute_query(session, ds, limited(sql, ds.kind, 1), binds, 1)
    return [{"name": name, "type": "unknown"}
            for name in result.get("columns") or []]


def dataset_output_columns(content):
    if content.get("mode") == "sql":
        return [c.get("name") for c in content.get("columns") or []
                if isinstance(c, dict) and c.get("name")]
    out = []
    query = content.get("query") or {}
    for item in query.get("select") or []:
        if isinstance(item, dict):
            out.append(item.get("as") or item.get("column"))
    return out


def validate_metric(session, content, project_id):
    if not isinstance(content, dict):
        return [_err("content", "content must be an object")]
    ds_content, err = _published_dataset(
        session, content.get("dataset_id"), project_id)
    if err:
        return [err]
    ds_errs = validate_content(session, ds_content, project_id)
    if ds_errs:
        return [_err("dataset_id", "dataset is invalid")]
    names = dataset_output_columns(ds_content)
    errs = []
    measure = content.get("measure")
    if not isinstance(measure, dict):
        return [_err("measure", "measure must be an object")]
    agg = measure.get("agg")
    col = measure.get("column")
    if not isinstance(agg, str) or agg not in METRIC_AGGS:
        errs.append(_err("measure.agg", "unsupported aggregate"))
    if not isinstance(col, str) or (col != "*" and col not in names):
        errs.append(_err("measure.column", "column not in dataset output"))
    if agg != "count" and col == "*":
        errs.append(_err("measure.column", "* is only valid for count"))
    alias = measure.get("as") or "value"
    if not isinstance(alias, str) or not _ALIAS.fullmatch(alias):
        errs.append(_err("measure.as", "invalid alias"))
    dims = content.get("dimensions") or []
    if not isinstance(dims, list):
        return [_err("dimensions", "dimensions must be an array")]
    if not all(isinstance(d, str) for d in dims):
        return [_err("dimensions", "dimensions must be strings")]
    if len(dims) != len(set(dims)):
        errs.append(_err("dimensions", "duplicate dimension"))
    for d in dims:
        if not isinstance(d, str) or d not in names:
            errs.append(_err("dimensions",
                             "column not in dataset output: %s" % d))
    if alias in dims:
        errs.append(_err("measure.as", "alias conflicts with a dimension"))
    filters = content.get("filters") or []
    if not isinstance(filters, list):
        return [_err("filters", "filters must be an array")]
    for f in filters:
        if not isinstance(f, dict):
            errs.append(_err("filters", "filter must be an object"))
            continue
        if f.get("column") not in names:
            errs.append(_err("filters", "column not in dataset output"))
        if not isinstance(f.get("op"), str) or f.get("op") not in OPS:
            errs.append(_err("filters", "unsupported operator"))
        if f.get("op") == "in":
            value = f.get("value")
            if not isinstance(value, list) or not value:
                errs.append(_err("filters", "in requires a non-empty list"))
    return errs
