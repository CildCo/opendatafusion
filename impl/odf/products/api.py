import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from odf.assets.service import (DraftConflict, create_asset,
                                delete_asset_of, get_asset,
                                list_versions, page_assets, publish_asset,
                                rollback_asset, update_asset, update_draft)
from odf.db import get_session
from odf.models import AssetVersion
from odf.products.content import (empty_product, product_bundle,
                                  validate_product)
from odf.services.audit import write_audit
from odf.services.auth import require_editor, require_user

router = APIRouter()


class ProductIn(BaseModel):
    project_id: int = 1
    name: str = Field(min_length=1, max_length=128)
    content: dict | None = None


class UpdateIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)


class ContentIn(BaseModel):
    content: dict
    base_version: int | None = None


def _asset(s, asset_id, claims):
    a = get_asset(s, asset_id)
    if not a or a.type != "data_product" \
            or a.project_id != claims.get("project_id"):
        raise HTTPException(404, "data product not found")
    return a


def _get(s, a):
    draft = s.get(AssetVersion, a.draft_version_id) if a.draft_version_id else None
    pub = (s.get(AssetVersion, a.published_version_id)
           if a.published_version_id else None)
    return {"id": a.id, "key": a.key, "name": a.name,
            "draft_version": draft.version if draft else None,
            "published_version": pub.version if pub else None,
            "draft": draft.content_json if draft else None,
            "published": pub.content_json if pub else None}


@router.get("/data-products")
def list_(page: int = 1, page_size: int = 50, q: str | None = None,
          s: Session = Depends(get_session),
          claims: dict = Depends(require_user)):
    from odf.services.pagination import envelope
    rows, total, page, page_size = page_assets(
        s, claims["project_id"], "data_product", page, page_size, q)
    return envelope([{"id": a.id, "key": a.key, "name": a.name,
                      "published": a.published_version_id is not None}
                     for a in rows], total, page, page_size)


@router.post("/data-products")
def create(body: ProductIn, s: Session = Depends(get_session),
           claims: dict = Depends(require_editor)):
    if body.project_id != claims["project_id"]:
        raise HTTPException(403, "project mismatch")
    content = body.content or empty_product()
    a = create_asset(s, body.project_id, "data_product", body.name, content,
                     claims["sub"], enabled=False)
    write_audit(s, claims["sub"], "create_data_product", str(a.id),
                {"name": body.name})
    return {"id": a.id, "key": a.key}


@router.get("/data-products/{asset_id}")
def get_(asset_id: int, s: Session = Depends(get_session),
         claims: dict = Depends(require_user)):
    return _get(s, _asset(s, asset_id, claims))


@router.put("/data-products/{asset_id}")
def update(asset_id: int, body: UpdateIn, s: Session = Depends(get_session),
           claims: dict = Depends(require_editor)):
    a = _asset(s, asset_id, claims)
    a = update_asset(s, a.id, body.name, None)
    write_audit(s, claims["sub"], "update_data_product", str(a.id), {})
    return {"id": a.id, "name": a.name}


@router.put("/data-products/{asset_id}/draft")
def draft(asset_id: int, body: ContentIn,
          s: Session = Depends(get_session),
          claims: dict = Depends(require_editor)):
    a = _asset(s, asset_id, claims)
    try:
        v = update_draft(s, a.id, body.content, claims["sub"],
                         base_version=body.base_version)
    except DraftConflict as error:
        raise HTTPException(409, str(error))
    write_audit(s, claims["sub"], "update_data_product_draft", str(a.id),
                {"version": v.version})
    return {"version": v.version}


@router.post("/data-products/{asset_id}/validate")
def validate(asset_id: int, body: ContentIn,
             s: Session = Depends(get_session),
             claims: dict = Depends(require_user)):
    a = _asset(s, asset_id, claims)
    errs = validate_product(s, body.content, a.project_id)
    return {"valid": not errs, "errors": errs}


@router.post("/data-products/{asset_id}/publish")
def publish(asset_id: int, s: Session = Depends(get_session),
            claims: dict = Depends(require_editor)):
    a = _asset(s, asset_id, claims)
    try:
        v = publish_asset(s, a.id, claims["sub"])
    except ValueError as error:
        raise HTTPException(400, str(error))
    write_audit(s, claims["sub"], "publish_data_product", str(a.id),
                {"version": v.version})
    return {"version": v.version}


@router.get("/data-products/{asset_id}/versions")
def versions(asset_id: int, s: Session = Depends(get_session),
             claims: dict = Depends(require_user)):
    a = _asset(s, asset_id, claims)
    return [{"version": v.version, "status": v.status,
             "created_by": v.created_by, "created_at": v.created_at,
             "current": v.id in (a.draft_version_id,
                                 a.published_version_id)}
            for v in list_versions(s, a.id)]


@router.post("/data-products/{asset_id}/rollback/{version}")
def rollback(asset_id: int, version: int,
             s: Session = Depends(get_session),
             claims: dict = Depends(require_editor)):
    a = _asset(s, asset_id, claims)
    try:
        v = rollback_asset(s, a.id, version, claims["sub"])
    except ValueError as error:
        raise HTTPException(400, str(error))
    return {"version": v.version}


@router.get("/data-products/{asset_id}/bundle")
def bundle(asset_id: int, s: Session = Depends(get_session),
           claims: dict = Depends(require_user)):
    a = _asset(s, asset_id, claims)
    v = s.get(AssetVersion, a.published_version_id or a.draft_version_id) \
        if (a.published_version_id or a.draft_version_id) else None
    if not v:
        raise HTTPException(404, "product content not found")
    payload = product_bundle(s, a.project_id, v.content_json or {})
    body = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    return Response(
        content=body, media_type="application/json",
        headers={"Content-Disposition":
                 'attachment; filename="odf-product-%d.json"' % a.id})


@router.delete("/data-products/{asset_id}", status_code=204)
def delete(asset_id: int, s: Session = Depends(get_session),
           claims: dict = Depends(require_editor)):
    try:
        delete_asset_of(s, asset_id, claims["project_id"], "data_product")
    except ValueError as error:
        raise HTTPException(404, str(error))
    write_audit(s, claims["sub"], "delete_data_product", str(asset_id), {})
    return None
