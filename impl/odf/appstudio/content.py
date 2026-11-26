import re

from odf.apistudio.catalog import table_columns
from odf.apistudio.params import (ParamError, coerce_params,
                                  validate_param_defs)
from odf.modelstudio.content import (dataset_output_columns,
                                     metric_dimensions, validate_dataset,
                                     validate_metric)
from odf.models import Asset, AssetVersion, Datasource

TYPES = {"text", "heading", "divider", "image", "button", "progress",
         "metric", "table", "form", "container", "tabs", "modal",
         "upload", "approval", "list"}
CONTAINER_TYPES = {"container", "tabs", "modal"}
MAX_NESTING = 4
MAX_PAGE_COMPONENTS = 200
FORM_WIDGETS = {"input", "textarea", "number", "date", "select", "checkbox"}
FORM_ROLES = {"viewer", "editor", "approver", "admin"}


def empty_app():
    return {"start_page": "p1", "pages": [{
        "id": "p1", "title": "页面 1", "params": [],
        "components": []}]}


BINDING = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_.]*)\s*\}\}")


def child_lists(comp):
    typ = comp.get("type")
    if typ in ("container", "modal"):
        children = comp.get("children")
        return [children] if isinstance(children, list) else []
    if typ == "tabs":
        out = []
        for tab in comp.get("tabs") or []:
            if isinstance(tab, dict) and isinstance(tab.get("components"),
                                                    list):
                out.append(tab["components"])
        return out
    return []


def iter_components(components, depth=0):
    if not isinstance(components, list) or depth > MAX_NESTING:
        return
    for comp in components:
        if not isinstance(comp, dict):
            continue
        yield comp
        for children in child_lists(comp):
            yield from iter_components(children, depth + 1)


def collect_component_ids(components):
    return {comp.get("id") for comp in iter_components(components)
            if isinstance(comp.get("id"), str)}


def _container_errors(comp):
    typ = comp.get("type")
    if typ == "container":
        children = comp.get("children", [])
        if not isinstance(children, list) or len(children) > 50:
            return [_err("component.children",
                         "container children must be an array of at most 50")]
        return []
    if typ == "modal":
        errs = []
        children = comp.get("children", [])
        if not isinstance(children, list) or len(children) > 50:
            errs.append(_err("component.children",
                             "modal children must be an array of at most 50"))
        for name in ("label", "title"):
            value = comp.get(name)
            if value is not None and (not isinstance(value, str)
                                      or len(value) > 80):
                errs.append(_err("component.%s" % name,
                                 "modal %s must be a string" % name))
        return errs
    if typ == "tabs":
        tabs = comp.get("tabs")
        if not isinstance(tabs, list) or not 1 <= len(tabs) <= 8:
            return [_err("component.tabs",
                         "tabs must contain 1 to 8 tabs")]
        errs, ids = [], set()
        for tab in tabs:
            if not isinstance(tab, dict):
                errs.append(_err("component.tabs", "tab must be an object"))
                continue
            tid = tab.get("id")
            if not isinstance(tid, str) or not re.fullmatch(
                    r"[A-Za-z0-9_-]{1,40}", tid):
                errs.append(_err("component.tabs", "invalid tab id"))
            elif tid in ids:
                errs.append(_err("component.tabs",
                                 "duplicate tab id: %s" % tid))
            ids.add(tid)
            if not isinstance(tab.get("title"), str) \
                    or len(tab.get("title")) > 80:
                errs.append(_err("component.tabs",
                                 "tab title must be a string"))
            if not isinstance(tab.get("components"), list):
                errs.append(_err("component.tabs",
                                 "tab components must be an array"))
        return errs
    return []


def _layout_errors(comp):
    layout = comp.get("layout")
    if layout is None:
        return []
    if not isinstance(layout, dict):
        return [_err("component.layout", "layout must be an object")]
    errs = []
    values = {}
    for key in ("x", "y", "w", "h"):
        value = layout.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            errs.append(_err("component.layout",
                             "layout %s must be a non-negative integer" % key))
            continue
        values[key] = value
    if len(values) == 4:
        if values["w"] < 1 or values["h"] < 1:
            errs.append(_err("component.layout", "layout size must be positive"))
        if values["x"] + values["w"] > 12:
            errs.append(_err("component.layout", "layout exceeds 12 columns"))
    return errs


def _visible_errors(comp, page_params):
    value = comp.get("visible_when")
    if value is None:
        return []
    if not isinstance(value, dict):
        return [_err("component.visible_when", "visible_when must be an object")]
    param = value.get("param")
    if not isinstance(param, str) or param not in page_params:
        return [_err("component.visible_when", "visibility param not found")]
    if value.get("op") not in ("=", "!=", "in"):
        return [_err("component.visible_when", "unsupported visibility operator")]
    return []


