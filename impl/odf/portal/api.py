from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.portal.service import get_portal, update_portal
from odf.services.auth import require_project_admin, require_user
from odf.services.platform import public_doc

router = APIRouter()


@router.get("/portal")
def get_(s: Session = Depends(get_session),
         claims: dict = Depends(require_user)):
    data = get_portal(s, claims["project_id"])
    platform = public_doc(s)
    brand = platform["brand"]
    data["brand_name"] = brand.get("name") or data["brand_name"]
    data["primary_color"] = brand.get("color") or data["primary_color"]
    data["default_locale"] = platform["default_locale"]
    data["announcement"] = platform["announcement"]
    data["features"] = platform["features"]
    return data


@router.put("/portal")
def put(body: dict, s: Session = Depends(get_session),
        claims: dict = Depends(require_project_admin)):
    try:
        return update_portal(s, claims["project_id"], body, claims["sub"])
    except ValueError as e:
        raise HTTPException(400, str(e))
