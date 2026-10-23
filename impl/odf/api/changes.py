from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.services.approval import issue_token
from odf.services.auth import require_approver, require_user
from odf.services.changes import apply, list_changes, propose

router = APIRouter()


class ChangeIn(BaseModel):
    project_id: int = 1
    action: str
    target: int
    payload: dict = {}


@router.get("/changes")
def changes(status: str | None = None, s: Session = Depends(get_session),
            claims: dict = Depends(require_user)):
    return [{"id": c.id, "action": c.action, "target": c.target,
             "status": c.status, "actor": c.actor,
             "created_at": c.created_at.isoformat()}
            for c in list_changes(s, status, claims["project_id"])]


@router.post("/changes")
def create(body: ChangeIn, s: Session = Depends(get_session),
           claims: dict = Depends(require_user)):
    if body.project_id != claims["project_id"]:
        raise HTTPException(403, "project mismatch")
    c = propose(s, body.project_id, claims["sub"], body.action,
                body.target, body.payload)
    return {"id": c.id, "status": c.status}


@router.post("/changes/{change_id}/approve")
def approve(change_id: int, s: Session = Depends(get_session),
            claims: dict = Depends(require_approver)):
    from odf.models import ChangeRequest
    c = s.get(ChangeRequest, change_id)
    if not c or c.project_id != claims["project_id"]:
        raise HTTPException(404, "change not found")
    if c.action == "app_form_submit":
        from odf.models import Asset
        a = s.get(Asset, int(c.target))
        if not a or a.type != "app" or a.project_id != c.project_id:
            raise HTTPException(404, "app not found")
        return {"approval_token": issue_token(
            int(c.target), c.action, nonce=str(c.id))}
    return {"approval_token": issue_token(int(c.target), c.action)}


@router.post("/changes/{change_id}/apply")
def apply_(change_id: int, approval_token: str,
           s: Session = Depends(get_session),
           claims: dict = Depends(require_user)):
    from odf.models import ChangeRequest
    c = s.get(ChangeRequest, change_id)
    if not c or c.project_id != claims["project_id"]:
        raise HTTPException(404, "change not found")
    try:
        c = apply(s, change_id, approval_token)
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except (ValueError, KeyError) as e:
        raise HTTPException(400, str(e))
    return {"id": c.id, "status": c.status}