def _binding_errors(text, page_params, field, component_ids):
    if not isinstance(text, str):
        return []
    errs = []
    for path in sorted(set(BINDING.findall(text))):
        if path.startswith("params."):
            name = path[7:]
            if "." in name or name not in page_params:
                errs.append(_err(field,
                                 "binding param not found: %s" % path))
        elif path.startswith("components."):
            parts = path.split(".")
            if len(parts) < 2 or parts[1] not in component_ids:
                errs.append(_err(field,
                                 "binding component not found: %s" % path))
        elif path not in page_params:
            errs.append(_err(field, "binding param not found: %s" % path))
    return errs


def _role_list_errors(roles, field):
    if roles is None:
        return []
    if not isinstance(roles, list) or not roles:
        return [_err(field, "visible_roles must be a non-empty array")]
    if any(not isinstance(role, str) or role not in FORM_ROLES
           for role in roles) or len(set(roles)) != len(roles):
        return [_err(field,
                     "visible_roles must be viewer/editor/approver/admin")]
    return []


def _visible_role_errors(comp):
    return _role_list_errors(comp.get("visible_roles"),
                             "component.visible_roles")


STYLE_COLORS = re.compile(
    r"^(#[0-9a-fA-F]{3}|#[0-9a-fA-F]{6}|#[0-9a-fA-F]{8}|transparent|inherit)$")
STYLE_KEYS = {"background", "color", "align", "padding", "radius",
              "font_size"}
STYLE_NUMBERS = {"padding": (0, 64), "radius": (0, 64),
                 "font_size": (8, 48)}
HIGHLIGHT_TONES = {"info", "success", "warning", "danger"}


def _style_errors(comp):
    style = comp.get("style")
    if style is None:
        return []
    if not isinstance(style, dict):
        return [_err("component.style", "style must be an object")]
    errs = []
    for key, value in style.items():
        field = "component.style.%s" % key
        if key not in STYLE_KEYS:
            errs.append(_err(field, "unsupported style property: %s" % key))
        elif key in ("background", "color"):
            if not isinstance(value, str) or not STYLE_COLORS.match(value):
                errs.append(_err(field, "style color must be a hex color"))
        elif key == "align":
            if value not in ("left", "center", "right"):
                errs.append(_err(field, "align must be left, center or right"))
        elif key in STYLE_NUMBERS:
            low, high = STYLE_NUMBERS[key]
            if not isinstance(value, int) or isinstance(value, bool)                     or not low <= value <= high:
                errs.append(_err(field,
                                 "%s must be %d..%d" % (key, low, high)))
    return errs


def _highlight_errors(comp, page_params):
    rule = comp.get("highlight_when")
    if rule is None:
        return []
    if not isinstance(rule, dict):
        return [_err("component.highlight_when",
                     "highlight_when must be an object")]
    errs = []
    param = rule.get("param")
    if not isinstance(param, str) or param not in page_params:
        errs.append(_err("component.highlight_when.param",
                         "highlight param not found"))
    if rule.get("op") not in ("=", "!=", "in"):
        errs.append(_err("component.highlight_when.op",
                         "unsupported highlight operator"))
    if rule.get("tone") not in HIGHLIGHT_TONES:
        errs.append(_err("component.highlight_when.tone",
                         "tone must be info/success/warning/danger"))
    value = rule.get("value")
    if rule.get("op") == "in":
        if not isinstance(value, list) or not 1 <= len(value) <= 50:
            errs.append(_err("component.highlight_when.value",
                             "in requires 1..50 values"))
    elif value is None or isinstance(value, (dict, list)):
        errs.append(_err("component.highlight_when.value",
                         "highlight value must be a scalar"))
    return errs


