from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.ops.service import ack_alert as ack_scoped
from odf.ops.service import close_alert as close_scoped
from odf.services.alerts import create_rule, list_alerts, list_rules
from odf.services.auth import require_editor, require_user

router = APIRouter()


class RuleIn(BaseModel):
    project_id: int = 1
    name: str
    kind: str
    config: dict = {}


@router.get("/alerts/rules")
def rules(s: Session = Depends(get_session),
          claims: dict = Depends(require_user)):
    return [{"id": r.id, "name": r.name, "kind": r.kind,
             "enabled": r.enabled}
            for r in list_rules(s, claims["project_id"])]


@router.post("/alerts/rules")
def create(body: RuleIn, s: Session = Depends(get_session),
           claims: dict = Depends(require_editor)):
    r = create_rule(s, claims["project_id"], body.name, body.kind,
                    body.config)
    return {"id": r.id}


@router.get("/alerts")
def alerts(status: str | None = None, s: Session = Depends(get_session),
           claims: dict = Depends(require_user)):
    return [{"id": a.id, "severity": a.severity, "title": a.title,
             "status": a.status, "detail": a.detail_json,
             "created_at": a.created_at.isoformat()}
            for a in list_alerts(s, claims["project_id"], status)]


@router.post("/alerts/{alert_id}/ack")
def ack(alert_id: int, s: Session = Depends(get_session),
        claims: dict = Depends(require_editor)):
    try:
        return ack_scoped(s, claims["project_id"], alert_id, claims["sub"])
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/alerts/{alert_id}/close")
def close(alert_id: int, s: Session = Depends(get_session),
          claims: dict = Depends(require_editor)):
    try:
        return close_scoped(s, claims["project_id"], alert_id, claims["sub"])
    except ValueError as e:
        raise HTTPException(404, str(e))
