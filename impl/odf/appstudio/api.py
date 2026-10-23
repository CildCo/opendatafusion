from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from odf.appstudio.content import empty_app, validate_app
from odf.appstudio.forms import form_schema, submit_form
from odf.appstudio.service import app_data
from odf.assets.service import (create_asset, get_asset, list_assets,
                                list_versions, update_asset, update_draft)
from odf.db import get_session
from odf.models import AssetVersion, User
from odf.services.approval import verify_token
from odf.services.audit import write_audit
from odf.services.auth import (claims_role, require_approver,
                                require_editor, require_user)
from odf.services.changes import apply as apply_change
from odf.services.changes import propose

router = APIRouter()


class AppIn(BaseModel):
    name: str
    project_id: int = 1
    content: dict = Field(default_factory=dict)


class UpdateIn(BaseModel):
    name: str | None = None


class ContentIn(BaseModel):
    content: dict


class DataIn(BaseModel):
    page_id: str | None = None
    params: dict | None = None
    limit: int = Field(100, ge=1, le=10000)
    content: dict | None = None
    published: bool = False


class SubmitIn(BaseModel):
    component_id: str
    values: dict = Field(default_factory=dict)
    published: bool = False


class RollbackIn(BaseModel):
    version: int


def _asset(s, asset_id, claims):
    a = get_asset(s, asset_id)
    if not a or a.type != "app" or \
            a.project_id != claims.get("project_id"):
        raise HTTPException(404, "app not found")
    return a


def _get(s, a):
    draft = s.get(AssetVersion, a.draft_version_id) if a.draft_version_id else None
    pub = s.get(AssetVersion, a.published_version_id) if a.published_version_id else None
    return {"id": a.id, "key": a.key, "name": a.name,
            "draft_version": draft.version if draft else None,
            "published_version": pub.version if pub else None,
            "draft": draft.content_json if draft else None,
            "published": pub.content_json if pub else None}


@router.get("/apps")
def list_(s: Session = Depends(get_session),
          claims: dict = Depends(require_user)):
    return [{"id": a.id, "key": a.key, "name": a.name,
             "published": a.published_version_id is not None}
            for a in list_assets(s, claims["project_id"], "app")]


@router.post("/apps")
def create(body: AppIn, s: Session = Depends(get_session),
           claims: dict = Depends(require_editor)):
    if body.project_id != claims["project_id"]:
        raise HTTPException(403, "project mismatch")
    a = create_asset(s, body.project_id, "app", body.name,
                     body.content or empty_app(), claims["sub"],
                     enabled=False)
    write_audit(s, claims["sub"], "create_app", str(a.id),
                {"name": body.name})
    return {"id": a.id, "key": a.key}


@router.get("/apps/{asset_id}")
def get_(asset_id: int, s: Session = Depends(get_session),
         claims: dict = Depends(require_user)):
    return _get(s, _asset(s, asset_id, claims))


@router.put("/apps/{asset_id}")
def update(asset_id: int, body: UpdateIn, s: Session = Depends(get_session),
           claims: dict = Depends(require_editor)):
    a = _asset(s, asset_id, claims)
    a = update_asset(s, a.id, body.name, None)
    write_audit(s, claims["sub"], "update_app", str(a.id),
                {"name": a.name})
    return {"id": a.id, "name": a.name}


@router.put("/apps/{asset_id}/draft")
def draft(asset_id: int, body: ContentIn,
          s: Session = Depends(get_session),
          claims: dict = Depends(require_editor)):
    a = _asset(s, asset_id, claims)
    v = update_draft(s, a.id, body.content, claims["sub"])
    write_audit(s, claims["sub"], "update_app_draft", str(a.id),
                {"version": v.version})
    return {"version": v.version}


@router.post("/apps/{asset_id}/validate")
def validate(asset_id: int, body: ContentIn,
             s: Session = Depends(get_session),
             claims: dict = Depends(require_user)):
    a = _asset(s, asset_id, claims)
    errs = validate_app(s, body.content, a.project_id)
    return {"valid": not errs, "errors": errs}


@router.post("/apps/{asset_id}/data")
def data(asset_id: int, body: DataIn, s: Session = Depends(get_session),
         claims: dict = Depends(require_user)):
    a = _asset(s, asset_id, claims)
    try:
        result = app_data(s, a.id, page_id=body.page_id, params=body.params,
                          content=body.content, limit=body.limit,
                          published_only=body.published,
                          role=claims_role(s, claims))
    except ValueError as e:
        raise HTTPException(400, str(e))
    write_audit(s, claims["sub"], "query_app", str(a.id),
                {"page_id": result["page_id"]})
    return result


@router.get("/apps/{asset_id}/form-schema")
def form_schema_(asset_id: int, dataset_id: int,
                 s: Session = Depends(get_session),
                 claims: dict = Depends(require_user)):
    a = _asset(s, asset_id, claims)
    try:
        return form_schema(s, a.project_id, dataset_id)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/apps/{asset_id}/submit")
def submit_(asset_id: int, body: SubmitIn,
            s: Session = Depends(get_session),
            claims: dict = Depends(require_user)):
    a = _asset(s, asset_id, claims)
    user = s.get(User, int(claims["sub"]))
    if not user or not user.active:
        raise HTTPException(403, "user is inactive")
    role = user.role
    published = body.published or role == "viewer"
    try:
        return submit_form(s, a.id, body.component_id, body.values,
                           published, claims["sub"], role)
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/apps/{asset_id}/versions")
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


@router.post("/apps/{asset_id}/publish")
def publish(asset_id: int, approval_token: str,
            s: Session = Depends(get_session),
            claims: dict = Depends(require_approver)):
    a = _asset(s, asset_id, claims)
    v = s.get(AssetVersion, a.draft_version_id) if a.draft_version_id else None
    if not v:
        raise HTTPException(400, "draft not found")
    errs = validate_app(s, v.content_json, a.project_id)
    if errs:
        raise HTTPException(400, {"errors": errs})
    _change(s, a, "publish_app", claims, approval_token)
    s.refresh(a)
    return {"version": s.get(AssetVersion, a.published_version_id).version}


@router.post("/apps/{asset_id}/rollback")
def rollback(asset_id: int, body: RollbackIn, approval_token: str,
             s: Session = Depends(get_session),
             claims: dict = Depends(require_approver)):
    a = _asset(s, asset_id, claims)
    _change(s, a, "rollback_app", claims, approval_token,
            {"version": body.version})
    s.refresh(a)
    return {"version": s.get(AssetVersion, a.published_version_id).version}
