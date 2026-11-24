from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from odf.assets.service import (DraftConflict, create_asset,
                                delete_asset_of, get_asset, list_assets,
                                list_versions, page_assets, update_asset,
                                update_draft)
from odf.dashboards.content import empty_dashboard, validate_dashboard
from odf.dashboards.service import dashboard_data, dashboard_drill
from odf.db import get_session
from odf.models import AssetVersion
from odf.services.approval import verify_token
from odf.services.audit import write_audit
from odf.services.auth import (claims_role, require_approver,
                                require_editor, require_user)
from odf.services.changes import apply as apply_change
from odf.services.changes import propose

router = APIRouter()


class DashboardIn(BaseModel):
    name: str
    project_id: int = 1
    content: dict = Field(default_factory=dict)


class UpdateIn(BaseModel):
    name: str | None = None


class ContentIn(BaseModel):
    content: dict
    base_version: int | None = None


class DataIn(BaseModel):
    limit: int = Field(100, ge=1, le=10000)
    params: dict | None = None
    content: dict | None = None
    published: bool = False


class RollbackIn(BaseModel):
    version: int


class DrillIn(BaseModel):
    widget_id: str
    dimension: str | None = None
    value: object | None = None
    params: dict | None = None
    limit: int = Field(100, ge=1, le=10000)


class ReportIn(BaseModel):
    cron: str
    enabled: bool = True


def _asset(s, asset_id, claims):
    a = get_asset(s, asset_id)
    if not a or a.type != "dashboard" or \
            a.project_id != claims.get("project_id"):
        raise HTTPException(404, "dashboard not found")
    return a


def _get(s, a):
    draft = s.get(AssetVersion, a.draft_version_id) if a.draft_version_id else None
    pub = s.get(AssetVersion, a.published_version_id) if a.published_version_id else None
    return {"id": a.id, "key": a.key, "name": a.name,
            "draft_version": draft.version if draft else None,
            "published_version": pub.version if pub else None,
            "draft": draft.content_json if draft else None,
            "published": pub.content_json if pub else None}


@router.get("/dashboards")
def list_(page: int = 1, page_size: int = 50, q: str | None = None,
          s: Session = Depends(get_session),
          claims: dict = Depends(require_user)):
    from odf.services.pagination import envelope
    rows, total, page, page_size = page_assets(
        s, claims["project_id"], "dashboard", page, page_size, q)
    return envelope([{"id": a.id, "key": a.key, "name": a.name,
                      "published": a.published_version_id is not None}
                     for a in rows], total, page, page_size)


@router.post("/dashboards")
def create(body: DashboardIn, s: Session = Depends(get_session),
           claims: dict = Depends(require_editor)):
    if body.project_id != claims["project_id"]:
        raise HTTPException(403, "project mismatch")
    a = create_asset(s, body.project_id, "dashboard", body.name,
                     body.content or empty_dashboard(), claims["sub"],
                     enabled=False)
    write_audit(s, claims["sub"], "create_dashboard", str(a.id),
                {"name": body.name})
    return {"id": a.id, "key": a.key}


@router.delete("/dashboards/{asset_id}", status_code=204)
def delete(asset_id: int, s: Session = Depends(get_session),
           claims: dict = Depends(require_editor)):
    try:
        delete_asset_of(s, asset_id, claims["project_id"], "dashboard")
    except ValueError as e:
        raise HTTPException(404, str(e))
    write_audit(s, claims["sub"], "delete_dashboard", str(asset_id), {})
    return None


@router.get("/dashboards/{asset_id}")
def get_(asset_id: int, s: Session = Depends(get_session),
         claims: dict = Depends(require_user)):
    return _get(s, _asset(s, asset_id, claims))


@router.put("/dashboards/{asset_id}")
def update(asset_id: int, body: UpdateIn, s: Session = Depends(get_session),
           claims: dict = Depends(require_editor)):
    a = _asset(s, asset_id, claims)
    a = update_asset(s, a.id, body.name, None)
    write_audit(s, claims["sub"], "update_dashboard", str(a.id),
                {"name": a.name})
    return {"id": a.id, "name": a.name}


@router.put("/dashboards/{asset_id}/draft")
def draft(asset_id: int, body: ContentIn,
          s: Session = Depends(get_session),
          claims: dict = Depends(require_editor)):
    a = _asset(s, asset_id, claims)
    try:
        v = update_draft(s, a.id, body.content, claims["sub"],
                         base_version=body.base_version)
    except DraftConflict as error:
        raise HTTPException(409, str(error))
    write_audit(s, claims["sub"], "update_dashboard_draft", str(a.id),
                {"version": v.version})
    return {"version": v.version}


@router.post("/dashboards/{asset_id}/validate")
def validate(asset_id: int, body: ContentIn,
             s: Session = Depends(get_session),
             claims: dict = Depends(require_user)):
    a = _asset(s, asset_id, claims)
    errs = validate_dashboard(s, body.content, a.project_id)
    return {"valid": not errs, "errors": errs}


@router.post("/dashboards/{asset_id}/data")
def data(asset_id: int, body: DataIn, s: Session = Depends(get_session),
         claims: dict = Depends(require_user)):
    a = _asset(s, asset_id, claims)
    try:
        result = dashboard_data(s, a.id, body.params, body.content,
                                body.limit, published_only=body.published,
                                role=claims_role(s, claims))
    except ValueError as e:
        raise HTTPException(400, str(e))
    write_audit(s, claims["sub"], "query_dashboard", str(a.id),
                {"widgets": len(result["widgets"])})
    return result


