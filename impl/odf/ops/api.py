from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.ops import service
from odf.services.auth import require_admin, require_editor, require_user

router = APIRouter()


def _value_error(e):
    msg = str(e)
    raise HTTPException(404 if "not found" in msg else 400, msg)


@router.get("/ops/summary")
def summary(s: Session = Depends(get_session),
            claims: dict = Depends(require_user)):
    return service.summary(s, claims["project_id"])


@router.get("/ops/jobs")
def jobs(status: str | None = None, limit: int = 50,
         s: Session = Depends(get_session),
         claims: dict = Depends(require_user)):
    return service.list_jobs(s, claims["project_id"], status, limit)


@router.post("/ops/jobs/{job_id}/retry")
def retry(job_id: int, s: Session = Depends(get_session),
          claims: dict = Depends(require_editor)):
    try:
        return service.retry_job(s, claims["project_id"], job_id,
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


@router.get("/ops/health")
def health(s: Session = Depends(get_session),
           claims: dict = Depends(require_user)):
    return service.list_health(s, claims["project_id"])


@router.get("/ops/timeline")
def timeline(limit: int = 50, s: Session = Depends(get_session),
             claims: dict = Depends(require_user)):
    return service.timeline(s, claims["project_id"], limit)


@router.get("/ops/audit")
def audit(actor: str | None = None, action: str | None = None,
          q: str | None = None, limit: int = 100,
          s: Session = Depends(get_session),
          claims: dict = Depends(require_admin)):
    return service.search_audit(s, actor, action, q, limit)