def _action_errors(comp, page_ids, page_params):
    actions = comp.get("actions")
    if actions is None:
        return []
    if not isinstance(actions, list) or len(actions) > 10:
        return [_err("component.actions",
                     "actions must be an array of at most 10 items")]
    errs = []
    for action in actions:
        if not isinstance(action, dict):
            errs.append(_err("component.actions",
                             "action must be an object"))
            continue
        kind = action.get("type")
        if kind not in ("navigate", "url", "set_param", "refresh",
                        "message"):
            errs.append(_err("component.actions.type",
                             "unsupported action type: %s" % kind))
            continue
        if kind == "navigate":
            target = action.get("page")
            if not isinstance(target, str) or target not in page_ids:
                errs.append(_err("component.actions.page",
                                 "target page does not exist"))
        elif kind == "url":
            url = action.get("url")
            if not isinstance(url, str) or not url.startswith(
                    ("/", "http://", "https://")) or len(url) > 512:
                errs.append(_err("component.actions.url",
                                 "url must be a relative or http(s) path"))
        elif kind == "set_param":
            param = action.get("param")
            if not isinstance(param, str) or param not in page_params:
                errs.append(_err("component.actions.param",
                                 "param is not declared: %s" % param))
            if not isinstance(action.get("value"),
                              (str, int, float, bool)):
                errs.append(_err("component.actions.value",
                                 "action value must be a scalar"))
        elif kind == "message":
            text = action.get("text")
            if not isinstance(text, str) or not text.strip():
                errs.append(_err("component.actions.text",
                                 "message text is required"))
    return errs


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
    dims = metric_dimensions(content)
    measure = content.get("measure") or {}
    return dims + [measure.get("as") or "value"]


def _component_structure(components, comp_ids, depth, total,
                         page_params):
    if not isinstance(components, list):
        return [_err("component", "components must be an array")]
    if depth > MAX_NESTING:
        return [_err("component.nesting",
                     "component nesting exceeds %d levels" % MAX_NESTING)]
    errs = []
    for comp in components:
        if not isinstance(comp, dict):
            errs.append(_err("component", "component must be an object"))
            continue
        total[0] += 1
        if total[0] > MAX_PAGE_COMPONENTS:
            errs.append(_err("component.count",
                             "too many components on a page"))
            break
        cid = comp.get("id")
        if not isinstance(cid, str) or not cid:
            errs.append(_err("component.id", "invalid component id"))
            continue
        if cid in comp_ids:
            errs.append(_err("component.id",
                             "duplicate component id: %s" % cid))
        comp_ids.add(cid)
        ctype = comp.get("type")
        if not isinstance(ctype, str) or ctype not in TYPES:
            errs.append(_err("component.type", "unknown component type"))
        cols = comp.get("columns")
        if cols is not None and (
                not isinstance(cols, list)
                or any(not isinstance(x, str) for x in cols)):
            errs.append(_err("component.columns",
                             "columns must be an array of names"))
        errs.extend(_layout_errors(comp))
        errs.extend(_visible_role_errors(comp))
        errs.extend(_style_errors(comp))
        errs.extend(_highlight_errors(comp, page_params))
        errs.extend(_container_errors(comp))
        children = child_lists(comp)
        if children and depth >= MAX_NESTING:
            errs.append(_err("component.nesting",
                             "component nesting exceeds %d levels"
                             % MAX_NESTING))
        elif children:
            for items in children:
                errs.extend(_component_structure(
                    items, comp_ids, depth + 1, total, page_params))
    return errs


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
        errs.extend(_role_list_errors(page.get("visible_roles"),
                                      "page.visible_roles"))
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
        page_params = {p.get("name") for p in
                       (params if isinstance(params, list) else [])
                       if isinstance(p, dict) and isinstance(
                           p.get("name"), str)}
        errs.extend(_component_structure(comps, comp_ids, 0, [0],
                                         page_params))
    if not isinstance(start, str) or start not in ids:
        errs.append(_err("start_page", "start page does not exist"))
    for page in pages if isinstance(pages, list) else []:
        if not isinstance(page, dict):
            continue
        for comp in iter_components(page.get("components") or []):
            if comp.get("type") == "button":
                target = comp.get("target_page")
                if target and target not in ids:
                    errs.append(_err("component.target_page",
                                     "target page does not exist"))
    return errs


def _column_errors(comp):
    cols = comp.get("columns")
    if cols is not None and (
            not isinstance(cols, list)
            or any(not isinstance(x, str) for x in cols)):
        return [_err("component.columns", "columns must be an array of names")]
    return []


