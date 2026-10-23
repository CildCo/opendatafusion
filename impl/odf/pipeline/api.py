from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from odf.assets.service import (create_asset, get_asset, list_assets,
                                list_versions, update_asset, update_draft)
from odf.db import get_session
from odf.models import AssetVersion, Job
from odf.pipeline.cursors import list_cursors, set_cursor
from odf.pipeline.preview import preview_pipeline
from odf.pipeline.runner import PipelineRunError, backfill_content_error
from odf.pipeline.schema import validate_dag
from odf.pipeline.validate import validate_pipeline_content
from odf.services.approval import verify_token
from odf.services.audit import write_audit
from odf.services.auth import require_approver, require_editor, require_user
from odf.services.changes import apply as apply_change
from odf.services.changes import propose
from odf.services.jobs import enqueue_asset
from odf.services.scheduler import cron_to_trigger

router = APIRouter()


class PipelineIn(BaseModel):
    project_id: int = 1
    name: str
    content: dict = Field(default_factory=dict)


class PipelineUpdateIn(BaseModel):
    name: str | None = None
    cron: str | None = None


class ContentIn(BaseModel):
    content: dict


class RollbackIn(BaseModel):
    version: int


class PreviewIn(BaseModel):
    node_id: str
    limit: int = 100
    content: dict | None = None


class BackfillIn(BaseModel):
    start_cursor: str
    end_cursor: str | None = None
    batch: int | None = None
    max_batches: int = 100


class CursorIn(BaseModel):
    node_id: str
    cursor: str | None = None


def _asset(s, asset_id, claims):
    a = get_asset(s, asset_id)
    if not a or a.type != "pipeline" or \
            a.project_id != claims.get("project_id"):
        raise HTTPException(404, "pipeline not found")
    return a


def _bad_request(e):
    return HTTPException(400, str(e))


@router.get("/pipelines")
def list_(s: Session = Depends(get_session),
          claims: dict = Depends(require_user)):
    return [{"id": a.id, "key": a.key, "name": a.name,
             "enabled": a.enabled, "cron": a.cron,
             "published": a.published_version_id is not None}
            for a in list_assets(s, claims["project_id"], "pipeline")]


@router.get("/pipelines/{asset_id}")
def get_(asset_id: int, s: Session = Depends(get_session),
         claims: dict = Depends(require_user)):
    a = _asset(s, asset_id, claims)
    draft = (s.get(AssetVersion, a.draft_version_id)
             if a.draft_version_id else None)
    published = (s.get(AssetVersion, a.published_version_id)
                 if a.published_version_id else None)
    return {"id": a.id, "key": a.key, "name": a.name,
            "enabled": a.enabled, "cron": a.cron,
            "draft_version": draft.version if draft else None,
            "published_version": published.version if published else None,
            "draft": draft.content_json if draft else None,
            "published": published.content_json if published else None}


@router.post("/pipelines")
def create(body: PipelineIn, s: Session = Depends(get_session),
           claims: dict = Depends(require_editor)):
    if body.project_id != claims["project_id"]:
        raise HTTPException(403, "project mismatch")
    a = create_asset(s, body.project_id, "pipeline", body.name,
                     body.content, claims["sub"])
    write_audit(s, claims["sub"], "create_pipeline", str(a.id),
                {"name": body.name})
    return {"id": a.id, "key": a.key}


@router.put("/pipelines/{asset_id}")
def update(asset_id: int, body: PipelineUpdateIn,
           s: Session = Depends(get_session),
           claims: dict = Depends(require_editor)):
    a = _asset(s, asset_id, claims)
    if body.cron is not None and body.cron:
        try:
            cron_to_trigger(body.cron)
        except Exception:
            raise HTTPException(400, "invalid cron expression")
    a = update_asset(s, a.id, body.name, body.cron)
    write_audit(s, claims["sub"], "update_pipeline", str(a.id),
                {"name": a.name, "cron": a.cron})
    return {"id": a.id, "name": a.name, "cron": a.cron}


@router.put("/pipelines/{asset_id}/draft")
def draft(asset_id: int, body: ContentIn, s: Session = Depends(get_session),
          claims: dict = Depends(require_editor)):
    a = _asset(s, asset_id, claims)
    v = update_draft(s, a.id, body.content, claims["sub"])
    write_audit(s, claims["sub"], "update_pipeline_draft", str(a.id),
                {"version": v.version})
    return {"version": v.version}


@router.post("/pipelines/{asset_id}/validate")
def validate(asset_id: int, body: ContentIn, s: Session = Depends(get_session),
             claims: dict = Depends(require_user)):
    a = _asset(s, asset_id, claims)
    errors = validate_pipeline_content(s, body.content, a.project_id)
    return {"valid": not errors, "errors": errors}


@router.get("/pipelines/{asset_id}/versions")
def versions(asset_id: int, s: Session = Depends(get_session),
             claims: dict = Depends(require_user)):
    a = _asset(s, asset_id, claims)
    return [{"version": v.version, "status": v.status,
             "created_by": v.created_by,
             "current": v.id == a.published_version_id,
             "created_at": v.created_at.isoformat()}
            for v in list_versions(s, a.id)]


