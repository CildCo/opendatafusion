from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.ops import service
from odf.services.auth import require_admin, require_editor, require_user

router = APIRouter()


class ReplayIn(BaseModel):
    ids: list[int]


class RunPolicyIn(BaseModel):
    max_attempts: int = 3
    retry_backoff_seconds: int = 30
    priority: int = 0
    max_duration_seconds: int = 0


def _value_error(e):
    msg = str(e)
    raise HTTPException(404 if "not found" in msg else 400, msg)


@router.get("/ops/summary")
def summary(s: Session = Depends(get_session),
            claims: dict = Depends(require_user)):
    return service.summary(s, claims["project_id"])


@router.get("/ops/run-matrix")
def run_matrix(days: int = 7, s: Session = Depends(get_session),
               claims: dict = Depends(require_user)):
    return service.run_matrix(s, claims["project_id"], days)


@router.get("/ops/run-health")
def run_health(days: int = 30, s: Session = Depends(get_session),
               claims: dict = Depends(require_user)):
    return service.run_health(s, claims["project_id"], days)


@router.get("/ops/cost")
def cost(days: int = 30, s: Session = Depends(get_session),
         claims: dict = Depends(require_user)):
    return service.cost_report(s, claims["project_id"], days)


@router.get("/ops/schedules")
def schedules(s: Session = Depends(get_session),
              claims: dict = Depends(require_user)):
    return service.schedules(s, claims["project_id"])


@router.get("/ops/run-policies")
def run_policies(s: Session = Depends(get_session),
                 claims: dict = Depends(require_user)):
    return service.run_policies(s, claims["project_id"])


@router.put("/ops/run-policies/{asset_id}")
def update_run_policy(asset_id: int, body: RunPolicyIn,
                      s: Session = Depends(get_session),
                      claims: dict = Depends(require_editor)):
    try:
        return service.update_run_policy(
            s, claims["project_id"], asset_id, body.max_attempts,
            body.retry_backoff_seconds, claims["sub"],
            body.priority, body.max_duration_seconds)
    except ValueError as e:
        _value_error(e)


@router.get("/ops/jobs")

def jobs(status: str | None = None, limit: int = 50,
         s: Session = Depends(get_session),
         claims: dict = Depends(require_user)):
    return service.list_jobs(s, claims["project_id"], status, limit)


@router.get("/ops/dead-letters")
def dead_letters(asset_type: str | None = None,
                 since: datetime | None = None, limit: int = 100,
                 s: Session = Depends(get_session),
                 claims: dict = Depends(require_user)):
    return service.dead_letters(s, claims["project_id"], asset_type,
                                since, limit)


@router.post("/ops/dead-letters/replay")
def replay_dead_letters(body: ReplayIn, s: Session = Depends(get_session),
                        claims: dict = Depends(require_editor)):
    if not body.ids or len(body.ids) > 100:
        raise HTTPException(400, "select between 1 and 100 jobs")
    try:
        return service.replay_jobs(s, claims["project_id"], body.ids,
                                   claims["sub"])
    except ValueError:
        raise HTTPException(400, "could not replay the selected jobs")


@router.get("/ops/jobs/{job_id}/detail")
def job_detail(job_id: int, s: Session = Depends(get_session),
               claims: dict = Depends(require_user)):
    try:
        return service.job_detail(s, claims["project_id"], job_id)
    except ValueError as e:
        _value_error(e)


@router.get("/ops/jobs/{job_id}/compare")
def job_compare(job_id: int, s: Session = Depends(get_session),
                claims: dict = Depends(require_user)):
    try:
        return service.job_compare(s, claims["project_id"], job_id)
    except ValueError as e:
        _value_error(e)


@router.post("/ops/jobs/{job_id}/retry")
def retry(job_id: int, s: Session = Depends(get_session),
          claims: dict = Depends(require_editor)):
    try:
        return service.retry_job(s, claims["project_id"], job_id,
                                 claims["sub"])
    except ValueError as e:
        _value_error(e)


@router.post("/ops/jobs/{job_id}/cancel")
def cancel(job_id: int, s: Session = Depends(get_session),
           claims: dict = Depends(require_editor)):
    try:
        return service.cancel_job(s, claims["project_id"], job_id,
                                  claims["sub"])
    except ValueError as e:
        _value_error(e)


@router.get("/ops/alerts")
def alerts(status: str | None = None, severity: str | None = None,
           s: Session = Depends(get_session),
           claims: dict = Depends(require_user)):
    return service.list_alerts(s, claims["project_id"], status, severity)


@router.post("/ops/alerts/{alert_id}/ack")
def ack(alert_id: int, s: Session = Depends(get_session),
        claims: dict = Depends(require_editor)):
    try:
        return service.ack_alert(s, claims["project_id"], alert_id,
                                 claims["sub"])
    except ValueError as e:
        _value_error(e)


@router.post("/ops/alerts/{alert_id}/close")
def close(alert_id: int, s: Session = Depends(get_session),
          claims: dict = Depends(require_editor)):
    try:
        return service.close_alert(s, claims["project_id"], alert_id,
                                   claims["sub"])
    except ValueError as e:
        _value_error(e)


@router.get("/ops/timeline")
def timeline(limit: int = 50, s: Session = Depends(get_session),
             claims: dict = Depends(require_user)):
    return service.timeline(s, claims["project_id"], limit)


@router.get("/ops/dependency-status")
def dependency_status(hours: int = 24, limit: int = 50,
                      s: Session = Depends(get_session),
                      claims: dict = Depends(require_user)):
    from odf.services.dependencies import recent_blocked
    return recent_blocked(s, claims["project_id"], hours, limit)


@router.get("/ops/audit")
def audit(actor: str | None = None, action: str | None = None,
          q: str | None = None, limit: int = 100,
          s: Session = Depends(get_session),
          claims: dict = Depends(require_admin)):
    return service.search_audit(s, actor, action, q, limit)
