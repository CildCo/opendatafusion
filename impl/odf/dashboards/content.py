from odf.apistudio.catalog import table_columns
from odf.apistudio.compiler import OPS
from odf.apistudio.params import (ParamError, coerce_params,
                                  validate_param_defs)
from odf.modelstudio.content import (dataset_output_columns,
                                     validate_dataset, validate_metric)
from odf.models import Asset, AssetVersion, Datasource

TYPES = {"card", "line", "bar", "pie", "table", "text"}
CHART_TYPES = {"line", "bar", "pie"}
METRIC_TYPES = {"card"} | CHART_TYPES


def empty_dashboard():
    return {"columns": 12, "row_height": 80, "widgets": []}


def _err(field, message):
    return {"field": field, "message": message}


def _published(session, asset_id, type_, project_id):
    if not isinstance(asset_id, int) or isinstance(asset_id, bool):
        return None, _err("%s_id" % type_, "invalid %s id" % type_)
    a = session.get(Asset, asset_id) if asset_id else None
    if not a or a.type != type_:
        return None, _err("%s_id" % type_, "%s not found" % type_)
    if a.project_id != project_id:
        return None, _err("%s_id" % type_, "outside project")
    if not a.published_version_id:
        return None, _err("%s_id" % type_, "%s is not published" % type_)
    v = session.get(AssetVersion, a.published_version_id)
    if not v:
        return None, _err("%s_id" % type_, "version not found")
    return v.content_json, None


def _metric_columns(content):
    dims = content.get("dimensions") or []
    measure = content.get("measure") or {}
    return list(dims) + [measure.get("as") or "value"]


def structural_errors(content):
    if not isinstance(content, dict):
        return [_err("content", "content must be an object")]
    columns = content.get("columns", 12)
    row_height = content.get("row_height", 80)
    if not isinstance(columns, int) or isinstance(columns, bool) \
            or not 1 <= columns <= 24:
        return [_err("columns", "columns must be an integer 1..24")]
    if not isinstance(row_height, int) or isinstance(row_height, bool) \
            or not 20 <= row_height <= 200:
        return [_err("row_height", "row_height must be an integer 20..200")]
    widgets = content.get("widgets") or []
    if not isinstance(widgets, list):
        return [_err("widgets", "widgets must be an array")]
    errs, seen = [], set()
    params = content.get("params") or []
    if not isinstance(params, list):
        errs.append(_err("params", "params must be an array"))
    else:
        try:
            defs = validate_param_defs(params)
        except ParamError as e:
            errs.append(_err("params", str(e)))
        else:
            for p in defs:
                if p.get("default") is None:
                    continue
                try:
                    coerce_params([{**p, "required": False}], {})
                except ParamError as e:
                    errs.append(_err("params", str(e)))
    for w in widgets:
        if not isinstance(w, dict):
            errs.append(_err("widgets", "widget must be an object"))
            continue
        wid = w.get("id")
        if not isinstance(wid, str) or not wid:
            errs.append(_err("widget.id", "invalid widget id"))
            continue
        if wid in seen:
            errs.append(_err("widget.id", "duplicate widget id: %s" % wid))
        seen.add(wid)
        typ = w.get("type")
        if not isinstance(typ, str) or typ not in TYPES:
            errs.append(_err("widget.type", "unknown widget type: %s" % typ))
            continue
        for k in ("x", "y", "w", "h"):
            if not isinstance(w.get(k), int) or isinstance(w.get(k), bool):
                errs.append(_err("widget.%s" % k, "must be an integer"))
        if all(isinstance(w.get(k), int) for k in ("x", "y", "w", "h")):
            if w["x"] < 0 or w["y"] < 0 or w["w"] < 1 or w["h"] < 1:
                errs.append(_err("widget.bounds", "invalid position/size"))
            elif w["x"] + w["w"] > columns:
                errs.append(_err("widget.x", "widget exceeds grid columns"))
    return errs


def _param_names(content):
    params = content.get("params")
    if not isinstance(params, list):
        return set()
    return {p.get("name") for p in params if isinstance(p, dict)}


