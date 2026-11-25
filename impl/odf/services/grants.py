from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from odf.assets.service import get_asset
from odf.models import Asset, AssetGrant, AssetRequest, Project
from odf.services.audit import write_audit

READ_TYPES = ("api", "dataset", "model")


def _now():
    return datetime.now(timezone.utc)


def _asset(session, asset_id, types=None):
    asset = get_asset(session, asset_id)
    allowed = tuple(types or READ_TYPES)
    if not asset or asset.type not in allowed:
        raise ValueError("asset not found")
    return asset


def _active_grant(session, asset_id, grantee_project_id):
    return (session.query(AssetGrant)
            .filter_by(asset_id=asset_id,
                       grantee_project_id=grantee_project_id,
                       revoked_at=None).first())


def can_access(session, asset, grantee_project_id):
    if asset.project_id == grantee_project_id:
        return True
    return _active_grant(session, asset.id, grantee_project_id) is not None


def _project_name(session, project_id):
    project = session.get(Project, project_id)
    return project.name if project else ""


def _request_dict(session, row):
    asset = session.get(Asset, row.asset_id)
    return {"id": row.id, "asset_id": row.asset_id,
            "asset_type": row.asset_type,
            "asset_name": asset.name if asset else "",
            "asset_key": asset.key if asset else "",
            "owner_project_id": row.owner_project_id,
            "owner_project": _project_name(session, row.owner_project_id),
            "grantee_project_id": row.grantee_project_id,
            "grantee_project": _project_name(session, row.grantee_project_id),
            "requested_by": row.requested_by, "note": row.note,
            "status": row.status, "created_at": row.created_at,
            "decided_by": row.decided_by, "decided_at": row.decided_at}


def request_access(session, asset_id, grantee_project_id, user, note="",
                   types=None):
    asset = _asset(session, asset_id, types)
    if not asset.published_version_id:
        raise ValueError("asset is not published")
    if asset.project_id == grantee_project_id:
        raise ValueError("asset belongs to your project")
    if _active_grant(session, asset.id, grantee_project_id):
        raise ValueError("access already granted")
    pending = (session.query(AssetRequest)
               .filter_by(asset_id=asset.id,
                          grantee_project_id=grantee_project_id,
                          status="pending").first())
    if pending:
        raise ValueError("access request already pending")
    row = AssetRequest(asset_id=asset.id, asset_type=asset.type,
                       owner_project_id=asset.project_id,
                       grantee_project_id=grantee_project_id,
                       requested_by=user, note=note or "",
                       status="pending")
    session.add(row)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise ValueError("access request already pending")
    session.refresh(row)
    write_audit(session, user, "request_asset_access", str(asset.id),
                {"request_id": row.id, "asset_type": asset.type,
                 "grantee_project_id": grantee_project_id})
    return _request_dict(session, row)


def request_by_key(session, key, grantee_project_id, user, note=""):
    asset = session.query(Asset).filter_by(key=key).first()
    if not asset or asset.type not in READ_TYPES:
        raise ValueError("asset not found")
    return request_access(session, asset.id, grantee_project_id, user, note)


def list_requests(session, project_id, direction="outgoing"):
    query = session.query(AssetRequest)
    if direction == "incoming":
        query = query.filter_by(owner_project_id=project_id)
    elif direction == "outgoing":
        query = query.filter_by(grantee_project_id=project_id)
    else:
        raise ValueError("direction must be outgoing or incoming")
    return [_request_dict(session, row)
            for row in query.order_by(AssetRequest.id.desc()).limit(200)]


def decide_request(session, request_id, owner_project_id, actor, approve):
    row = session.get(AssetRequest, request_id)
    if not row or row.owner_project_id != owner_project_id:
        raise ValueError("request not found")
    if row.status != "pending":
        raise ValueError("request already decided")
    asset = get_asset(session, row.asset_id)
    if not asset or asset.type not in READ_TYPES or not asset.enabled \
            or not asset.published_version_id:
        raise ValueError("asset is not available")
    if approve:
        if not _active_grant(session, row.asset_id,
                             row.grantee_project_id):
            session.add(AssetGrant(
                asset_id=row.asset_id, asset_type=asset.type,
                owner_project_id=row.owner_project_id,
                grantee_project_id=row.grantee_project_id,
                granted_by=actor))
        row.status = "approved"
        action = "approve_asset_access"
    else:
        row.status = "rejected"
        action = "reject_asset_access"
    row.decided_by = actor
    row.decided_at = _now()
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise ValueError("request already decided")
    write_audit(session, actor, action, str(row.asset_id),
                {"request_id": row.id, "asset_type": asset.type,
                 "grantee_project_id": row.grantee_project_id})
    session.refresh(row)
    return _request_dict(session, row)


