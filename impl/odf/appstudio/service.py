from odf.apistudio.params import ParamError, coerce_params
from odf.appstudio.content import structural_errors, validate_component
from odf.assets.service import get_asset
from odf.modelstudio.service import preview_dataset, query_metric
from odf.models import AssetVersion


def _version(session, asset, published_only):
    vid = asset.published_version_id if published_only \
        else (asset.draft_version_id or asset.published_version_id)
    v = session.get(AssetVersion, vid) if vid else None
    if not v:
        raise ValueError("content not found")
    return v.content_json


def _component_error(errs):
    return {"columns": [], "rows": [], "row_count": 0, "ms": 0,
            "error": "; ".join(e["message"] for e in errs)}


def app_data(session, asset_id, page_id=None, params=None, content=None,
             limit=100, published_only=False, role=None):
    a = get_asset(session, asset_id)
    if not a or a.type != "app":
        raise ValueError("app not found")
    if params is not None and not isinstance(params, dict):
        raise ValueError("params must be an object")
    if content is None:
        content = _version(session, a, published_only)
    errs = structural_errors(content)
    if errs:
        raise ValueError("invalid app: %s" % errs)
    pid = page_id or content.get("start_page")
    page = next((p for p in content["pages"] if p.get("id") == pid), None)
    if not page:
        raise ValueError("page not found")
    try:
        values = coerce_params(page.get("params") or [], params or {})
    except ParamError as e:
        raise ValueError(str(e))
    out = {}
    for comp in page.get("components") or []:
        cid = comp.get("id")
        if comp.get("type") == "form":
            continue
        try:
            errs = validate_component(session, page, comp, a.project_id)
            if errs:
                out[cid] = _component_error(errs)
                continue
            if comp.get("type") == "text":
                out[cid] = {"columns": [], "rows": [], "row_count": 0,
                            "ms": 0, "text": comp.get("text"),
                            "error": None}
            elif comp.get("type") == "table" and comp.get("dataset_id"):
                r = preview_dataset(session, comp["dataset_id"],
                                    limit=comp.get("limit") or limit,
                                    published_only=True, params=values,
                                    role=role)
                out[cid] = {**r, "error": None}
            else:
                r = query_metric(session, comp["metric_id"],
                                 limit=comp.get("limit") or limit,
                                 published_only=True, role=role)
                out[cid] = {**r, "error": None}
        except Exception as e:
            out[cid] = {"columns": [], "rows": [], "row_count": 0, "ms": 0,
                        "error": str(e)}
    return {"page_id": pid, "params": values, "components": out}