@router.post("/pipelines/{asset_id}/publish")
def publish(asset_id: int, approval_token: str,
            s: Session = Depends(get_session),
            claims: dict = Depends(require_approver)):
    a = _asset(s, asset_id, claims)
    if not a.draft_version_id:
        raise HTTPException(400, "draft not found")
    v = s.get(AssetVersion, a.draft_version_id)
    errs = (validate_pipeline_content(s, v.content_json, a.project_id)
            if v else [{"message": "draft not found"}])
    if errs:
        raise HTTPException(400, {"errors": errs})
    if not verify_token(a.id, "publish_pipeline", approval_token):
        raise HTTPException(403, "approval required")
    c = propose(s, a.project_id, claims["sub"], "publish_pipeline", a.id)
    try:
        apply_change(s, c.id, approval_token)
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except (ValueError, KeyError) as e:
        raise _bad_request(e)
    s.refresh(a)
    return {"version": s.get(AssetVersion, a.published_version_id).version}


@router.post("/pipelines/{asset_id}/rollback")
def rollback(asset_id: int, body: RollbackIn, approval_token: str,
             s: Session = Depends(get_session),
             claims: dict = Depends(require_approver)):
    a = _asset(s, asset_id, claims)
    if not verify_token(a.id, "rollback_pipeline", approval_token):
        raise HTTPException(403, "approval required")
    c = propose(s, a.project_id, claims["sub"], "rollback_pipeline", a.id,
                {"version": body.version})
    try:
        apply_change(s, c.id, approval_token)
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except (ValueError, KeyError) as e:
        raise _bad_request(e)
    s.refresh(a)
    return {"version": s.get(AssetVersion, a.published_version_id).version}


@router.post("/pipelines/{asset_id}/run")
def run(asset_id: int, s: Session = Depends(get_session),
        claims: dict = Depends(require_editor)):
    a = _asset(s, asset_id, claims)
    if not a.published_version_id:
        raise HTTPException(400, "pipeline is not published")
    job = enqueue_asset(s, a.id, "pipeline")
    write_audit(s, claims["sub"], "run_pipeline", str(a.id),
                {"job_id": job.id})
    return {"job_id": job.id}


@router.get("/pipelines/{asset_id}/cursors")
def cursors(asset_id: int, s: Session = Depends(get_session),
            claims: dict = Depends(require_user)):
    a = _asset(s, asset_id, claims)
    try:
        return list_cursors(s, a)
    except ValueError as e:
        raise _bad_request(e)


@router.put("/pipelines/{asset_id}/cursors")
def update_cursor(asset_id: int, body: CursorIn,
                  s: Session = Depends(get_session),
                  claims: dict = Depends(require_editor)):
    a = _asset(s, asset_id, claims)
    try:
        out = set_cursor(s, a, body.node_id, body.cursor)
    except ValueError as e:
        raise _bad_request(e)
    write_audit(s, claims["sub"], "reset_pipeline_cursor", str(a.id),
                {"node_id": body.node_id, "cursor": body.cursor})
    return out


@router.post("/pipelines/{asset_id}/backfill")
def backfill(asset_id: int, body: BackfillIn,
             s: Session = Depends(get_session),
             claims: dict = Depends(require_editor)):
    a = _asset(s, asset_id, claims)
    if not a.published_version_id:
        raise HTTPException(400, "pipeline is not published")
    version = s.get(AssetVersion, a.published_version_id)
    err = backfill_content_error(version.content_json if version else None)
    if err:
        raise HTTPException(400, err)
    if not body.start_cursor.strip():
        raise HTTPException(400, "start_cursor is required")
    if body.batch is not None and not 1 <= body.batch <= 100000:
        raise HTTPException(400, "batch must be 1..100000")
    if not 1 <= body.max_batches <= 1000:
        raise HTTPException(400, "max_batches must be 1..1000")
    payload = {"start_cursor": body.start_cursor.strip(),
               "end_cursor": body.end_cursor,
               "batch": body.batch,
               "max_batches": body.max_batches}
    try:
        job = enqueue_asset(s, a.id, "pipeline_backfill", payload=payload)
    except ValueError as e:
        raise HTTPException(409, str(e))
    write_audit(s, claims["sub"], "backfill_pipeline", str(a.id),
                {"job_id": job.id, **payload})
    return {"job_id": job.id}


@router.get("/pipelines/{asset_id}/jobs")
def jobs(asset_id: int, s: Session = Depends(get_session),
         claims: dict = Depends(require_user)):
    a = _asset(s, asset_id, claims)
    rows = (s.query(Job).filter(Job.asset_id == a.id,
                                Job.asset_type.in_(
                                    ("pipeline", "pipeline_backfill")))
            .order_by(Job.id.desc()).limit(50).all())
    return [{"id": j.id, "status": j.status, "attempts": j.attempts,
             "asset_type": j.asset_type, "payload": j.payload_json or {},
             "last_error": j.last_error} for j in rows]


@router.post("/pipelines/{asset_id}/preview")
def preview(asset_id: int, body: PreviewIn,
            s: Session = Depends(get_session),
            claims: dict = Depends(require_user)):
    a = _asset(s, asset_id, claims)
    try:
        return preview_pipeline(s, a.id, body.node_id, body.limit,
                                content=body.content)
    except PipelineRunError as e:
        raise HTTPException(400, {"node_id": e.node_id,
                                  "errors": [e.message],
                                  "node_stats": e.stats})
    except ValueError as e:
        raise HTTPException(400, {"node_id": body.node_id,
                                  "errors": [str(e)]})
    except Exception as e:
        raise HTTPException(400, {"node_id": body.node_id,
                                  "errors": [str(e)]})
