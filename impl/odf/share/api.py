from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from odf.assets.service import get_asset
from odf.db import get_session
from odf.services.auth import require_editor, require_user
from odf.share import service

router = APIRouter()
public_router = APIRouter()


class ShareIn(BaseModel):
    expires_days: int = 7


class PublicDataIn(BaseModel):
    page_id: str | None = None
    params: dict | None = None
    limit: int = Field(100, ge=1, le=10000)


def _asset(s, asset_id, claims, type_):
    a = get_asset(s, asset_id)
    if not a or a.type != type_ or a.project_id != claims.get("project_id"):
        raise HTTPException(404, "%s not found" % type_)
    return a


def _create(s, a, type_, body, claims):
    try:
        out = service.create_share(s, a.project_id, a.id, type_,
                                   body.expires_days, claims["sub"])
    except ValueError as e:
        raise HTTPException(404 if "share not found" in str(e) else 400,
                            str(e))
    out["url_path"] = "#/share/" + out["token"]
    return out


def _list(s, a, type_):
    return service.list_shares(s, a.project_id, a.id, type_)


def _revoke(s, a, type_, share_id, claims):
    try:
        return service.revoke_share(s, a.project_id, a.id, type_, share_id,
                                    claims["sub"])
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/apps/{asset_id}/share")
def create_app(asset_id: int, body: ShareIn,
               s: Session = Depends(get_session),
               claims: dict = Depends(require_editor)):
    return _create(s, _asset(s, asset_id, claims, "app"), "app", body, claims)


@router.get("/apps/{asset_id}/shares")
def list_app(asset_id: int, s: Session = Depends(get_session),
             claims: dict = Depends(require_user)):
    return _list(s, _asset(s, asset_id, claims, "app"), "app")


@router.post("/apps/{asset_id}/shares/{share_id}/revoke")
def revoke_app(asset_id: int, share_id: int,
               s: Session = Depends(get_session),
               claims: dict = Depends(require_editor)):
    return _revoke(s, _asset(s, asset_id, claims, "app"), "app", share_id,
                   claims)


@router.post("/dashboards/{asset_id}/share")
def create_dashboard(asset_id: int, body: ShareIn,
                     s: Session = Depends(get_session),
                     claims: dict = Depends(require_editor)):
    return _create(s, _asset(s, asset_id, claims, "dashboard"), "dashboard",
                   body, claims)


@router.get("/dashboards/{asset_id}/shares")
def list_dashboard(asset_id: int, s: Session = Depends(get_session),
                   claims: dict = Depends(require_user)):
    return _list(s, _asset(s, asset_id, claims, "dashboard"), "dashboard")


@router.post("/dashboards/{asset_id}/shares/{share_id}/revoke")
def revoke_dashboard(asset_id: int, share_id: int,
                     s: Session = Depends(get_session),
                     claims: dict = Depends(require_editor)):
    return _revoke(s, _asset(s, asset_id, claims, "dashboard"), "dashboard",
                   share_id, claims)


def _token(value):
    if not value:
        raise HTTPException(404, "share not found")
    return value


@public_router.get("/public/share")
def public_view(
        x_share_token: str | None = Header(None, alias="X-Share-Token"),
        s: Session = Depends(get_session)):
    try:
        return service.public_view(s, _token(x_share_token))
    except ValueError as e:
        raise HTTPException(404, str(e))


@public_router.post("/public/share/data")
def public_data(body: PublicDataIn,
                x_share_token: str | None = Header(None,
                                                   alias="X-Share-Token"),
                s: Session = Depends(get_session)):
    try:
        return service.public_data(s, _token(x_share_token),
                                   page_id=body.page_id,
                                   params=body.params, limit=body.limit)
    except ValueError as e:
        raise HTTPException(404 if "share not found" in str(e) else 400,
                            str(e))
