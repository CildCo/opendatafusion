from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.models import Flow, FlowRun
from odf.services.alerts import evaluate_health
from odf.services.auth import require_user
from odf.services.health import (compute_health, cron_period_seconds,
                                  evaluate_and_record)

router = APIRouter()


@router.get("/health/snapshot")
def snapshot(s: Session = Depends(get_session),
             claims: dict = Depends(require_user)):
    now = datetime.now(timezone.utc)
    out = []
    for f in s.query(Flow).filter_by(project_id=claims["project_id"]).all():
        runs = (s.query(FlowRun).filter_by(flow_id=f.id)
                .order_by(FlowRun.id.desc()).limit(20).all())
        period = cron_period_seconds(f.cron)
        h = compute_health(runs, now, period)
        evaluate_and_record(s, f.id, h, period)
        evaluate_health(s, f.project_id, f.id, f.name, h)
        out.append({"flow_id": f.id, "name": f.name, **h})
    return out
