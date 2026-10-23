from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.settings import get_settings

_bearer = HTTPBearer(auto_error=False)


def create_token(user_id: int, project_id: int,
                 token_version: int | None = None) -> str:
    if token_version is None:
        from odf.db import SessionLocal
        from odf.models import User
        with SessionLocal() as s:
            user = s.get(User, user_id)
            token_version = user.token_version if user else 0
    now = datetime.now(timezone.utc)
    ttl = get_settings().token_ttl_hours
    return jwt.encode({"sub": str(user_id), "project_id": project_id,
                       "ver": int(token_version or 0),
                       "iat": now, "exp": now + timedelta(hours=ttl)},
                      get_settings().jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict:
    return jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])


def require_user(
        cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
        s: Session = Depends(get_session)) -> dict:
    if cred is None:
        raise HTTPException(401, "missing bearer token")
    try:
        claims = decode_token(cred.credentials)
    except Exception:
        raise HTTPException(401, "invalid or expired token")
    from odf.models import User
    user = s.get(User, int(claims["sub"]))
    if not user or not user.active:
        raise HTTPException(401, "invalid or inactive user")
    if int(claims.get("ver", 0)) != int(user.token_version or 0):
        raise HTTPException(401, "session has been revoked")
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
                   s: Session = Depends(get_session)) -> dict:
    from odf.models import User
    user = s.get(User, int(claims["sub"]))
    if not user or not user.active or effective_role(
            s, user, claims["project_id"]) not in ("editor", "approver",
                                                   "admin"):
        raise HTTPException(403, "editor role required")
    return claims


def require_approver(claims: dict = Depends(require_user),
                     s: Session = Depends(get_session)) -> dict:
    from odf.models import User
    user = s.get(User, int(claims["sub"]))
    if not user or not user.active or effective_role(
            s, user, claims["project_id"]) not in ("approver", "admin"):
        raise HTTPException(403, "approver role required")
    return claims


def require_admin(claims: dict = Depends(require_user),
                  s: Session = Depends(get_session)) -> dict:
    from odf.models import User
    user = s.get(User, int(claims["sub"]))
    if not user or not user.active or user.role != "admin":
        raise HTTPException(403, "admin role required")
    return claims
