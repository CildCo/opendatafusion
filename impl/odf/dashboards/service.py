import hashlib
import json

from odf.apistudio.params import ParamError, coerce_params
from odf.assets.service import get_asset
from odf.dashboards.content import (structural_errors, validate_widget)
from odf.modelstudio import cache
from odf.modelstudio.service import preview_dataset, query_metric
from odf.models import AssetVersion
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