def _filter_errors(w, columns, param_names):
    filters = w.get("filters")
    if filters is None:
        return []
    if not isinstance(filters, list):
        return [_err("widget.filters", "filters must be an array")]
    errs = []
    for f in filters:
        if not isinstance(f, dict):
            errs.append(_err("widget.filters", "filter must be an object"))
            continue
        column = f.get("column")
        if column not in columns:
            errs.append(_err("widget.filters",
                             "column not in model output: %s" % column))
        if f.get("op") not in OPS:
            errs.append(_err("widget.filters",
                             "unsupported operator: %s" % f.get("op")))
        param = f.get("param")
        if not isinstance(param, str) or param not in param_names:
            errs.append(_err("widget.filters",
                             "param is not declared: %s" % param))
    return errs


def _emit_errors(w, columns, param_names, dimension=None):
    emit = w.get("emit")
    if emit is None:
        return []
    if not isinstance(emit, dict):
        return [_err("widget.emit", "emit must be an object")]
    errs = []
    param = emit.get("param")
    if not isinstance(param, str) or param not in param_names:
        errs.append(_err("widget.emit",
                         "param is not declared: %s" % param))
    source = emit.get("from")
    if dimension is not None:
        if source != dimension:
            errs.append(_err("widget.emit",
                             "from must equal the chart dimension"))
    elif source not in columns:
        errs.append(_err("widget.emit",
                         "from is not an output column: %s" % source))
    return errs


def validate_widget(session, content, w, project_id):
    typ = w.get("type")
    param_names = _param_names(content)
    if typ == "text":
        errs = []
        if not isinstance(w.get("text"), str) or not w["text"].strip():
            errs.append(_err("widget.text", "text is required"))
        if w.get("filters"):
            errs.append(_err("widget.text",
                             "text widgets cannot define filters"))
        if w.get("emit"):
            errs.append(_err("widget.text",
                             "text widgets cannot define emit"))
        return errs
    if typ == "table" and w.get("dataset_id") and w.get("metric_id"):
        return [_err("widget.table", "choose a dataset or a metric, not both")]
    if typ == "table":
        limit = w.get("limit", 100)
        if not isinstance(limit, int) or isinstance(limit, bool) \
                or not 1 <= limit <= 10000:
            return [_err("widget.limit", "limit must be 1..10000")]
    if typ == "table" and w.get("dataset_id"):
        ds_content, err = _published(session, w["dataset_id"], "dataset",
                                     project_id)
        if err:
            return [err]
        if validate_dataset(session, ds_content, project_id):
            return [_err("widget.dataset_id", "dataset is invalid")]
        cols = dataset_output_columns(ds_content)
        query = ds_content.get("query") or {}
        ds = session.get(Datasource, query.get("datasource_id"))
        source_cols = cols
        if ds and query.get("table"):
            try:
                source_cols = table_columns(session, ds, query["table"])
            except Exception:
                pass
        errs = _filter_errors(w, source_cols, param_names)
        errs.extend(_emit_errors(w, cols, param_names))
        return errs
    metric_content, err = _published(session, w.get("metric_id"), "metric",
                                     project_id)
    if err:
        return [err]
    if validate_metric(session, metric_content, project_id):
        return [_err("widget.metric_id", "metric is invalid")]
    errs = []
    cols = _metric_columns(metric_content)
    ds_content, _ = _published(session, metric_content.get("dataset_id"),
                               "dataset", project_id)
    filter_cols = dataset_output_columns(ds_content) if ds_content else cols
    errs.extend(_filter_errors(w, filter_cols, param_names))
    value = (w.get("value_column")
             or (metric_content.get("measure") or {}).get("as")
             or "value")
    if value not in cols:
        errs.append(_err("widget.value_column", "column not in metric output"))
    if typ in CHART_TYPES:
        dim = w.get("dimension")
        if not dim or dim not in (metric_content.get("dimensions") or []):
            errs.append(_err("widget.dimension",
                             "dimension must be a metric dimension"))
        errs.extend(_emit_errors(w, cols, param_names, dimension=dim))
    elif typ == "table":
        errs.extend(_emit_errors(w, cols, param_names))
    elif typ == "card":
        if w.get("emit"):
            errs.append(_err("widget.emit",
                             "cards cannot define emit"))
    return errs


def validate_dashboard(session, content, project_id):
    errs = structural_errors(content)
    if not isinstance(content, dict):
        return errs
    for w in content.get("widgets") or []:
        if isinstance(w, dict) and w.get("type") in TYPES:
            errs.extend(validate_widget(session, content, w, project_id))
    return errs
