from odf.apistudio.catalog import table_columns
from odf.apistudio.params import (ParamError, coerce_params,
                                  validate_param_defs)
from odf.modelstudio.content import (dataset_output_columns,
                                     validate_dataset, validate_metric)
from odf.models import Asset, AssetVersion, Datasource

TYPES = {"text", "metric", "table", "form"}
FORM_WIDGETS = {"input", "textarea", "number", "date", "select", "checkbox"}
FORM_ROLES = {"viewer", "editor", "approver", "admin"}


def empty_app():
    return {"start_page": "p1", "pages": [{
        "id": "p1", "title": "页面 1", "params": [],
        "components": []}]}


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


def dataset_physical_columns(session, ds_content):
    query = ds_content.get("query") or {}
    ds = session.get(Datasource, query.get("datasource_id"))
    table = query.get("table")
    if not ds or not table:
        raise ValueError("dataset table not found")
    return ds, table, table_columns(session, ds, table)


def _default_ok(widget, value):
    if widget == "number":
        if isinstance(value, bool):
            return False
        try:
            float(value)
        except (TypeError, ValueError):
            return False
        return True
    if widget == "checkbox":
        if isinstance(value, bool):
            return True
        return str(value).strip().lower() in (
            "1", "true", "t", "yes", "y", "0", "false", "f", "no", "n")
    if widget == "date":
        from datetime import date, datetime
        if isinstance(value, (date, datetime)):
            return True
        text = str(value)
        try:
            if "T" in text or " " in text:
                datetime.fromisoformat(text)
            else:
                date.fromisoformat(text)
        except ValueError:
            return False
        return True
    return True


def _form_errors(session, comp, project_id):
    ds_content, err = _published(session, comp.get("dataset_id"), "dataset",
                                 project_id)
    if err:
        return [err]
    if validate_dataset(session, ds_content, project_id):
        return [_err("component.dataset_id", "dataset is invalid")]
    try:
        _, _, columns = dataset_physical_columns(session, ds_content)
    except Exception:
        return [_err("component.dataset_id", "dataset table not found")]
    errs = []
    mode = comp.get("mode")
    if mode not in ("insert", "update", "delete"):
        errs.append(_err("component.mode",
                         "mode must be insert, update or delete"))
    fields = comp.get("fields")
    if not isinstance(fields, list) or not fields:
        return errs + [_err("component.fields",
                            "at least one field is required")]
    seen = set()
    field_cols = set()
    for f in fields:
        if not isinstance(f, dict):
            errs.append(_err("component.fields", "field must be an object"))
            continue
        col = f.get("column")
        if col not in columns:
            errs.append(_err("component.fields",
                             "column not in table: %s" % col))
        if isinstance(col, str):
            if col in seen:
                errs.append(_err("component.fields",
                                 "duplicate column: %s" % col))
            seen.add(col)
            field_cols.add(col)
        widget = f.get("widget")
        if not isinstance(widget, str) or widget not in FORM_WIDGETS:
            errs.append(_err("component.fields.widget",
                             "unsupported widget: %s" % widget))
        if widget == "select":
            options = f.get("options")
            if not isinstance(options, list) or not options or                     any(not isinstance(o, str) for o in options):
                errs.append(_err("component.fields.options",
                                 "select requires string options"))
            elif f.get("default") not in (None, "") and                     f.get("default") not in options:
                errs.append(_err("component.fields.default",
                                 "default must be one of the options"))
        if f.get("default") not in (None, ""):
            if not _default_ok(widget, f.get("default")):
                errs.append(_err("component.fields.default",
                                 "default does not match the widget type"))
        if "required" in f and not isinstance(f["required"], bool):
            errs.append(_err("component.fields.required",
                             "required must be a boolean"))
        if "label" in f and not isinstance(f["label"], str):
            errs.append(_err("component.fields.label",
                             "label must be a string"))
    if mode in ("update", "delete"):
        key = comp.get("key")
        if not isinstance(key, str) or key not in field_cols:
            errs.append(_err("component.key",
                             "key must be one of the form fields"))
    if mode == "delete" and len(fields) != 1:
        errs.append(_err("component.fields",
                         "delete requires exactly one field (the key)"))
    roles = comp.get("allow_roles")
    if roles is not None:
        if not isinstance(roles, list) or not roles or                 any(not isinstance(r, str) or r not in FORM_ROLES
                    for r in roles) or                 len(set(roles)) != len(roles):
            errs.append(_err("component.allow_roles",
                             "allow_roles must be a non-empty subset of "
                             "viewer/editor/approver/admin"))
    for name in ("submit_text", "success_message"):
        if name in comp and not isinstance(comp[name], str):
            errs.append(_err("component.%s" % name,
                             "must be a string"))
    return errs


def _metric_columns(content):
    dims = [d for d in content.get("dimensions") or []
            if isinstance(d, str)]
    measure = content.get("measure") or {}
    return dims + [measure.get("as") or "value"]


