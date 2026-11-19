from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.models import Flow, FlowRun, Job
from odf.services.audit import write_audit
from odf.services.auth import require_user
from odf.services.jobs import enqueue

router = APIRouter()


@router.post("/flows/{flow_id}/runs")
def start(flow_id: int, s: Session = Depends(get_session),
          claims: dict = Depends(require_user)):
    flow = s.get(Flow, flow_id)
    if not flow or flow.status != 1:
        raise HTTPException(400, "flow is disabled")
    job = enqueue(s, flow_id)
    write_audit(s, claims["sub"], "trigger_flow", str(flow_id),
                {"job_id": job.id})
    return {"job_id": job.id}


@router.get("/flows/{flow_id}/runs")
def list_runs(flow_id: int, s: Session = Depends(get_session)):
    rows = (s.query(FlowRun).filter_by(flow_id=flow_id)
            .order_by(FlowRun.id.desc()).limit(50).all())
    out = []
    for r in rows:
        ms = None
        if r.started_at and r.finished_at:
            ms = int((r.finished_at - r.started_at).total_seconds() * 1000)
        out.append({"id": r.id, "status": r.status, "in": r.in_num,
                    "out": r.out_num, "err": r.err_num,
                    "cursor": r.cursor_value,
                    "started_at": r.started_at.isoformat()
                    if r.started_at else None,
                    "finished_at": r.finished_at.isoformat()
                    if r.finished_at else None,
                    "duration_ms": ms})
    return out


@router.post("/flows/{flow_id}/runs/{run_id}/retry")
def retry(flow_id: int, run_id: int, s: Session = Depends(get_session),
          claims: dict = Depends(require_user)):
    flow = s.get(Flow, flow_id)
    if not flow or flow.project_id != claims["project_id"]:
        raise HTTPException(404, "flow not found")
    if flow.status != 1:
        raise HTTPException(400, "flow is disabled")
    run = s.get(FlowRun, run_id)
    if not run or run.flow_id != flow_id:
        raise HTTPException(404, "run not found")
    job = enqueue(s, flow_id)
    write_audit(s, claims["sub"], "retry_flow", str(flow_id),
                {"run_id": run_id, "job_id": job.id})
    return {"job_id": job.id}


@router.get("/flows/{flow_id}/jobs")
def list_jobs(flow_id: int, s: Session = Depends(get_session)):
    rows = (s.query(Job).filter_by(flow_id=flow_id)
            .order_by(Job.id.desc()).limit(50).all())
    return [{"id": j.id, "status": j.status, "attempts": j.attempts,
             "run_at": j.run_at.isoformat(), "last_error": j.last_error}
            for j in rows]
