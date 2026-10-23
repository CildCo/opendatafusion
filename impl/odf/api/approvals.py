from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.models import Flow, Interface
from odf.services.approval import issue_token
from odf.services.audit import write_audit
from odf.services.auth import require_user

router = APIRouter()


@router.post("/flows/{flow_id}/approve")
def approve(flow_id: int, action: str, s: Session = Depends(get_session),
            claims: dict = Depends(require_user)):
    if action not in ("pause", "resume"):
        raise HTTPException(400, "action must be pause or resume")
    if not s.get(Flow, flow_id):
        raise HTTPException(404, "flow not found")
    write_audit(s, claims["sub"], "approve_flow", str(flow_id),
                {"action": action})
    return {"approval_token": issue_token(flow_id, action)}


@router.post("/interfaces/{interface_id}/approve")
def approve_interface(interface_id: int, action: str = "publish",
                      s: Session = Depends(get_session),
                      claims: dict = Depends(require_user)):
    if action not in ("publish", "revoke"):
        raise HTTPException(400, "action must be publish or revoke")
    if not s.get(Interface, interface_id):
        raise HTTPException(404, "interface not found")
    write_audit(s, claims["sub"], "approve_interface", str(interface_id),
                {"action": action})
    return {"approval_token": issue_token(interface_id, action)}
