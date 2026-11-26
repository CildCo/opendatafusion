from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.ops.service import ack_alert as ack_scoped
from odf.ops.service import close_alert as close_scoped
from odf.models import Alert, User
from odf.services.alerts import (add_alert_note, alert_assignees,
                                 assign_alert, create_rule, delete_rule,
                                 alert_notes_dict, list_alert_notes,
                                 list_alerts, list_rules)
from odf.services.auth import require_editor, require_user

router = APIRouter()


class RuleIn(BaseModel):
    project_id: int = 1
    name: str
    kind: str
    config: dict = {}


class AssignIn(BaseModel):
    assignee: str = ""


class NoteIn(BaseModel):
    body: str


def _actor(s, claims):
    user = s.get(User, int(claims["sub"]))
    return user.username if user else claims["sub"]


def _alert_dict(s, a, with_notes=False):
    out = {"id": a.id, "severity": a.severity, "title": a.title,
           "status": a.status, "detail": a.detail_json,
           "created_at": a.created_at.isoformat(),
           "acked_at": a.acked_at.isoformat() if a.acked_at else None,
           "closed_at": a.closed_at.isoformat() if a.closed_at else None,
           "assigned_to": a.assigned_to, "acked_by": a.acked_by,
           "closed_by": a.closed_by}
    if with_notes:
        out["notes"] = alert_notes_dict(
            list_alert_notes(s, a.project_id, a.id))
    return out


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


@router.delete("/alerts/rules/{rule_id}", status_code=204)
def remove_rule(rule_id: int, s: Session = Depends(get_session),
                claims: dict = Depends(require_editor)):
    try:
        delete_rule(s, claims["project_id"], rule_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return None


@router.get("/alerts")
def alerts(status: str | None = None, page: int = 1, page_size: int = 50,
           s: Session = Depends(get_session),
           claims: dict = Depends(require_user)):
    from odf.services.pagination import envelope, limits
    page, page_size = limits(page, page_size)
    rows = [_alert_dict(s, a)
            for a in list_alerts(s, claims["project_id"], status)]
    start = (page - 1) * page_size
    return envelope(rows[start:start + page_size], len(rows), page, page_size)


@router.get("/alerts/assignees")
def assignees(s: Session = Depends(get_session),
              claims: dict = Depends(require_user)):
    return alert_assignees(s, claims["project_id"])


@router.get("/alerts/{alert_id}")
def detail(alert_id: int, s: Session = Depends(get_session),
           claims: dict = Depends(require_user)):
    a = s.get(Alert, alert_id)
    if not a or a.project_id != claims["project_id"]:
        raise HTTPException(404, "alert not found")
    return _alert_dict(s, a, with_notes=True)


@router.post("/alerts/{alert_id}/ack")
def ack(alert_id: int, s: Session = Depends(get_session),
        claims: dict = Depends(require_editor)):
    try:
        result = ack_scoped(s, claims["project_id"], alert_id,
                            _actor(s, claims))
        return result
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/alerts/{alert_id}/close")
def close(alert_id: int, s: Session = Depends(get_session),
          claims: dict = Depends(require_editor)):
    try:
        return close_scoped(s, claims["project_id"], alert_id,
                            _actor(s, claims))
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/alerts/{alert_id}/assign")
def assign(alert_id: int, body: AssignIn,
           s: Session = Depends(get_session),
           claims: dict = Depends(require_editor)):
    try:
        a = assign_alert(s, claims["project_id"], alert_id, body.assignee,
                         _actor(s, claims))
        return _alert_dict(s, a)
    except ValueError as e:
        raise HTTPException(404 if "not found" in str(e) else 400, str(e))


@router.post("/alerts/{alert_id}/notes", status_code=201)
def note(alert_id: int, body: NoteIn,
         s: Session = Depends(get_session),
         claims: dict = Depends(require_editor)):
    try:
        row = add_alert_note(s, claims["project_id"], alert_id,
                             _actor(s, claims), body.body)
        return {"id": row.id, "actor": row.actor, "body": row.body,
                "created_at": row.created_at.isoformat()}
    except ValueError as e:
        raise HTTPException(404 if "not found" in str(e) else 400, str(e))
