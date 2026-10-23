from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.models import (Alert, Asset, Datasource, Flow, FlowRun, Interface,
                        Job, PipelineNodeRun, QualityRule)
from odf.services.auth import require_user

router = APIRouter()

_JOB_STATUS = {"queued": 0, "running": 1, "success": 2, "failed": 3}


def _flow_runs(s, project_id, since):
    base = (s.query(FlowRun)
            .join(Flow, FlowRun.flow_id == Flow.id)
            .filter(Flow.project_id == project_id))
    recent = (base.order_by(FlowRun.id.desc()).limit(8).all())
    return {
        "runs_24h": base.filter(FlowRun.started_at >= since).count(),
        "running": base.filter(FlowRun.status == 1).count(),
        "failed_24h": base.filter(FlowRun.status == 3,
                                  FlowRun.started_at >= since).count(),
        "recent": recent,
    }


def _pipeline_runs(s, project_id, since):
    base = (s.query(Job)
            .join(Asset, Job.asset_id == Asset.id)
            .filter(Asset.project_id == project_id,
                    Job.asset_type.in_(("pipeline", "pipeline_backfill"))))
    recent = (base.order_by(Job.id.desc()).limit(8).all())
    return {
        "runs_24h": base.filter(Job.created_at >= since).count(),
        "running": base.filter(Job.status == "running").count(),
        "failed_24h": base.filter(Job.status == "failed",
                                  Job.created_at >= since).count(),
        "recent": recent,
    }


def _pipeline_stats(s, job_ids):
    if not job_ids:
        return {}
    rows = (s.query(PipelineNodeRun.job_id,
                    func.max(PipelineNodeRun.in_num),
                    func.max(PipelineNodeRun.out_num),
                    func.sum(case((PipelineNodeRun.error.is_not(None), 1),
                                  else_=0)))
            .filter(PipelineNodeRun.job_id.in_(job_ids))
            .group_by(PipelineNodeRun.job_id).all())
    return {job_id: {"in": in_num or 0, "out": out_num or 0,
                     "err": int(err or 0)}
            for job_id, in_num, out_num, err in rows}


@router.get("/dashboard")
def dashboard(s: Session = Depends(get_session),
              claims: dict = Depends(require_user)):
    project_id = (claims["project_id"] if isinstance(claims, dict)
                  else claims.project_id)
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    flows = _flow_runs(s, project_id, since)
    pipes = _pipeline_runs(s, project_id, since)
    stats = _pipeline_stats(s, [j.id for j in pipes["recent"]])

    recent = []
    for r in flows["recent"]:
        name = s.get(Flow, r.flow_id).name
        recent.append({"id": r.id, "flow": name, "status": r.status,
                       "in": r.in_num, "out": r.out_num, "err": r.err_num,
                       "started_at": r.started_at.isoformat(),
                       "kind": "flow", "flow_id": r.flow_id})
    for j in pipes["recent"]:
        asset = s.get(Asset, j.asset_id)
        row = stats.get(j.id, {"in": 0, "out": 0, "err": 0})
        recent.append({
            "id": j.id, "flow": asset.name if asset else "pipeline",
            "status": _JOB_STATUS.get(j.status, 0),
            "in": row["in"], "out": row["out"],
            "err": row["err"] + (1 if j.last_error else 0),
            "started_at": j.created_at.isoformat(), "kind": "pipeline",
            "asset_id": j.asset_id,
        })
    recent.sort(key=lambda x: x["started_at"], reverse=True)

    return {
        "datasources": s.query(func.count(Datasource.id))
                         .filter(Datasource.project_id == project_id).scalar(),
        "flows": s.query(func.count(Flow.id))
                  .filter(Flow.project_id == project_id).scalar(),
        "interfaces": s.query(func.count(Interface.id))
                       .filter(Interface.project_id == project_id).scalar(),
        "quality_rules": s.query(func.count(QualityRule.id))
                          .filter(QualityRule.project_id == project_id).scalar(),
        "open_alerts": s.query(func.count(Alert.id))
                        .filter(Alert.project_id == project_id,
                                Alert.status == "open").scalar(),
        "runs_24h": flows["runs_24h"] + pipes["runs_24h"],
        "running_runs": flows["running"] + pipes["running"],
        "failed_24h": flows["failed_24h"] + pipes["failed_24h"],
        "recent_runs": recent[:8],
    }