def validate_component(session, page, comp, project_id, page_ids=None):
    params = page.get("params")
    page_params = {p.get("name") for p in (params if isinstance(params, list)
                                           else [])
                   if isinstance(p, dict)}
    typ = comp.get("type")
    page_components = page.get("components") or []
    component_ids = collect_component_ids(page_components)
    page_ids = set(page_ids or [])
    if typ in CONTAINER_TYPES:
        errs = _visible_errors(comp, page_params)
        errs.extend(_container_errors(comp))
        for children in child_lists(comp):
            for child in children:
                if isinstance(child, dict):
                    errs.extend(validate_component(
                        session, page, child, project_id, page_ids))
        return errs
    errs = _visible_errors(comp, page_params)
    if typ == "form":
        return errs + _form_errors(session, comp, project_id)
    if typ == "upload":
        label = comp.get("label") or ""
        if not isinstance(label, str) or len(label) > 120:
            return errs + [_err("component.label",
                                "upload label must be a string")]
        accept = comp.get("accept")
        if accept is not None:
            if not isinstance(accept, list) or len(accept) > 10 or any(
                    not isinstance(item, str)
                    or not re.fullmatch(r"[A-Za-z0-9]{1,16}", item)
                    for item in accept):
                return errs + [_err("component.accept",
                                    "accept must list up to 10 extensions")]
        max_mb = comp.get("max_mb", 20)
        if not isinstance(max_mb, int) or isinstance(max_mb, bool)                 or not 1 <= max_mb <= 20:
            return errs + [_err("component.max_mb",
                                "max_mb must be 1..20")]
        return errs
    if typ == "approval":
        title = comp.get("title") or ""
        if not isinstance(title, str) or len(title) > 120:
            return errs + [_err("component.title",
                                "approval title must be a string")]
        limit = comp.get("limit", 10)
        if not isinstance(limit, int) or isinstance(limit, bool)                 or not 1 <= limit <= 50:
            return errs + [_err("component.limit",
                                "approval limit must be 1..50")]
        return errs
    if typ == "list":
        dsid = comp.get("dataset_id")
        if not isinstance(dsid, int):
            return errs + [_err("component.dataset_id",
                                "list requires a dataset")]
        ds_content, err = _published(session, dsid, "dataset", project_id)
        if err:
            return errs + [err]
        if validate_dataset(session, ds_content, project_id):
            return errs + [_err("component.dataset_id",
                                "dataset is invalid")]
        required = {p.get("name") for p in ds_content.get("params") or []
                    if isinstance(p, dict) and p.get("required")}
        if required - page_params:
            return errs + [_err("page.params",
                                "dataset params not exposed: %s"
                                % ", ".join(sorted(required - page_params)))]
        cols = dataset_output_columns(ds_content)
        for c in comp.get("columns") or []:
            if c not in cols:
                return errs + [_err("component.columns",
                                    "column not in dataset output: %s" % c)]
        for key in ("title_column", "subtitle_column", "value_column"):
            value = comp.get(key)
            if value and value not in cols:
                return errs + [_err("component.%s" % key,
                                    "column not in dataset output: %s"
                                    % value)]
        limit = comp.get("limit", 100)
        if not isinstance(limit, int) or isinstance(limit, bool)                 or not 1 <= limit <= 1000:
            return errs + [_err("component.limit",
                                "limit must be 1..1000")]
        return errs
    col_errs = _column_errors(comp)
    if col_errs:
        return errs + col_errs
    if typ in ("text", "heading"):
        if not isinstance(comp.get("text"), str) or not comp["text"].strip():
            return errs + [_err("component.text", "text is required")]
        return errs + _binding_errors(comp.get("text"), page_params,
                                      "component.text", component_ids)
    if typ == "divider":
        return errs
    if typ == "image":
        url = comp.get("url")
        if not isinstance(url, str) or not url.strip():
            return errs + [_err("component.url", "image url is required")]
        if not (url.startswith("http://") or url.startswith("https://")
                or url.startswith("/")):
            return errs + [_err("component.url", "image url is not supported")]
        return errs
    if typ == "button":
        if not isinstance(comp.get("label") or comp.get("text") or "",
                          str):
            return errs + [_err("component.label", "button label is invalid")]
        errs.extend(_action_errors(comp, page_ids, page_params))
        url = comp.get("url")
        if url and not (str(url).startswith("http://")
                        or str(url).startswith("https://")
                        or str(url).startswith("/")):
            return errs + [_err("component.url", "button url is not supported")]
        return errs
    if typ == "progress":
        value = comp.get("value")
        if value is None and not comp.get("value_param"):
            return errs + [_err("component.value", "progress value is required")]
        if value is not None and (not isinstance(value, (int, float))
                                  or isinstance(value, bool)
                                  or not 0 <= value <= 100):
            return errs + [_err("component.value",
                                "progress value must be 0..100")]
        param = comp.get("value_param")
        if param and param not in page_params:
            return errs + [_err("component.value_param",
                                "progress param not found")]
        return errs
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
    page_ids = {p.get("id") for p in pages
                if isinstance(p, dict) and isinstance(p.get("id"), str)}
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
                                               project_id, page_ids))
    return errs