def list_grants(session, owner_project_id, asset_id=None, asset_type=None):
    query = (session.query(AssetGrant)
             .filter_by(owner_project_id=owner_project_id, revoked_at=None))
    if asset_id:
        query = query.filter_by(asset_id=asset_id)
    if asset_type:
        query = query.filter_by(asset_type=asset_type)
    out = []
    for grant in query.order_by(AssetGrant.id.desc()).all():
        asset = session.get(Asset, grant.asset_id)
        out.append({"id": grant.id, "asset_id": grant.asset_id,
                    "asset_type": grant.asset_type,
                    "asset_name": asset.name if asset else "",
                    "asset_key": asset.key if asset else "",
                    "grantee_project_id": grant.grantee_project_id,
                    "grantee_project": _project_name(
                        session, grant.grantee_project_id),
                    "granted_by": grant.granted_by,
                    "created_at": grant.created_at})
    return out


def revoke_grant(session, grant_id, owner_project_id, actor):
    grant = session.get(AssetGrant, grant_id)
    if not grant or grant.owner_project_id != owner_project_id or \
            grant.revoked_at is not None:
        raise ValueError("grant not found")
    grant.revoked_at = _now()
    session.commit()
    write_audit(session, actor, "revoke_asset_grant", str(grant.asset_id),
                {"grant_id": grant.id, "asset_type": grant.asset_type,
                 "grantee_project_id": grant.grantee_project_id})
    return {"id": grant.id, "revoked": True}


def _column_names(content):
    out = []
    for item in (content.get("query") or {}).get("select") or []:
        if isinstance(item, dict) and item.get("column"):
            out.append({"name": item.get("as") or item["column"],
                        "type": ""})
    return out


def shared_assets(session, project_id):
    grants = (session.query(AssetGrant)
              .filter_by(grantee_project_id=project_id, revoked_at=None)
              .order_by(AssetGrant.id.desc()).all())
    out = []
    for grant in grants:
        asset = session.get(Asset, grant.asset_id)
        if not asset or not asset.enabled or not asset.published_version_id:
            continue
        out.append({"grant_id": grant.id, "asset_id": asset.id,
                    "asset_type": asset.type, "name": asset.name,
                    "key": asset.key,
                    "owner_project": _project_name(session,
                                                   asset.project_id),
                    "description": asset.description,
                    "granted_by": grant.granted_by,
                    "created_at": grant.created_at})
    return out


def shared_asset(session, project_id, asset_id):
    asset = get_asset(session, asset_id)
    if not asset or asset.type not in READ_TYPES:
        raise ValueError("asset not found")
    if not can_access(session, asset, project_id):
        raise ValueError("asset not found")
    if not asset.published_version_id:
        raise ValueError("asset is not published")
    from odf.models import AssetVersion
    version = session.get(AssetVersion, asset.published_version_id)
    content = (version.content_json or {}) if version else {}
    out = {"asset_id": asset.id, "asset_type": asset.type,
           "name": asset.name, "key": asset.key,
           "description": asset.description,
           "owner_project": _project_name(session, asset.project_id),
           "columns": [], "layer": None, "materialization": None}
    if asset.type == "dataset":
        out["columns"] = _column_names(content)
        out["mode"] = content.get("mode") or "visual"
    elif asset.type == "model":
        out["columns"] = [{"name": column.get("name"),
                           "type": column.get("type") or ""}
                          for column in content.get("columns") or []
                          if isinstance(column, dict)]
        out["layer"] = content.get("layer")
        out["materialization"] = content.get("materialization")
        try:
            from odf.transform.service import target_for
            target, _, _ = target_for(session, asset, content)
            out["target"] = target
        except ValueError:
            out["target"] = None
    elif asset.type == "api":
        params = content.get("params") or []
        out["params"] = [{"name": item.get("name"),
                          "type": item.get("type") or "string"}
                         for item in params if isinstance(item, dict)]
    return out
