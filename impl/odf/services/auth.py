from datetime import datetime, timedelta, timezone

from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.services.messages import tr
from odf.settings import get_settings

_bearer = HTTPBearer(auto_error=False)


def create_token(user_id: int, project_id: int,
                 token_version: int | None = None,
                 ttl_hours: int | None = None) -> str:
    if token_version is None:
        from odf.db import SessionLocal
        from odf.models import User
        with SessionLocal() as s:
            user = s.get(User, user_id)
            token_version = user.token_version if user else 0
    now = datetime.now(timezone.utc)
    ttl = ttl_hours or get_settings().token_ttl_hours
    return jwt.encode({"sub": str(user_id), "project_id": project_id,
                       "ver": int(token_version or 0),
                       "iat": now, "exp": now + timedelta(hours=ttl)},
                      get_settings().jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict:
    return jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])


def require_user(
        cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
        s: Session = Depends(get_session),
        accept_language: str | None = Header(default=None)) -> dict:
    if cred is None:
        raise HTTPException(401, tr(accept_language, "auth.missing_token"))
    try:
        claims = decode_token(cred.credentials)
    except Exception:
        raise HTTPException(401, tr(accept_language, "auth.invalid_token"))
    from odf.models import User
    user = s.get(User, int(claims["sub"]))
    if not user or not user.active:
        raise HTTPException(401, tr(accept_language, "auth.inactive_user"))
    if int(claims.get("ver", 0)) != int(user.token_version or 0):
        raise HTTPException(401, tr(accept_language, "auth.revoked"))
    return claims


def current_project(claims: dict = Depends(require_user)) -> int:
    return claims["project_id"]


def effective_role(session, user, project_id):
    if user.role == "admin":
        return "admin"
    from odf.models import ProjectMember
    member = (session.query(ProjectMember)
              .filter_by(project_id=project_id, user_id=user.id).first())
    return member.role if member else user.role


def claims_role(session, claims):
    from odf.models import User
    user = session.get(User, int(claims["sub"]))
    if not user or not user.active:
        return None
    return effective_role(session, user, claims["project_id"])


def require_editor(claims: dict = Depends(require_user),
                   s: Session = Depends(get_session),
                   accept_language: str | None = Header(default=None)) -> dict:
    from odf.models import User
    user = s.get(User, int(claims["sub"]))
    if not user or not user.active or effective_role(
            s, user, claims["project_id"]) not in ("editor", "approver",
                                                   "admin"):
        raise HTTPException(403, tr(accept_language, "auth.editor"))
    return claims


def require_approver(claims: dict = Depends(require_user),
                     s: Session = Depends(get_session),
                     accept_language: str | None = Header(default=None)) -> dict:
    from odf.models import User
    user = s.get(User, int(claims["sub"]))
    if not user or not user.active or effective_role(
            s, user, claims["project_id"]) not in ("approver", "admin"):
        raise HTTPException(403, tr(accept_language, "auth.approver"))
    return claims


def require_platform_admin(
        claims: dict = Depends(require_user),
        s: Session = Depends(get_session),
        accept_language: str | None = Header(default=None)) -> dict:
    from odf.models import User
    from odf.services.platform import is_platform_admin
    user = s.get(User, int(claims["sub"]))
    if not user or not user.active or not is_platform_admin(user):
        raise HTTPException(403, tr(accept_language, "auth.admin"))
    return claims


def require_project_admin(
        claims: dict = Depends(require_user),
        s: Session = Depends(get_session),
        accept_language: str | None = Header(default=None)) -> dict:
    from odf.models import ProjectMember, User
    from odf.services.platform import is_platform_admin
    user = s.get(User, int(claims["sub"]))
    if not user or not user.active:
        raise HTTPException(403, tr(accept_language, "auth.admin"))
    if is_platform_admin(user):
        return claims
    member = (s.query(ProjectMember)
              .filter_by(project_id=claims["project_id"],
                         user_id=user.id).first())
    if not member or member.role != "admin":
        raise HTTPException(403, tr(accept_language, "auth.admin"))
    return claims


require_admin = require_platform_admin
