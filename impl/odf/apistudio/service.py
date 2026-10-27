import json
import time

from odf.apistudio.catalog import table_columns
from odf.apistudio.compiler import compile_visual, render_sql
from odf.apistudio.content import validate_content
from odf.apistudio.params import ParamError, coerce_params
from odf.apistudio.sqlguard import ensure_read_only
from odf.assets.service import get_asset
from odf.models import AssetVersion, Datasource
from odf.services.query import execute_query
from odf.settings import get_settings


class ApiError(ValueError):
    def __init__(self, message, errors=None, parameter=None):
        super().__init__(message)
        self.errors = errors or []
        self.parameter = parameter


def _published_content(session, asset):
    v = session.get(AssetVersion, asset.published_version_id) \
        if asset.published_version_id else None
    if not v:
        raise ApiError("API is not published")
    return v.content_json


def _run(session, asset, content, params, limit=None, include_sql=False,
         role=None):
    errs = validate_content(session, content, asset.project_id)
    if errs:
        raise ApiError("invalid API content", errors=errs)
    if params is not None and not isinstance(params, dict):
        raise ApiError("params must be an object")
    defs = content.get("params") or []
    try:
        values = coerce_params(defs, params)
    except ParamError as e:
        raise ApiError(str(e), parameter=e.parameter)
    ds_id = (content.get("query") or {}).get("datasource_id")
    ds = session.get(Datasource, ds_id) if ds_id else None
    if not ds or ds.project_id != asset.project_id:
        raise ApiError("datasource does not belong to project")
    try:
        if content.get("mode") == "visual":
            columns = table_columns(session, ds, content["query"]["table"])
            sql, binds = compile_visual(content["query"], columns, values)
        else:
            sql, binds = render_sql(content["sql"], defs, values)
        ensure_read_only(sql)
    except ValueError as e:
        raise ApiError(str(e))

    s = get_settings()
    try:
        requested = int(limit or s.query_max_rows)
    except (TypeError, ValueError):
        raise ApiError("limit must be a number")
    max_rows = max(1, min(requested, s.query_max_rows))
    started = time.time()
    try:
        result = execute_query(session, ds, sql, binds, max_rows)
        columns = result["columns"]
        rows = result["rows"]
    except ValueError as e:
        raise ApiError(str(e))
    if content.get("mode") == "visual":
        from odf.services.masking import apply_masks
        rows = apply_masks(session, content, rows, role)
    ms = int((time.time() - started) * 1000)
    out = {"columns": columns, "rows": rows, "row_count": len(rows),
           "ms": ms}
    if include_sql:
        out["sql"] = sql
    return out


def run_content(session, asset, content, params, limit=None,
                include_sql=False, role=None):
    return _run(session, asset, content, params, limit, include_sql, role)


def preview_api(session, asset_id, params, content=None, limit=100,
                role=None):
    asset = get_asset(session, asset_id)
    if not asset or asset.type != "api":
        raise ApiError("API not found")
    if content is None:
        v = session.get(AssetVersion, asset.draft_version_id) \
            if asset.draft_version_id else None
        if not v:
            raise ApiError("draft not found")
        content = v.content_json
    return _run(session, asset, content, params, limit=limit,
                include_sql=True, role=role)


def execute_published(session, asset_id, params, role=None):
    asset = get_asset(session, asset_id)
    if not asset or asset.type != "api" or not asset.enabled:
        raise ApiError("API not found")
    return _run(session, asset, _published_content(session, asset), params,
                role=role)


def build_docs(asset, content):
    params = content.get("params") or []
    path = "/openapi/%s" % asset.key
    example = {p["name"]: p["example"] if p.get("example") is not None
               else p.get("default") for p in params}
    curl = (
        "curl -X POST 'http://HOST%s' \\\n"
        "  -H 'projectKey: PROJECT_CODE' \\\n"
        "  -H 'Authorization: AK:Base64(HMAC-SHA256(SK, stringToSign))' \\\n"
        "  -H 'Content-Type: application/json' \\\n"
        "  -d '%s'" % (path, json.dumps(example)))
    python = (
        "import requests\n"
        "requests.post('http://HOST%s', json=%s, headers={\n"
        "    'projectKey': 'PROJECT_CODE',\n"
        "    'Authorization': 'AK:<signature>',\n"
        "    'Content-Type': 'application/json'})" % (path, example))
    return {"key": asset.key, "name": asset.name, "method": "POST",
            "path": path, "params": params, "example": example,
            "curl": curl, "python": python}
