from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.services.aksk_admin import issue_aksk, list_aksk, revoke_aksk
from odf.models import User
from odf.services.auth import require_admin, require_approver, require_user
from odf.services.projects import (add_member, create_project, list_members,
                                   list_projects, list_projects_for_user)

router = APIRouter()


class ProjectIn(BaseModel):
    code: str
    name: str


class MemberIn(BaseModel):
    user_id: int
    role: str = "viewer"


class KeyPolicyIn(BaseModel):
    ip_allowlist: list[str] | None = None
    rate_limit_per_min: int | None = None


def _project(p):
    return {"id": p.id, "code": p.code, "name": p.name, "status": p.status}


@router.get("/projects")
def projects(s: Session = Depends(get_session),
             claims: dict = Depends(require_admin)):
    return [_project(p) for p in list_projects(s)]


@router.get("/projects/mine")
def mine(s: Session = Depends(get_session),
         claims: dict = Depends(require_user)):
    user = s.get(User, int(claims["sub"]))
    if not user or not user.active:
        raise HTTPException(403, "user is inactive")
    return [_project(p) for p in list_projects_for_user(s, user)]


@router.post("/projects")
def create(body: ProjectIn, s: Session = Depends(get_session),
           claims: dict = Depends(require_admin)):
    return _project(create_project(s, body.code, body.name))


@router.get("/projects/{project_id}/members")
def members(project_id: int, s: Session = Depends(get_session),
            claims: dict = Depends(require_approver)):
    return [{"id": m.id, "user_id": m.user_id, "role": m.role}
            for m in list_members(s, project_id)]


@router.post("/projects/{project_id}/members")
def add(project_id: int, body: MemberIn, s: Session = Depends(get_session),
        claims: dict = Depends(require_admin)):
    m = add_member(s, project_id, body.user_id, body.role)
    return {"id": m.id, "user_id": m.user_id, "role": m.role}


@router.post("/projects/{project_id}/aksk")
def issue(project_id: int, s: Session = Depends(get_session),
          claims: dict = Depends(require_approver)):
    row, sk = issue_aksk(s, project_id)
    return {"ak": row.ak, "sk": sk}          # SK shown once


@router.get("/projects/{project_id}/aksk")
def list_keys(project_id: int, s: Session = Depends(get_session),
              claims: dict = Depends(require_approver)):
    return [{"ak": r.ak, "enabled": r.enabled} for r in list_aksk(s, project_id)]


@router.put("/projects/{project_id}/aksk/{ak}")
def key_policy(project_id: int, ak: str, body: KeyPolicyIn,
               s: Session = Depends(get_session),
               claims: dict = Depends(require_approver)):
    from odf.models import AkSk
    import ipaddress
    row = s.query(AkSk).filter_by(ak=ak, project_id=project_id).first()
    if not row:
        raise HTTPException(404, "key not found")
    if body.ip_allowlist is not None:
        for item in body.ip_allowlist:
            try:
                ipaddress.ip_network(item, strict=False)
            except (TypeError, ValueError):
                raise HTTPException(400, "invalid CIDR: %s" % item)
        row.ip_allowlist = body.ip_allowlist
    if body.rate_limit_per_min is not None:
        if not 0 <= body.rate_limit_per_min <= 100000:
            raise HTTPException(400, "invalid rate limit")
        row.rate_limit_per_min = body.rate_limit_per_min
    s.commit()
    return {"ak": row.ak, "ip_allowlist": row.ip_allowlist or [],
            "rate_limit_per_min": row.rate_limit_per_min}


@router.delete("/projects/{project_id}/aksk/{ak}")
def revoke(project_id: int, ak: str, s: Session = Depends(get_session),
           claims: dict = Depends(require_approver)):
    try:
        return {"ak": revoke_aksk(s, ak).ak, "enabled": False}
    except ValueError as e:
        raise HTTPException(404, str(e))
