from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.models import Asset, Project, ProjectMember, User
from odf.services.auth import require_approver, require_editor, require_user
from odf.services.grants import (decide_request, list_grants, list_requests,
                                 request_access, revoke_grant)

router = APIRouter()


class RequestIn(BaseModel):
    asset_id: int
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


@router.get("/api-catalog")
def catalog(s: Session = Depends(get_session),
            claims: dict = Depends(require_user)):
    _identity(s, claims)
    rows = (s.query(Asset)
            .filter(Asset.type == "api", Asset.enabled.is_(True),
                    Asset.published_version_id.isnot(None))
            .order_by(Asset.id).all())
    projects = {p.id: p for p in s.query(Project).all()}
    return [{"id": a.id, "key": a.key, "name": a.name,
             "owner_project_id": a.project_id,
             "owner_project": projects[a.project_id].name
             if a.project_id in projects else "",
             "owned": a.project_id == claims["project_id"]}
            for a in rows]


@router.post("/api-requests")
def create_request(body: RequestIn, s: Session = Depends(get_session),
                   claims: dict = Depends(require_user)):
    user = _identity(s, claims)
    try:
        return request_access(s, body.asset_id, claims["project_id"],
                              user.username, body.note)
    except ValueError as e:
        raise _value(e)


@router.get("/api-requests")
def requests(direction: str = "outgoing",
             s: Session = Depends(get_session),
             claims: dict = Depends(require_user)):
    _identity(s, claims)
    try:
        return list_requests(s, claims["project_id"], direction)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/api-requests/{request_id}/approve")
def approve(request_id: int, s: Session = Depends(get_session),
            claims: dict = Depends(require_approver)):
    user = _identity(s, claims)
    try:
        return decide_request(s, request_id, claims["project_id"],
                              user.username, True)
    except ValueError as e:
        raise _value(e)


@router.post("/api-requests/{request_id}/reject")
def reject(request_id: int, s: Session = Depends(get_session),
           claims: dict = Depends(require_approver)):
    user = _identity(s, claims)
    try:
        return decide_request(s, request_id, claims["project_id"],
                              user.username, False)
    except ValueError as e:
        raise _value(e)


@router.get("/api-grants")
def grants(asset_id: int | None = None,
           s: Session = Depends(get_session),
           claims: dict = Depends(require_user)):
    _identity(s, claims)
    return list_grants(s, claims["project_id"], asset_id)


@router.delete("/api-grants/{grant_id}")
def revoke(grant_id: int, s: Session = Depends(get_session),
           claims: dict = Depends(require_editor)):
    user = _identity(s, claims)
    try:
        return revoke_grant(s, grant_id, claims["project_id"], user.username)
    except ValueError as e:
        raise _value(e)
