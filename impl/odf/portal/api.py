from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.portal.service import get_portal, update_portal
from odf.services.auth import require_editor, require_user
from odf.models import User

router = APIRouter()


@router.get("/portal")
def get_(s: Session = Depends(get_session),
         claims: dict = Depends(require_user)):
    return get_portal(s, claims["project_id"])


@router.put("/portal")
def put(body: dict, s: Session = Depends(get_session),
        claims: dict = Depends(require_editor)):
    user = s.get(User, int(claims["sub"]))
    if "allowed_menus" in body and (not user or user.role != "admin"):
        raise HTTPException(403, "admin role required for menu permissions")
    try:
        return update_portal(s, claims["project_id"], body, claims["sub"])
    except ValueError as e:
        raise HTTPException(400, str(e))
