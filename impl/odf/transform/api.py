from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from odf.assets.service import (DraftConflict, create_asset,
                                delete_asset_of, get_asset, list_versions,
                                page_assets, update_asset, update_draft)
from odf.db import get_session
from odf.models import AssetVersion
from odf.services.approval import verify_token
from odf.services.audit import write_audit
from odf.services.auth import require_approver, require_editor, require_user
from odf.services.changes import apply as apply_change
from odf.services.changes import propose
from odf.services.jobs import enqueue_asset
from odf.transform.content import empty_model, validate_model
from odf.transform.service import (model_target, preview_model,
                                   sync_model_graph)

router = APIRouter()


class ModelIn(BaseModel):
    name: str
    project_id: int = 1
    content: dict = Field(default_factory=dict)


class UpdateIn(BaseModel):
    name: str | None = None


class ContentIn(BaseModel):
    content: dict
    base_version: int | None = None


class PreviewIn(BaseModel):
    limit: int = Field(100, ge=1, le=10000)
    content: dict | None = None


class RollbackIn(BaseModel):
    version: int


def _asset(session, asset_id, claims):
    a = get_asset(session, asset_id)
    if not a or a.type != "model" or a.project_id != claims.get("project_id"):
        raise HTTPException(404, "model not found")
    return a


def _get(session, a):
    draft = session.get(AssetVersion, a.draft_version_id) \
        if a.draft_version_id else None
    published = session.get(AssetVersion, a.published_version_id) \
        if a.published_version_id else None
    return {"id": a.id, "key": a.key, "name": a.name,
            "draft_version": draft.version if draft else None,
            "published_version": published.version if published else None,
            "draft": draft.content_json if draft else None,
            "published": published.content_json if published else None,
            "enabled": bool(a.enabled)}


def _change(session, a, action, claims, token, payload=None):
    if not verify_token(a.id, action, token):
        raise HTTPException(403, "approval required")
    change = propose(session, a.project_id, claims["sub"], action, a.id,
                     payload or {})
    try:
        apply_change(session, change.id, token)
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except (ValueError, KeyError) as e:
        raise HTTPException(400, str(e))


@router.get("/models")
def list_models(page: int = 1, page_size: int = 50, q: str | None = None,
                s: Session = Depends(get_session),
                claims: dict = Depends(require_user)):
    from odf.services.pagination import envelope
    rows, total, page, page_size = page_assets(
        s, claims["project_id"], "model", page, page_size, q)
    items = []
    for a in rows:
        version_id = a.draft_version_id or a.published_version_id
        version = s.get(AssetVersion, version_id) if version_id else None
        content = version.content_json if version else {}
        items.append({"id": a.id, "key": a.key, "name": a.name,
                      "published": a.published_version_id is not None,
                      "enabled": bool(a.enabled),
                      "layer": content.get("layer") or "",
                      "materialization": content.get("materialization") or "",
                      "owner": a.owner})
    return envelope(items, total, page, page_size)


@router.post("/models")
def create(body: ModelIn, s: Session = Depends(get_session),
           claims: dict = Depends(require_editor)):
    if body.project_id != claims["project_id"]:
        raise HTTPException(403, "project mismatch")
    a = create_asset(s, body.project_id, "model", body.name,
                     body.content or empty_model(), claims["sub"],
                     enabled=True)
    write_audit(s, claims["sub"], "create_model", str(a.id),
                {"name": body.name})
    return {"id": a.id, "key": a.key}


@router.delete("/models/{asset_id}", status_code=204)
def delete(asset_id: int, s: Session = Depends(get_session),
           claims: dict = Depends(require_editor)):
    try:
        delete_asset_of(s, asset_id, claims["project_id"], "model")
    except ValueError as e:
        raise HTTPException(404, str(e))
    write_audit(s, claims["sub"], "delete_model", str(asset_id), {})
    return None


@router.get("/models/{asset_id}")
def get_model(asset_id: int, s: Session = Depends(get_session),
              claims: dict = Depends(require_user)):
    return _get(s, _asset(s, asset_id, claims))


