from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.models import User
from odf.services.auth import require_admin
from odf.services.passwords import validate_password
from odf.services.users import (create_user, hash_password, list_users,
                                set_active, set_role)

router = APIRouter()


class UserIn(BaseModel):
    username: str
    password: str
    role: str = "viewer"


class ResetIn(BaseModel):
    password: str


def _out(u):
    return {"id": u.id, "username": u.username, "role": u.role,
            "active": u.active}


@router.get("/users")
def list_(s: Session = Depends(get_session),
          claims: dict = Depends(require_admin)):
    return [_out(u) for u in list_users(s)]


@router.post("/users")
def create(body: UserIn, s: Session = Depends(get_session),
           claims: dict = Depends(require_admin)):
    try:
        validate_password(body.password)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _out(create_user(s, body.username, body.password, body.role))


@router.post("/users/{user_id}/reset-password")
def reset(user_id: int, body: ResetIn,
          s: Session = Depends(get_session),
          claims: dict = Depends(require_admin)):
    try:
        validate_password(body.password)
    except ValueError as e:
        raise HTTPException(400, str(e))
    u = s.get(User, user_id)
    if not u:
        raise HTTPException(404, "user not found")
    u.password_hash = hash_password(body.password)
    u.password_changed_at = datetime.now(timezone.utc)
    u.token_version = int(u.token_version or 0) + 1
    s.commit()
    return {"ok": True}


@router.put("/users/{user_id}/role")
def role(user_id: int, role: str, s: Session = Depends(get_session),
         claims: dict = Depends(require_admin)):
    try:
        return _out(set_role(s, user_id, role))
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.put("/users/{user_id}/active")
def active(user_id: int, active: bool, s: Session = Depends(get_session),
           claims: dict = Depends(require_admin)):
    try:
        return _out(set_active(s, user_id, active))
    except ValueError as e:
        raise HTTPException(404, str(e))
