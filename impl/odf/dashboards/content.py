from odf.apistudio.catalog import table_columns
from odf.apistudio.compiler import OPS
from odf.apistudio.params import (ParamError, coerce_params,
                                  validate_param_defs)
from odf.modelstudio.content import (dataset_output_columns,
                                     metric_dimensions, validate_dataset,
                                     validate_metric)
from odf.models import Asset, AssetVersion, Datasource

TYPES = {"card", "line", "bar", "area", "pie", "table", "text",
         "pivot", "map"}
CHART_TYPES = {"line", "bar", "area", "pie"}
MAP_TYPES = {"map"}
METRIC_TYPES = {"card"} | CHART_TYPES | MAP_TYPES | {"pivot"}


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
    dims = metric_dimensions(content)
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


PALETTES = {"default", "blue", "green", "warm", "mono"}
NUMBER_FORMATS = {"auto", "number", "percent", "compact"}


def _format_errors(w):
    fmt = w.get("format")
    if fmt is None:
        return []
    if not isinstance(fmt, dict):
        return [_err("widget.format", "format must be an object")]
    errs = []
    if "palette" in fmt and fmt["palette"] not in PALETTES:
        errs.append(_err("widget.format.palette", "unsupported palette"))
    if "numberFormat" in fmt and fmt["numberFormat"] not in NUMBER_FORMATS:
        errs.append(_err("widget.format.numberFormat",
                         "unsupported number format"))
    for key in ("legend", "labels", "smooth"):
        if key in fmt and not isinstance(fmt[key], bool):
            errs.append(_err("widget.format.%s" % key,
                             "%s must be a boolean" % key))
    for key in ("xTitle", "yTitle"):
        if key in fmt and (not isinstance(fmt[key], str)
                           or len(fmt[key]) > 80):
            errs.append(_err("widget.format.%s" % key,
                             "%s must be a short string" % key))
    return errs


def _interaction_errors(w, columns, param_names, dimension=None):
    value = w.get("interaction")
    if value is None:
        return []
    if not isinstance(value, dict):
        return [_err("widget.interaction", "interaction must be an object")]
    kind = value.get("type")
    if kind not in ("filter", "navigate", "url"):
        return [_err("widget.interaction.type",
                     "interaction type must be filter, navigate or url")]
    errs = []
    if kind == "filter":
        param = value.get("param")
        if not isinstance(param, str) or param not in param_names:
            errs.append(_err("widget.interaction.param",
                             "param is not declared: %s" % param))
        source = value.get("from")
        if dimension is not None:
            if source and source != dimension:
                errs.append(_err("widget.interaction.from",
                                 "from must equal the chart dimension"))
        elif source not in columns:
            errs.append(_err("widget.interaction.from",
                             "from is not an output column: %s" % source))
    else:
        url = value.get("url")
        if not isinstance(url, str) or not url.startswith(
                ("/", "http://", "https://")) or len(url) > 512:
            errs.append(_err("widget.interaction.url",
                             "url must be a relative or http(s) path"))
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
        errs = _format_errors(w)
        if w.get("interaction"):
            errs.append(_err("widget.interaction",
                             "text widgets cannot define interaction"))
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
        errs = _format_errors(w)
        errs.extend(_filter_errors(w, source_cols, param_names))
        errs.extend(_emit_errors(w, cols, param_names))
        errs.extend(_interaction_errors(w, cols, param_names))
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
    if typ == "pivot":
        dims = metric_dimensions(metric_content)
        row_dim = w.get("row_dimension")
        col_dim = w.get("column_dimension")
        if row_dim not in dims or col_dim not in dims:
            return [_err("widget.pivot",
                         "row and column dimensions must be metric dimensions")]
        if row_dim == col_dim:
            return [_err("widget.pivot", "row and column dimensions differ")]
        value = (w.get("value_column")
                 or (metric_content.get("measure") or {}).get("as")
                 or "value")
        if value not in cols:
            return [_err("widget.value_column",
                         "column not in metric output")]
        return _format_errors(w) + errs
    value = (w.get("value_column")
             or (metric_content.get("measure") or {}).get("as")
             or "value")
    if value not in cols:
        errs.append(_err("widget.value_column", "column not in metric output"))
    if typ in CHART_TYPES or typ in MAP_TYPES:
        errs.extend(_format_errors(w))
        dim = w.get("dimension")
        if not dim or dim not in metric_dimensions(metric_content):
            errs.append(_err("widget.dimension",
                             "dimension must be a metric dimension"))
        errs.extend(_emit_errors(w, cols, param_names, dimension=dim))
        errs.extend(_interaction_errors(w, cols, param_names, dimension=dim))
        if typ in MAP_TYPES:
            errs.extend(_map_errors(w))
    elif typ == "table":
        errs.extend(_format_errors(w))
        errs.extend(_emit_errors(w, cols, param_names))
        errs.extend(_interaction_errors(w, cols, param_names))
    elif typ == "card":
        errs.extend(_format_errors(w))
        if w.get("emit"):
            errs.append(_err("widget.emit",
                             "cards cannot define emit"))
    return errs


def _map_errors(widget):
    geo = widget.get("geo_json")
    if not isinstance(geo, dict):
        return [_err("widget.geo_json", "map requires GeoJSON data")]
    if geo.get("type") != "FeatureCollection" or             not isinstance(geo.get("features"), list) or             not geo["features"]:
        return [_err("widget.geo_json",
                     "GeoJSON must be a non-empty FeatureCollection")]
    import json
    if len(json.dumps(geo)) > 1500000:
        return [_err("widget.geo_json", "GeoJSON exceeds 1.5 MB")]
    for feature in geo["features"]:
        if not isinstance(feature, dict) or                 not isinstance(feature.get("properties"), dict):
            return [_err("widget.geo_json",
                         "every feature needs a properties object")]
    prop = widget.get("name_property") or "name"
    if not isinstance(prop, str) or not prop:
        return [_err("widget.name_property", "name property is required")]
    return []


def validate_dashboard(session, content, project_id):
    errs = structural_errors(content)
    if not isinstance(content, dict):
        return errs
    for w in content.get("widgets") or []:
        if isinstance(w, dict) and w.get("type") in TYPES:
            errs.extend(validate_widget(session, content, w, project_id))
    return errs
