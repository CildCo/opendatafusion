from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.models import (Asset, AssetGrant, AssetRequest, Project,
                        ProjectMember, User)
from odf.services.auth import (claims_role, require_approver, require_editor,
                               require_user)
from odf.services.grants import (READ_TYPES, decide_request, list_grants,
                                 list_requests, request_access, revoke_grant,
                                 shared_asset, shared_assets)

router = APIRouter()


class RequestIn(BaseModel):
    asset_id: int
    note: str = ""


class KeyRequestIn(BaseModel):
    key: str
    note: str = ""


def _identity(s, claims):
    user = s.get(User, int(claims["sub"]))
    if not user or not user.active:
        raise HTTPException(403, "user is inactive")
    if user.role != "admin":
        member = (s.query(ProjectMember)
                  .filter_by(project_id=claims["project_id"],
                             user_id=user.id).first())
        if not member:
            raise HTTPException(403, "not a project member")
    return user


def _value(e):
    msg = str(e)
    return HTTPException(404 if "not found" in msg else 400, msg)


def _catalog(session, project_id, types):
    rows = (session.query(Asset)
            .filter(Asset.type.in_(types), Asset.enabled.is_(True),
                    Asset.published_version_id.isnot(None))
            .order_by(Asset.id).all())
    projects = {p.id: p for p in session.query(Project).all()}
    return [{"id": a.id, "key": a.key, "name": a.name,
             "asset_type": a.type,
             "description": a.description,
             "owner_project_id": a.project_id,
             "owner_project": projects[a.project_id].name
             if a.project_id in projects else "",
             "owned": a.project_id == project_id}
            for a in rows]


@router.get("/asset-catalog")
def asset_catalog(s: Session = Depends(get_session),
                  claims: dict = Depends(require_user)):
    _identity(s, claims)
    return _catalog(s, claims["project_id"], READ_TYPES)


@router.get("/api-catalog")
def api_catalog(s: Session = Depends(get_session),
                claims: dict = Depends(require_user)):
    _identity(s, claims)
    return _catalog(s, claims["project_id"], ("api",))


@router.post("/asset-requests")
def create_request(body: RequestIn, s: Session = Depends(get_session),
                   claims: dict = Depends(require_user)):
    user = _identity(s, claims)
    try:
        return request_access(s, body.asset_id, claims["project_id"],
                              user.username, body.note)
    except ValueError as e:
        raise _value(e)


@router.post("/asset-requests/by-key")
def create_request_by_key(body: KeyRequestIn,
                          s: Session = Depends(get_session),
                          claims: dict = Depends(require_user)):
    user = _identity(s, claims)
    try:
        from odf.services.grants import request_by_key
        return request_by_key(s, body.key.strip(), claims["project_id"],
                              user.username, body.note)
    except ValueError as e:
        raise _value(e)


@router.get("/asset-requests")
def requests(direction: str = "outgoing",
             s: Session = Depends(get_session),
             claims: dict = Depends(require_user)):
    _identity(s, claims)
    try:
        return list_requests(s, claims["project_id"], direction)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/asset-requests/{request_id}/approve")
def approve(request_id: int, s: Session = Depends(get_session),
            claims: dict = Depends(require_approver)):
    user = _identity(s, claims)
    try:
        return decide_request(s, request_id, claims["project_id"],
                              user.username, True)
    except ValueError as e:
        raise _value(e)


@router.post("/asset-requests/{request_id}/reject")
def reject(request_id: int, s: Session = Depends(get_session),
           claims: dict = Depends(require_approver)):
    user = _identity(s, claims)
    try:
        return decide_request(s, request_id, claims["project_id"],
                              user.username, False)
    except ValueError as e:
        raise _value(e)


@router.get("/asset-grants")
def grants(asset_id: int | None = None, asset_type: str | None = None,
           s: Session = Depends(get_session),
           claims: dict = Depends(require_user)):
    _identity(s, claims)
    return list_grants(s, claims["project_id"], asset_id, asset_type)


