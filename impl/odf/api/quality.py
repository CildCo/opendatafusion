from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.services.audit import write_audit
from odf.services.auth import require_editor, require_user
from odf.services.quality import (create_rule, delete_rule,
                                  list_results, rule_summaries, run_rule)

router = APIRouter()


class RuleIn(BaseModel):
    project_id: int | None = None
    dataset_id: int
    name: str
    kind: str
    column_name: str | None = None
    config: dict = {}
    schedule_cron: str | None = None
    alert_on_fail: bool = False
    sla_percent: int | None = None


class RuleUpdateIn(BaseModel):
    schedule_cron: str | None = None
    alert_on_fail: bool | None = None
    enabled: bool | None = None
    sla_percent: int | None = None


@router.get("/quality/rules")
def rules(page: int = 1, page_size: int = 50,
          s: Session = Depends(get_session),
          claims: dict = Depends(require_user)):
    from odf.services.pagination import envelope, limits
    page, page_size = limits(page, page_size)
    rows = rule_summaries(s, claims["project_id"])
    start = (page - 1) * page_size
    return envelope(rows[start:start + page_size], len(rows), page, page_size)


@router.post("/quality/rules")
def create(body: RuleIn, s: Session = Depends(get_session),
           claims: dict = Depends(require_editor)):
    if (body.project_id is not None
            and body.project_id != claims["project_id"]):
        raise HTTPException(403, "project mismatch")
    try:
        r = create_rule(s, claims["project_id"], body.dataset_id, body.name,
                        body.kind, body.column_name, body.config)
        r.schedule_cron = (body.schedule_cron or None)
        r.alert_on_fail = bool(body.alert_on_fail)
        if body.sla_percent is not None:
            if not 0 <= int(body.sla_percent) <= 100:
                raise HTTPException(400, "sla_percent must be 0..100")
            r.config_json = {**(r.config_json or {}),
                             "sla_percent": int(body.sla_percent)}
        s.commit()
    except ValueError as e:
        raise HTTPException(404, str(e))
    write_audit(s, claims["sub"], "create_quality_rule", str(r.id),
                {"name": r.name, "kind": r.kind,
                 "dataset_id": r.dataset_id,
                 "column": r.column_name})
    return {"id": r.id}


@router.put("/quality/rules/{rule_id}")
def update(rule_id: int, body: RuleUpdateIn,
           s: Session = Depends(get_session),
           claims: dict = Depends(require_editor)):
    from odf.models import QualityRule
    rule = s.get(QualityRule, rule_id)
    if not rule or rule.project_id != claims["project_id"]:
        raise HTTPException(404, "rule not found")
    if body.schedule_cron is not None:
        rule.schedule_cron = body.schedule_cron or None
    if body.alert_on_fail is not None:
        rule.alert_on_fail = bool(body.alert_on_fail)
    if body.enabled is not None:
        rule.enabled = bool(body.enabled)
    if body.sla_percent is not None:
        if not 0 <= int(body.sla_percent) <= 100:
            raise HTTPException(400, "sla_percent must be 0..100")
        rule.config_json = {**(rule.config_json or {}),
                            "sla_percent": int(body.sla_percent)}
    s.commit()
    return {"id": rule.id, "schedule_cron": rule.schedule_cron,
            "alert_on_fail": bool(rule.alert_on_fail),
            "enabled": bool(rule.enabled),
            "sla_percent": (rule.config_json or {}).get("sla_percent")}


@router.get("/quality/trends")
def trends(days: int = 30, s: Session = Depends(get_session),
           claims: dict = Depends(require_user)):
    from odf.services.quality import trends as quality_trends
    return quality_trends(s, claims["project_id"], days)


@router.delete("/quality/rules/{rule_id}", status_code=204)
def remove(rule_id: int, s: Session = Depends(get_session),
           claims: dict = Depends(require_editor)):
    try:
        delete_rule(s, claims["project_id"], rule_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    write_audit(s, claims["sub"], "delete_quality_rule", str(rule_id), {})
    return None


@router.post("/quality/rules/{rule_id}/run")
def run(rule_id: int, s: Session = Depends(get_session),
        claims: dict = Depends(require_editor)):
    try:
        result = run_rule(s, rule_id, claims["project_id"])
    except ValueError as e:
        raise HTTPException(404, str(e))
    write_audit(s, claims["sub"], "run_quality_rule", str(rule_id),
                {"result_id": result.id, "status": result.status})
    return {"id": result.id, "status": result.status,
            "detail": result.detail_json}


@router.get("/quality/rules/{rule_id}/results")
def results(rule_id: int, s: Session = Depends(get_session),
            claims: dict = Depends(require_user)):
    try:
        rows = list_results(s, rule_id, claims["project_id"])
    except ValueError as e:
        raise HTTPException(404, str(e))
    return [{"id": r.id, "status": r.status, "detail": r.detail_json,
             "at": r.at.isoformat()} for r in rows]