@router.post("/dashboards/{asset_id}/drill")
def drill(asset_id: int, body: DrillIn, s: Session = Depends(get_session),
          claims: dict = Depends(require_user)):
    a = _asset(s, asset_id, claims)
    try:
        result = dashboard_drill(
            s, a.id, body.widget_id, body.dimension, body.value,
            body.params, body.limit, role=claims_role(s, claims))
    except ValueError as e:
        raise HTTPException(400, str(e))
    write_audit(s, claims["sub"], "drill_dashboard", str(a.id),
                {"widget": body.widget_id, "dimension": body.dimension})
    return result


@router.get("/dashboards/{asset_id}/report")
def get_report(asset_id: int, s: Session = Depends(get_session),
               claims: dict = Depends(require_user)):
    from odf.dashboards.report import schedule_for
    from odf.models import Job
    a = _asset(s, asset_id, claims)
    runs = (s.query(Job)
            .filter(Job.asset_id == a.id,
                    Job.asset_type == "dashboard_report")
            .order_by(Job.id.desc()).limit(20).all())
    return {"schedule": schedule_for(s, a.project_id, a.id),
            "runs": [{"id": job.id, "status": job.status,
                      "created_at": job.created_at.isoformat(),
                      "finished_at": (job.finished_at.isoformat()
                                      if job.finished_at else None),
                      "error": job.last_error} for job in runs]}


@router.put("/dashboards/{asset_id}/report")
def put_report(asset_id: int, body: ReportIn,
               s: Session = Depends(get_session),
               claims: dict = Depends(require_editor)):
    from odf.dashboards.report import upsert_schedule
    a = _asset(s, asset_id, claims)
    try:
        return upsert_schedule(s, a.project_id, a.id, body.cron,
                               body.enabled, claims["sub"])
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/dashboards/{asset_id}/report", status_code=204)
def delete_report(asset_id: int, s: Session = Depends(get_session),
                  claims: dict = Depends(require_editor)):
    from odf.dashboards.report import delete_schedule
    a = _asset(s, asset_id, claims)
    try:
        delete_schedule(s, a.project_id, a.id, claims["sub"])
    except ValueError as e:
        raise HTTPException(404, str(e))
    return None


@router.post("/dashboards/{asset_id}/report/run")
def run_report_now(asset_id: int, s: Session = Depends(get_session),
                   claims: dict = Depends(require_editor)):
    from odf.dashboards.report import schedule_for
    from odf.services.jobs import enqueue_asset
    a = _asset(s, asset_id, claims)
    schedule = schedule_for(s, a.project_id, a.id)
    if not schedule:
        raise HTTPException(400, "report schedule not found")
    job = enqueue_asset(s, a.id, "dashboard_report",
                        {"schedule_id": schedule["id"]})
    write_audit(s, claims["sub"], "run_dashboard_report_now", str(a.id),
                {"job_id": job.id})
    return {"job_id": job.id}


@router.get("/dashboards/{asset_id}/export.csv")
def export_csv(asset_id: int, s: Session = Depends(get_session),
               claims: dict = Depends(require_user)):
    from fastapi import Response
    from odf.dashboards.render import dashboard_csv
    a = _asset(s, asset_id, claims)
    if not a.published_version_id:
        raise HTTPException(400, "dashboard is not published")
    try:
        result = dashboard_data(s, a.id, None, None, 10000,
                                published_only=True,
                                role=claims_role(s, claims))
        content, count = dashboard_csv(result)
    except ValueError as error:
        raise HTTPException(400, str(error))
    write_audit(s, claims["sub"], "export_dashboard", str(a.id),
                {"widgets": count})
    filename = "dashboard-%d.csv" % a.id
    return Response(content=content, media_type="text/csv",
                    headers={"Content-Disposition":
                             'attachment; filename="%s"' % filename})


@router.get("/dashboards/{asset_id}/versions")
def versions(asset_id: int, s: Session = Depends(get_session),
             claims: dict = Depends(require_user)):
    a = _asset(s, asset_id, claims)
    return [{"version": v.version, "status": v.status,
             "current": v.id == a.published_version_id,
             "created_by": v.created_by,
             "created_at": v.created_at.isoformat()}
            for v in list_versions(s, a.id)]


def _change(s, a, action, claims, token, payload=None):
    if not verify_token(a.id, action, token):
        raise HTTPException(403, "approval required")
    c = propose(s, a.project_id, claims["sub"], action, a.id, payload or {})
    try:
        apply_change(s, c.id, token)
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except (ValueError, KeyError) as e:
        raise HTTPException(400, str(e))


@router.post("/dashboards/{asset_id}/publish")
def publish(asset_id: int, approval_token: str,
            s: Session = Depends(get_session),
            claims: dict = Depends(require_approver)):
    a = _asset(s, asset_id, claims)
    v = s.get(AssetVersion, a.draft_version_id) if a.draft_version_id else None
    if not v:
        raise HTTPException(400, "draft not found")
    errs = validate_dashboard(s, v.content_json, a.project_id)
    if errs:
        raise HTTPException(400, {"errors": errs})
    _change(s, a, "publish_dashboard", claims, approval_token)
    s.refresh(a)
    return {"version": s.get(AssetVersion, a.published_version_id).version}


@router.post("/dashboards/{asset_id}/rollback")
def rollback(asset_id: int, body: RollbackIn, approval_token: str,
             s: Session = Depends(get_session),
             claims: dict = Depends(require_approver)):
    a = _asset(s, asset_id, claims)
    _change(s, a, "rollback_dashboard", claims, approval_token,
            {"version": body.version})
    s.refresh(a)
    return {"version": s.get(AssetVersion, a.published_version_id).version}
