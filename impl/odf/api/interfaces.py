from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.models import Interface
from odf.services.approval import verify_token
from odf.services.audit import write_audit
from odf.services.auth import require_user
from odf.services.interface import (create_interface, execute_interface,
                                    publish_interface)

router = APIRouter()


@router.get("/interfaces")
def list_(project_id: int | None = None,
          s: Session = Depends(get_session),
          claims: dict = Depends(require_user)):
    q = s.query(Interface)
    if project_id is not None:
        q = q.filter_by(project_id=project_id)
    return [{"id": i.id, "key": i.interface_key, "name": i.name,
             "status": i.status, "datasource_id": i.datasource_id}
            for i in q.order_by(Interface.id).all()]


@router.get("/interfaces/{interface_id}")
def get_(interface_id: int, s: Session = Depends(get_session),
         claims: dict = Depends(require_user)):
    i = s.get(Interface, interface_id)
    if not i:
        raise HTTPException(404, "interface not found")
    return {"id": i.id, "key": i.interface_key, "name": i.name,
            "status": i.status, "datasource_id": i.datasource_id,
            "sql": i.sql_text, "params": i.params_json}


class IfaceIn(BaseModel):
    project_id: int = 1
    datasource_id: int
    name: str
    sql_text: str
    params: list[dict] = []


@router.post("/interfaces")
def create(body: IfaceIn, s: Session = Depends(get_session),
           claims: dict = Depends(require_user)):
    i = create_interface(s, body.project_id, body.datasource_id, body.name,
                         body.sql_text, body.params)
    write_audit(s, claims["sub"], "create_interface", str(i.id),
                {"name": body.name})
    return {"id": i.id, "key": i.interface_key}


@router.post("/interfaces/{interface_id}/publish")
def publish(interface_id: int, approval_token: str,
            s: Session = Depends(get_session),
            claims: dict = Depends(require_user)):
    if not verify_token(interface_id, "publish", approval_token):
        raise HTTPException(403, "approval required")
    status = publish_interface(s, interface_id, actor=claims["sub"]).status
    write_audit(s, claims["sub"], "publish_interface", str(interface_id), {})
    return {"status": status}


@router.post("/interfaces/{interface_id}/revoke")
def revoke(interface_id: int, approval_token: str,
           s: Session = Depends(get_session),
           claims: dict = Depends(require_user)):
    if not verify_token(interface_id, "revoke", approval_token):
        raise HTTPException(403, "approval required")
    i = s.get(Interface, interface_id)
    if not i:
        raise HTTPException(404, "interface not found")
    i.status = 0
    write_audit(s, claims["sub"], "revoke_interface", str(interface_id), {})
    return {"status": 0}


@router.post("/interfaces/{interface_id}/execute")
def execute(interface_id: int, params: dict, s: Session = Depends(get_session),
            claims: dict = Depends(require_user)):
    rows, total = execute_interface(s, interface_id, params)
    write_audit(s, claims["sub"], "execute_interface", str(interface_id),
                {"rows": total})
    return {"total": total, "results": rows}
