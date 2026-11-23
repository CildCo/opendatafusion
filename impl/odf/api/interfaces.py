from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.models import Interface
from odf.services.approval import verify_token
from odf.services.audit import write_audit
from odf.services.auth import require_editor, require_user
from odf.services.interface import (create_interface, execute_interface,
                                    interface_history, interface_stats,
                                    publish_interface)

router = APIRouter()


def _iface(session, interface_id: int, claims: dict) -> Interface:
    i = session.get(Interface, interface_id)
    if not i or i.project_id != claims.get("project_id"):
        raise HTTPException(404, "interface not found")
    return i


@router.get("/interfaces")
def list_(s: Session = Depends(get_session),
          claims: dict = Depends(require_user)):
    return [{"id": i.id, "key": i.interface_key, "name": i.name,
             "status": i.status, "datasource_id": i.datasource_id,
             "migrated_asset_id": i.migrated_asset_id}
            for i in (s.query(Interface)
                      .filter_by(project_id=claims["project_id"])
                      .order_by(Interface.id).all())]


@router.post("/interfaces/{interface_id}/migrate")
def migrate(interface_id: int, s: Session = Depends(get_session),
            claims: dict = Depends(require_editor)):
    from odf.services.legacy import migrate_interface
    try:
        asset = migrate_interface(s, claims["project_id"], interface_id,
                                  claims["sub"])
    except ValueError as error:
        raise HTTPException(400, str(error))
    write_audit(s, claims["sub"], "migrate_interface", str(interface_id),
                {"asset_id": asset.id})
    return {"asset_id": asset.id, "link": "/apis/%d" % asset.id}


@router.get("/interfaces/{interface_id}")
def get_(interface_id: int, s: Session = Depends(get_session),
         claims: dict = Depends(require_user)):
    i = _iface(s, interface_id, claims)
    return {"id": i.id, "key": i.interface_key, "name": i.name,
            "status": i.status, "datasource_id": i.datasource_id,
            "sql": i.sql_text, "params": i.params_json}


@router.get("/interfaces/{interface_id}/stats")
def stats(interface_id: int, days: int = 30,
          s: Session = Depends(get_session),
          claims: dict = Depends(require_user)):
    out = interface_stats(s, claims["project_id"], interface_id, days)
    if out is None:
        raise HTTPException(404, "interface not found")
    return out


@router.get("/interfaces/{interface_id}/history")
def history(interface_id: int, limit: int = 50,
            s: Session = Depends(get_session),
            claims: dict = Depends(require_user)):
    rows = interface_history(s, claims["project_id"], interface_id, limit)
    if rows is None:
        raise HTTPException(404, "interface not found")
    return rows


class IfaceIn(BaseModel):
    project_id: int = 1
    datasource_id: int
    name: str
    sql_text: str
    params: list[dict] = []


@router.post("/interfaces")
def create(body: IfaceIn, s: Session = Depends(get_session),
           claims: dict = Depends(require_user)):
    if body.project_id != claims["project_id"]:
        raise HTTPException(403, "cross-project interface is not allowed")
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
    _iface(s, interface_id, claims)
    status = publish_interface(s, interface_id, actor=claims["sub"]).status
    write_audit(s, claims["sub"], "publish_interface", str(interface_id), {})
    return {"status": status}


@router.post("/interfaces/{interface_id}/revoke")
def revoke(interface_id: int, approval_token: str,
           s: Session = Depends(get_session),
           claims: dict = Depends(require_user)):
    if not verify_token(interface_id, "revoke", approval_token):
        raise HTTPException(403, "approval required")
    _iface(s, interface_id, claims)
    i = s.get(Interface, interface_id)
    i.status = 0
    write_audit(s, claims["sub"], "revoke_interface", str(interface_id), {})
    return {"status": 0}


@router.post("/interfaces/{interface_id}/execute")
def execute(interface_id: int, params: dict, s: Session = Depends(get_session),
            claims: dict = Depends(require_user)):
    _iface(s, interface_id, claims)
    rows, total = execute_interface(s, interface_id, params)
    write_audit(s, claims["sub"], "execute_interface", str(interface_id),
                {"rows": total})
    return {"total": total, "results": rows}


@router.delete("/interfaces/{interface_id}", status_code=204)
def delete(interface_id: int, s: Session = Depends(get_session),
           claims: dict = Depends(require_editor)):
    i = _iface(s, interface_id, claims)
    s.delete(i)
    s.commit()
    write_audit(s, claims["sub"], "delete_interface", str(interface_id), {})
    return None