@router.delete("/asset-grants/{grant_id}")
def revoke(grant_id: int, s: Session = Depends(get_session),
           claims: dict = Depends(require_editor)):
    user = _identity(s, claims)
    try:
        return revoke_grant(s, grant_id, claims["project_id"], user.username)
    except ValueError as e:
        raise _value(e)


@router.get("/shared-assets")
def shared(s: Session = Depends(get_session),
           claims: dict = Depends(require_user)):
    _identity(s, claims)
    return shared_assets(s, claims["project_id"])


@router.get("/shared-assets/{asset_id}")
def shared_detail(asset_id: int, s: Session = Depends(get_session),
                  claims: dict = Depends(require_user)):
    _identity(s, claims)
    try:
        return shared_asset(s, claims["project_id"], asset_id)
    except ValueError as e:
        raise _value(e)


@router.get("/shared-assets/{asset_id}/preview")
def shared_preview(asset_id: int, limit: int = 50,
                   s: Session = Depends(get_session),
                   claims: dict = Depends(require_user)):
    _identity(s, claims)
    asset = s.get(Asset, asset_id)
    if not asset or asset.type != "dataset":
        raise HTTPException(404, "asset not found")
    from odf.services.grants import can_access
    if not can_access(s, asset, claims["project_id"]):
        raise HTTPException(404, "asset not found")
    from odf.modelstudio.service import preview_dataset
    from odf.services.audit import write_audit
    try:
        result = preview_dataset(
            s, asset_id, limit=max(1, min(int(limit), 200)),
            published_only=True, role=claims_role(s, claims))
    except ValueError:
        raise HTTPException(400, "could not preview the shared dataset")
    result.pop("sql", None)
    result.pop("cached", None)
    write_audit(s, claims["sub"], "shared_dataset_preview", str(asset_id),
                {"row_count": result.get("row_count", 0)})
    return result


# Compatibility aliases for the previous API-only grant routes.
@router.post("/api-requests")
def create_api_request(body: RequestIn, s: Session = Depends(get_session),
                       claims: dict = Depends(require_user)):
    user = _identity(s, claims)
    try:
        return request_access(s, body.asset_id, claims["project_id"],
                              user.username, body.note, types=("api",))
    except ValueError as e:
        raise _value(e)


@router.get("/api-requests")
def api_requests(direction: str = "outgoing",
                 s: Session = Depends(get_session),
                 claims: dict = Depends(require_user)):
    _identity(s, claims)
    return [row for row in list_requests(s, claims["project_id"], direction)
            if row["asset_type"] == "api"]


@router.post("/api-requests/{request_id}/approve")
def approve_api_request(request_id: int, s: Session = Depends(get_session),
                        claims: dict = Depends(require_approver)):
    user = _identity(s, claims)
    row = s.get(AssetRequest, request_id)
    if not row or row.asset_type != "api":
        raise HTTPException(404, "request not found")
    try:
        return decide_request(s, request_id, claims["project_id"],
                              user.username, True)
    except ValueError as e:
        raise _value(e)


@router.post("/api-requests/{request_id}/reject")
def reject_api_request(request_id: int, s: Session = Depends(get_session),
                       claims: dict = Depends(require_approver)):
    user = _identity(s, claims)
    row = s.get(AssetRequest, request_id)
    if not row or row.asset_type != "api":
        raise HTTPException(404, "request not found")
    try:
        return decide_request(s, request_id, claims["project_id"],
                              user.username, False)
    except ValueError as e:
        raise _value(e)


@router.get("/api-grants")
def api_grants(asset_id: int | None = None,
               s: Session = Depends(get_session),
               claims: dict = Depends(require_user)):
    _identity(s, claims)
    return list_grants(s, claims["project_id"], asset_id, "api")


@router.delete("/api-grants/{grant_id}")
def revoke_api_grant(grant_id: int, s: Session = Depends(get_session),
                     claims: dict = Depends(require_editor)):
    user = _identity(s, claims)
    grant = s.get(AssetGrant, grant_id)
    if not grant or grant.asset_type != "api":
        raise HTTPException(404, "grant not found")
    try:
        return revoke_grant(s, grant_id, claims["project_id"],
                            user.username)
    except ValueError as e:
        raise _value(e)