@router.put("/models/{asset_id}")
def update(asset_id: int, body: UpdateIn, s: Session = Depends(get_session),
           claims: dict = Depends(require_editor)):
    a = update_asset(s, _asset(s, asset_id, claims).id, body.name, None)
    write_audit(s, claims["sub"], "update_model", str(a.id),
                {"name": a.name})
    return {"id": a.id, "name": a.name}


@router.put("/models/{asset_id}/draft")
def draft(asset_id: int, body: ContentIn,
          s: Session = Depends(get_session),
          claims: dict = Depends(require_editor)):
    a = _asset(s, asset_id, claims)
    try:
        v = update_draft(s, a.id, body.content, claims["sub"],
                         base_version=body.base_version)
    except DraftConflict as error:
        raise HTTPException(409, str(error))
    write_audit(s, claims["sub"], "update_model_draft", str(a.id),
                {"version": v.version})
    return {"version": v.version}


@router.post("/models/{asset_id}/validate")
def validate(asset_id: int, body: ContentIn,
             s: Session = Depends(get_session),
             claims: dict = Depends(require_user)):
    a = _asset(s, asset_id, claims)
    errs = validate_model(s, body.content, a.project_id, a.id)
    return {"valid": not errs, "errors": errs}


@router.post("/models/{asset_id}/preview")
def preview(asset_id: int, body: PreviewIn,
            s: Session = Depends(get_session),
            claims: dict = Depends(require_editor)):
    a = _asset(s, asset_id, claims)
    try:
        return preview_model(s, a.id, body.content, body.limit)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/models/{asset_id}/target")
def target(asset_id: int, s: Session = Depends(get_session),
           claims: dict = Depends(require_user)):
    a = _asset(s, asset_id, claims)
    try:
        content = (s.get(AssetVersion, a.draft_version_id).content_json
                   if a.draft_version_id else empty_model())
        return model_target(s, a, content)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/models/{asset_id}/run")
def run(asset_id: int, s: Session = Depends(get_session),
        claims: dict = Depends(require_editor)):
    a = _asset(s, asset_id, claims)
    if not a.published_version_id:
        raise HTTPException(400, "model is not published")
    job = enqueue_asset(s, a.id, "model")
    write_audit(s, claims["sub"], "run_model", str(a.id),
                {"job_id": job.id})
    return {"job_id": job.id}


@router.get("/models/{asset_id}/versions")
def versions(asset_id: int, s: Session = Depends(get_session),
             claims: dict = Depends(require_user)):
    a = _asset(s, asset_id, claims)
    return [{"version": v.version, "status": v.status,
             "current": v.id == a.published_version_id,
             "created_by": v.created_by,
             "created_at": v.created_at.isoformat()}
            for v in list_versions(s, a.id)]


@router.post("/models/{asset_id}/publish")
def publish(asset_id: int, approval_token: str,
            s: Session = Depends(get_session),
            claims: dict = Depends(require_approver)):
    a = _asset(s, asset_id, claims)
    v = s.get(AssetVersion, a.draft_version_id) if a.draft_version_id else None
    if not v:
        raise HTTPException(400, "draft not found")
    errs = validate_model(s, v.content_json, a.project_id, a.id)
    if errs:
        raise HTTPException(400, {"errors": errs})
    _change(s, a, "publish_model", claims, approval_token)
    s.refresh(a)
    a.enabled = True
    s.commit()
    sync_model_graph(s, a, s.get(AssetVersion,
                                 a.published_version_id).content_json)
    return {"version": s.get(AssetVersion, a.published_version_id).version}


@router.post("/models/{asset_id}/rollback")
def rollback(asset_id: int, body: RollbackIn, approval_token: str,
             s: Session = Depends(get_session),
             claims: dict = Depends(require_approver)):
    a = _asset(s, asset_id, claims)
    _change(s, a, "rollback_model", claims, approval_token,
            {"version": body.version})
    s.refresh(a)
    sync_model_graph(s, a, s.get(AssetVersion,
                                 a.published_version_id).content_json)
    return {"version": s.get(AssetVersion, a.published_version_id).version}
