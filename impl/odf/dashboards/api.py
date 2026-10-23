from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from odf.assets.service import (create_asset, get_asset, list_assets,
                                list_versions, update_asset, update_draft)
from odf.dashboards.content import empty_dashboard, validate_dashboard
from odf.dashboards.service import dashboard_data
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


class DataIn(BaseModel):
    limit: int = Field(100, ge=1, le=10000)
    params: dict | None = None
    content: dict | None = None
    published: bool = False


class RollbackIn(BaseModel):
    version: int


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
def list_(s: Session = Depends(get_session),
          claims: dict = Depends(require_user)):
    return [{"id": a.id, "key": a.key, "name": a.name,
             "published": a.published_version_id is not None}
            for a in list_assets(s, claims["project_id"], "dashboard")]


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
    v = update_draft(s, a.id, body.content, claims["sub"])
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
