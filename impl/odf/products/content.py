from odf.models import Asset, Dataset


def empty_product():
    return {"summary": "", "owner": "", "sla": "",
            "asset_ids": [], "terms": []}


def _err(field, message):
    return {"field": field, "message": message}


def validate_product(session, content, project_id):
    if not isinstance(content, dict):
        return [_err("content", "content must be an object")]
    errs = []
    summary = content.get("summary", "")
    if not isinstance(summary, str) or len(summary) > 4000:
        errs.append(_err("summary", "summary must be a string up to 4000"))
    for key in ("owner", "sla"):
        value = content.get(key, "")
        if not isinstance(value, str) or len(value) > 128:
            errs.append(_err(key, "%s must be a string up to 128" % key))
    terms = content.get("terms", [])
    if not isinstance(terms, list) or len(terms) > 20 or any(
            not isinstance(term, str) or len(term) > 128 for term in terms):
        errs.append(_err("terms", "terms must be up to 20 strings"))
    asset_ids = content.get("asset_ids", [])
    if not isinstance(asset_ids, list) or not 1 <= len(asset_ids) <= 50:
        errs.append(_err("asset_ids",
                         "asset_ids must contain 1 to 50 assets"))
        return errs
    if any(not isinstance(value, int) or isinstance(value, bool)
           for value in asset_ids):
        errs.append(_err("asset_ids", "asset ids must be integers"))
        return errs
    if len(set(asset_ids)) != len(asset_ids):
        errs.append(_err("asset_ids", "asset ids must be unique"))
    rows = (session.query(Asset)
            .filter(Asset.id.in_(asset_ids)).all())
    found = {row.id: row for row in rows}
    for asset_id in asset_ids:
        asset = found.get(asset_id)
        if not asset or asset.project_id != project_id:
            errs.append(_err("asset_ids",
                             "asset not found: %s" % asset_id))
        elif asset.type == "data_product":
            errs.append(_err("asset_ids",
                             "products cannot contain other products"))
    return errs


def product_bundle(session, project_id, content):
    from odf.services.bundles import export_bundle
    bundle = export_bundle(session, project_id,
                           content.get("asset_ids") or [])
    bundle["product"] = {
        "summary": content.get("summary", ""),
        "owner": content.get("owner", ""),
        "sla": content.get("sla", ""),
        "terms": content.get("terms", []),
    }
    return bundle
