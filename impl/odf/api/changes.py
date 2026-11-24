from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.services.approval import issue_token
from odf.services.auth import (claims_role, require_approver,
                               require_user)
from odf.services.changes import (apply, list_changes, propose,
                                  withdraw as withdraw_change)

router = APIRouter()


class ChangeIn(BaseModel):
    project_id: int = 1
    action: str
    target: int
    payload: dict = {}


ALLOWED_ACTIONS = {
    "publish_pipeline", "pause_pipeline", "resume_pipeline",
    "rollback_pipeline", "publish_api", "rollback_api", "enable_api",
    "revoke_api", "publish_dataset", "rollback_dataset", "publish_metric",
    "rollback_metric", "publish_dashboard", "rollback_dashboard",
    "publish_app", "rollback_app", "app_form_submit",
}


def _target_name(session, action, target):
    from odf.models import Asset
    try:
        object_id = int(target)
    except (TypeError, ValueError):
        return None
    if action.endswith(("_metric", "_dataset", "_api", "_pipeline",
                        "_dashboard", "_app")):
        row = session.get(Asset, object_id)
        return row.name if row else None
    return None


@router.get("/changes")
def changes(status: str | None = None, s: Session = Depends(get_session),
            claims: dict = Depends(require_user)):
    return [{"id": c.id, "action": c.action, "target": c.target,
             "target_name": _target_name(s, c.action, c.target),
             "status": c.status, "actor": c.actor,
             "created_at": c.created_at.isoformat()}
            for c in list_changes(s, status, claims["project_id"])]


@router.post("/changes")
def create(body: ChangeIn, s: Session = Depends(get_session),
           claims: dict = Depends(require_user)):
    if body.project_id != claims["project_id"]:
        raise HTTPException(403, "project mismatch")
    if body.action not in ALLOWED_ACTIONS:
        raise HTTPException(400, "unsupported action")
    c = propose(s, body.project_id, claims["sub"], body.action,
                body.target, body.payload)
    return {"id": c.id, "status": c.status}


@router.post("/changes/{change_id}/withdraw")
def withdraw(change_id: int, s: Session = Depends(get_session),
             claims: dict = Depends(require_user)):
    from odf.models import ChangeRequest
    c = s.get(ChangeRequest, change_id)
    if not c or c.project_id != claims["project_id"]:
        raise HTTPException(404, "change not found")
    role = claims_role(s, claims)
    if c.actor != claims["sub"] and role not in ("approver", "admin"):
        raise HTTPException(403, "only the requester or an approver may withdraw")
    try:
        out = withdraw_change(s, change_id, claims["sub"],
                              claims["project_id"])
    except ValueError as error:
        raise HTTPException(400, str(error))
    return {"id": out.id, "status": out.status}


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
