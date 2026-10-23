from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from odf.assets.service import get_asset
from odf.models import (Asset, InterfaceGrant, InterfaceRequest, Project)
from odf.services.audit import write_audit


def _now():
    return datetime.now(timezone.utc)


def _asset(session, asset_id):
    a = get_asset(session, asset_id)
    if not a or a.type != "api":
        raise ValueError("API not found")
    return a


def _active_grant(session, asset_id, grantee_project_id):
    return (session.query(InterfaceGrant)
            .filter_by(interface_asset_id=asset_id,
                       grantee_project_id=grantee_project_id,
                       revoked_at=None).first())


def can_access(session, asset, grantee_project_id):
    if asset.project_id == grantee_project_id:
        return True
    return _active_grant(session, asset.id, grantee_project_id) is not None


def _project_name(session, project_id):
    p = session.get(Project, project_id)
    return p.name if p else ""


def _request_dict(session, r):
    a = session.get(Asset, r.interface_asset_id)
    return {"id": r.id, "asset_id": r.interface_asset_id,
            "asset_name": a.name if a else "",
            "asset_key": a.key if a else "",
            "owner_project_id": r.owner_project_id,
            "owner_project": _project_name(session, r.owner_project_id),
            "grantee_project_id": r.grantee_project_id,
            "grantee_project": _project_name(session, r.grantee_project_id),
            "requested_by": r.requested_by, "note": r.note,
            "status": r.status, "created_at": r.created_at,
            "decided_by": r.decided_by, "decided_at": r.decided_at}


def request_access(session, asset_id, grantee_project_id, user, note=""):
    asset = _asset(session, asset_id)
    if not asset.published_version_id:
        raise ValueError("API is not published")
    if asset.project_id == grantee_project_id:
        raise ValueError("API belongs to your project")
    if _active_grant(session, asset.id, grantee_project_id):
        raise ValueError("access already granted")
    pending = (session.query(InterfaceRequest)
               .filter_by(interface_asset_id=asset.id,
                          grantee_project_id=grantee_project_id,
                          status="pending").first())
    if pending:
        raise ValueError("access request already pending")
    r = InterfaceRequest(interface_asset_id=asset.id,
                         owner_project_id=asset.project_id,
                         grantee_project_id=grantee_project_id,
                         requested_by=user, note=note or "",
                         status="pending")
    session.add(r)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise ValueError("access request already pending")
    session.refresh(r)
    write_audit(session, user, "request_api_access", str(asset.id),
                {"request_id": r.id, "grantee_project_id":
                 grantee_project_id})
    return _request_dict(session, r)


def list_requests(session, project_id, direction="outgoing"):
    q = session.query(InterfaceRequest)
    if direction == "incoming":
        q = q.filter_by(owner_project_id=project_id)
    elif direction == "outgoing":
        q = q.filter_by(grantee_project_id=project_id)
    else:
        raise ValueError("direction must be outgoing or incoming")
    return [_request_dict(session, r)
            for r in q.order_by(InterfaceRequest.id.desc()).limit(200).all()]


def decide_request(session, request_id, owner_project_id, actor, approve):
    r = session.get(InterfaceRequest, request_id)
    if not r or r.owner_project_id != owner_project_id:
        raise ValueError("request not found")
    if r.status != "pending":
        raise ValueError("request already decided")
    asset = get_asset(session, r.interface_asset_id)
    if not asset or asset.type != "api" or not asset.enabled or             not asset.published_version_id:
        raise ValueError("API is not available")
    if approve:
        if not _active_grant(session, r.interface_asset_id,
                             r.grantee_project_id):
            session.add(InterfaceGrant(
                interface_asset_id=r.interface_asset_id,
                owner_project_id=r.owner_project_id,
                grantee_project_id=r.grantee_project_id,
                granted_by=actor))
        r.status = "approved"
        action = "approve_api_access"
    else:
        r.status = "rejected"
        action = "reject_api_access"
    r.decided_by = actor
    r.decided_at = _now()
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise ValueError("request already decided")
    write_audit(session, actor, action, str(r.interface_asset_id),
                {"request_id": r.id,
                 "grantee_project_id": r.grantee_project_id})
    session.refresh(r)
    return _request_dict(session, r)


def list_grants(session, owner_project_id, asset_id=None):
    q = session.query(InterfaceGrant).filter_by(
        owner_project_id=owner_project_id, revoked_at=None)
    if asset_id:
        q = q.filter_by(interface_asset_id=asset_id)
    out = []
    for g in q.order_by(InterfaceGrant.id.desc()).all():
        a = session.get(Asset, g.interface_asset_id)
        out.append({"id": g.id, "asset_id": g.interface_asset_id,
                    "asset_name": a.name if a else "",
                    "asset_key": a.key if a else "",
                    "grantee_project_id": g.grantee_project_id,
                    "grantee_project": _project_name(
                        session, g.grantee_project_id),
                    "granted_by": g.granted_by,
                    "created_at": g.created_at})
    return out


def revoke_grant(session, grant_id, owner_project_id, actor):
    g = session.get(InterfaceGrant, grant_id)
    if not g or g.owner_project_id != owner_project_id or \
            g.revoked_at is not None:
        raise ValueError("grant not found")
    g.revoked_at = _now()
    session.commit()
    write_audit(session, actor, "revoke_api_grant",
                str(g.interface_asset_id),
                {"grant_id": g.id,
                 "grantee_project_id": g.grantee_project_id})
    return {"id": g.id, "revoked": True}
