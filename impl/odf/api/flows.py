from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.models import (Flow, FlowRun, FlowVersion, HealthEvent, Job,
                        JobDependency)
from odf.services.audit import write_audit
from odf.services.auth import require_editor, require_user
from odf.services.flow import create_flow, update_flow

router = APIRouter()


class FlowIn(BaseModel):
    project_id: int = 1
    name: str
    cron: str
    dag: dict


def _flow(session, flow_id: int, claims: dict) -> Flow:
    f = session.get(Flow, flow_id)
    if not f or f.project_id != claims.get("project_id"):
        raise HTTPException(404, "flow not found")
    return f


@router.get("/flows")
def list_(s: Session = Depends(get_session),
          claims: dict = Depends(require_user)):
    return [{"id": f.id, "name": f.name, "cron": f.cron,
             "status": f.status, "version": f.current_version}
            for f in (s.query(Flow)
                      .filter_by(project_id=claims["project_id"])
                      .order_by(Flow.id).all())]


@router.get("/flows/{flow_id}")
def get_(flow_id: int, s: Session = Depends(get_session),
         claims: dict = Depends(require_user)):
    f = _flow(s, flow_id, claims)
    v = (s.query(FlowVersion)
         .filter_by(flow_id=f.id, version=f.current_version).first())
    return {"id": f.id, "name": f.name, "cron": f.cron, "status": f.status,
            "version": f.current_version, "dag": v.dag_json if v else None}


@router.get("/flows/{flow_id}/versions")
def versions(flow_id: int, s: Session = Depends(get_session),
             claims: dict = Depends(require_user)):
    _flow(s, flow_id, claims)
    rows = (s.query(FlowVersion).filter_by(flow_id=flow_id)
            .order_by(FlowVersion.version.desc()).all())
    return [{"version": v.version, "created_by": v.created_by,
             "created_at": v.created_at.isoformat()} for v in rows]


@router.get("/flows/{flow_id}/versions/{version}")
def version_detail(flow_id: int, version: int,
                   s: Session = Depends(get_session),
                   claims: dict = Depends(require_user)):
    _flow(s, flow_id, claims)
    v = (s.query(FlowVersion)
         .filter_by(flow_id=flow_id, version=version).first())
    if not v:
        raise HTTPException(404, "version not found")
    return {"version": v.version, "created_by": v.created_by,
            "created_at": v.created_at.isoformat(), "dag": v.dag_json}


@router.post("/flows")
def create(body: FlowIn, s: Session = Depends(get_session),
           claims: dict = Depends(require_user)):
    if body.project_id != claims["project_id"]:
        raise HTTPException(403, "cross-project flow creation is not allowed")
    f = create_flow(s, body.project_id, body.name, body.cron, body.dag)
    write_audit(s, claims["sub"], "create_flow", str(f.id),
                {"name": body.name, "cron": body.cron})
    return {"id": f.id, "version": f.current_version}


@router.put("/flows/{flow_id}")
def update(flow_id: int, body: FlowIn, s: Session = Depends(get_session),
           claims: dict = Depends(require_user)):
    _flow(s, flow_id, claims)
    f = update_flow(s, flow_id, body.dag, actor=claims["sub"])
    write_audit(s, claims["sub"], "update_flow", str(f.id),
                {"version": f.current_version})
    return {"id": f.id, "version": f.current_version}


@router.delete("/flows/{flow_id}", status_code=204)
def delete(flow_id: int, s: Session = Depends(get_session),
           claims: dict = Depends(require_editor)):
    f = _flow(s, flow_id, claims)
    s.query(JobDependency).filter(or_(
        and_(JobDependency.downstream_type == "flow",
             JobDependency.downstream_id == flow_id),
        and_(JobDependency.upstream_type == "flow",
             JobDependency.upstream_id == flow_id),
    )).delete(synchronize_session=False)
    s.query(Job).filter(Job.flow_id == flow_id).delete(
        synchronize_session=False)
    s.query(FlowRun).filter_by(flow_id=flow_id).delete(
        synchronize_session=False)
    s.query(HealthEvent).filter_by(flow_id=flow_id).delete(
        synchronize_session=False)
    s.query(FlowVersion).filter_by(flow_id=flow_id).delete(
        synchronize_session=False)
    s.delete(f)
    s.commit()
    write_audit(s, claims["sub"], "delete_flow", str(flow_id), {})
    return None