def structural_errors(content):
    if not isinstance(content, dict):
        return [_err("content", "content must be an object")]
    pages = content.get("pages")
    if not isinstance(pages, list) or not pages:
        return [_err("pages", "at least one page is required")]
    start = content.get("start_page")
    ids, comp_ids, errs = set(), set(), []
    for page in pages:
        if not isinstance(page, dict):
            errs.append(_err("pages", "page must be an object"))
            continue
        pid = page.get("id")
        if not isinstance(pid, str) or not pid:
            errs.append(_err("page.id", "invalid page id"))
            continue
        if pid in ids:
            errs.append(_err("page.id", "duplicate page id: %s" % pid))
        ids.add(pid)
        if not isinstance(page.get("title"), str):
            errs.append(_err("page.title", "page title must be a string"))
        params = page.get("params") or []
        if not isinstance(params, list):
            errs.append(_err("page.params", "params must be an array"))
        else:
            try:
                defs = validate_param_defs(params)
            except ParamError as e:
                errs.append(_err("page.params", str(e)))
            else:
                for p in defs:
                    if p.get("default") is None:
                        continue
                    try:
                        coerce_params([{**p, "required": False}], {})
                    except ParamError as e:
                        errs.append(_err("page.params", str(e)))
        comps = page.get("components") or []
        if not isinstance(comps, list):
            errs.append(_err("page.components",
                             "components must be an array"))
            continue
        for c in comps:
            if not isinstance(c, dict):
                errs.append(_err("component", "component must be an object"))
                continue
            cid = c.get("id")
            if not isinstance(cid, str) or not cid:
                errs.append(_err("component.id", "invalid component id"))
                continue
            if cid in comp_ids:
                errs.append(_err("component.id",
                                 "duplicate component id: %s" % cid))
            comp_ids.add(cid)
            ctype = c.get("type")
            if not isinstance(ctype, str) or ctype not in TYPES:
                errs.append(_err("component.type", "unknown component type"))
            cols = c.get("columns")
            if cols is not None and (
                    not isinstance(cols, list)
                    or any(not isinstance(x, str) for x in cols)):
                errs.append(_err("component.columns",
                                 "columns must be an array of names"))
    if not isinstance(start, str) or start not in ids:
        errs.append(_err("start_page", "start page does not exist"))
    return errs


def _column_errors(comp):
    cols = comp.get("columns")
    if cols is not None and (
            not isinstance(cols, list)
            or any(not isinstance(x, str) for x in cols)):
        return [_err("component.columns", "columns must be an array of names")]
    return []


def validate_component(session, page, comp, project_id):
    params = page.get("params")
    page_params = {p.get("name") for p in (params if isinstance(params, list)
                                           else [])
                   if isinstance(p, dict)}
    typ = comp.get("type")
    if typ == "form":
        return _form_errors(session, comp, project_id)
    col_errs = _column_errors(comp)
    if col_errs:
        return col_errs
    if typ == "text":
        if not isinstance(comp.get("text"), str) or not comp["text"].strip():
            return [_err("component.text", "text is required")]
        return []
    if typ == "table" and comp.get("dataset_id") and comp.get("metric_id"):
        return [_err("component.table", "choose a dataset or a metric")]
    if typ == "table":
        limit = comp.get("limit", 100)
        if not isinstance(limit, int) or isinstance(limit, bool) \
                or not 1 <= limit <= 10000:
            return [_err("component.limit", "limit must be 1..10000")]
    if typ == "table" and comp.get("dataset_id"):
        ds_content, err = _published(session, comp["dataset_id"], "dataset",
                                     project_id)
        if err:
            return [err]
        if validate_dataset(session, ds_content, project_id):
            return [_err("component.dataset_id", "dataset is invalid")]
        errs = []
        required = {p.get("name") for p in ds_content.get("params") or []
                    if isinstance(p, dict) and p.get("required")}
        missing = required - page_params
        if missing:
            errs.append(_err("page.params",
                             "dataset params not exposed: %s"
                             % ", ".join(sorted(missing))))
        cols = dataset_output_columns(ds_content)
        for c in comp.get("columns") or []:
            if c not in cols:
                errs.append(_err("component.columns",
                                 "column not in dataset output: %s" % c))
        return errs
    if typ == "table" and not comp.get("metric_id"):
        return [_err("component.table", "choose a dataset or a metric")]
    metric_content, err = _published(session, comp.get("metric_id"), "metric",
                                     project_id)
    if err:
        return [err]
    if validate_metric(session, metric_content, project_id):
        return [_err("component.metric_id", "metric is invalid")]
    cols = _metric_columns(metric_content)
    errs = []
    value = (comp.get("value_column")
             or (metric_content.get("measure") or {}).get("as") or "value")
    if value not in cols:
        errs.append(_err("component.value_column",
                         "column not in metric output"))
    for c in comp.get("columns") or []:
        if c not in cols:
            errs.append(_err("component.columns",
                             "column not in metric output: %s" % c))
    return errs


def validate_app(session, content, project_id):
    errs = structural_errors(content)
    if not isinstance(content, dict):
        return errs
    pages = content.get("pages")
    if not isinstance(pages, list):
        return errs
    for page in pages:
        if not isinstance(page, dict):
            continue
        comps = page.get("components")
        if not isinstance(comps, list):
            continue
        for comp in comps:
            ctype = comp.get("type") if isinstance(comp, dict) else None
            if isinstance(ctype, str) and ctype in TYPES:
                errs.extend(validate_component(session, page, comp,
                                               project_id))
    return errs
