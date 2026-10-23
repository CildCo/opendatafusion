from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.services.auth import require_editor, require_user
from odf.services.quality import (create_rule, list_results, list_rules,
                                  run_rule)

router = APIRouter()


class RuleIn(BaseModel):
    project_id: int | None = None
    dataset_id: int
    name: str
    kind: str
    column_name: str | None = None
    config: dict = {}


@router.get("/quality/rules")
def rules(s: Session = Depends(get_session),
          claims: dict = Depends(require_user)):
    return [{"id": r.id, "dataset_id": r.dataset_id, "name": r.name,
             "kind": r.kind, "column": r.column_name, "enabled": r.enabled}
            for r in list_rules(s, claims["project_id"])]


@router.post("/quality/rules")
def create(body: RuleIn, s: Session = Depends(get_session),
           claims: dict = Depends(require_editor)):
    if (body.project_id is not None
            and body.project_id != claims["project_id"]):
        raise HTTPException(403, "project mismatch")
    try:
        r = create_rule(s, claims["project_id"], body.dataset_id, body.name,
                        body.kind, body.column_name, body.config)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"id": r.id}


@router.post("/quality/rules/{rule_id}/run")
def run(rule_id: int, s: Session = Depends(get_session),
        claims: dict = Depends(require_editor)):
    try:
        result = run_rule(s, rule_id, claims["project_id"])
    except ValueError as e:
        raise HTTPException(404, str(e))
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
