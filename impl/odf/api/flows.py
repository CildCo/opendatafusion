from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.models import Flow, FlowVersion
from odf.services.audit import write_audit
from odf.services.auth import require_user
from odf.services.flow import create_flow, update_flow

router = APIRouter()


class FlowIn(BaseModel):
    project_id: int = 1
    name: str
    cron: str
    dag: dict


@router.get("/flows")
def list_(project_id: int | None = None,
          s: Session = Depends(get_session),
          claims: dict = Depends(require_user)):
    q = s.query(Flow)
    if project_id is not None:
        q = q.filter_by(project_id=project_id)
    return [{"id": f.id, "name": f.name, "cron": f.cron,
             "status": f.status, "version": f.current_version}
            for f in q.order_by(Flow.id).all()]


@router.get("/flows/{flow_id}")
def get_(flow_id: int, s: Session = Depends(get_session),
         claims: dict = Depends(require_user)):
    f = s.get(Flow, flow_id)
    if not f:
        raise HTTPException(404, "flow not found")
    v = (s.query(FlowVersion)
         .filter_by(flow_id=f.id, version=f.current_version).first())
    return {"id": f.id, "name": f.name, "cron": f.cron, "status": f.status,
            "version": f.current_version, "dag": v.dag_json if v else None}


@router.get("/flows/{flow_id}/versions")
def versions(flow_id: int, s: Session = Depends(get_session),
             claims: dict = Depends(require_user)):
    rows = (s.query(FlowVersion).filter_by(flow_id=flow_id)
            .order_by(FlowVersion.version.desc()).all())
    return [{"version": v.version, "created_by": v.created_by,
             "created_at": v.created_at.isoformat()} for v in rows]


@router.post("/flows")
def create(body: FlowIn, s: Session = Depends(get_session),
           claims: dict = Depends(require_user)):
    f = create_flow(s, body.project_id, body.name, body.cron, body.dag)
    write_audit(s, claims["sub"], "create_flow", str(f.id),
                {"name": body.name, "cron": body.cron})
    return {"id": f.id, "version": f.current_version}


@router.put("/flows/{flow_id}")
def update(flow_id: int, body: FlowIn, s: Session = Depends(get_session),
           claims: dict = Depends(require_user)):
    f = update_flow(s, flow_id, body.dag, actor=claims["sub"])
    write_audit(s, claims["sub"], "update_flow", str(f.id),
                {"version": f.current_version})
    return {"id": f.id, "version": f.current_version}
