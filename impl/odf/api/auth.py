from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.models import ProjectMember, User
from odf.services.audit import write_audit
from odf.services.users import create_user
from odf.models import Project, ProjectMember
from odf.services import ldap_auth, oidc
from odf.services.auth import create_token, require_user
from odf.services.crypto import decrypt_secret, encrypt_secret
from odf.services.passwords import validate_password
from odf.services.totp import (generate_secret, matching_step,
                               provisioning_uri, verify_code)
from odf.services.ratelimit import check_rate
from odf.services.users import (authenticate, hash_password, verify_password)
from odf.settings import get_settings

router = APIRouter()


class LoginIn(BaseModel):
    username: str
    password: str
    project_id: int = 1
    otp: str | None = None


class PasswordIn(BaseModel):
    old_password: str
    new_password: str


class TotpIn(BaseModel):
    code: str


def _login_guard(s, username, request):
    host = request.client.host if request.client else ""
    try:
        import ipaddress
        ipaddress.ip_address(host)
    except ValueError:
        host = "127.0.0.1"
    if not check_rate(s, "login:%s:%s" % (username, host),
                      get_settings().login_rate_per_min):
        raise HTTPException(429, "too many login attempts")


@router.post("/auth/login")
def login(body: LoginIn, request: Request,
          s: Session = Depends(get_session)):
    u = authenticate(s, body.username, body.password)
    if not u and get_settings().ldap_url:
        try:
            name = ldap_auth.authenticate_ldap(body.username, body.password)
        except Exception:
            name = None
        if name:
            u = s.query(User).filter_by(username=name).first()
            if u and not u.active:
                raise HTTPException(401, "user is inactive")
            if not u and get_settings().ldap_auto_provision:
                u = create_user(s, name, __import__("secrets").token_urlsafe(24),
                                role="viewer")
    if not u or not u.active:
        _login_guard(s, body.username, request)
        raise HTTPException(401, "bad credentials")
    project = s.get(Project, body.project_id)
    if not project:
        raise HTTPException(400, "project not found")
    if u.role != "admin":
        member = (s.query(ProjectMember)
                  .filter_by(project_id=body.project_id, user_id=u.id)
                  .first())
        if not member:
            raise HTTPException(403, "not a project member")
    if u.totp_enabled:
        secret = decrypt_secret(u.totp_secret_encrypted or "")
        step = matching_step(secret, body.otp or "")
        if step is None or (u.totp_last_step is not None and
                            step <= u.totp_last_step):
            _login_guard(s, body.username, request)
            raise HTTPException(401, "invalid or missing one-time code")
        u.totp_last_step = step
        s.commit()
    write_audit(s, u.username, "login", str(u.id), {})
    return {"token": create_token(u.id, body.project_id, u.token_version)}


class SwitchIn(BaseModel):
    project_id: int


@router.post("/auth/switch-project")
def switch_project(body: SwitchIn, s: Session = Depends(get_session),
                   claims: dict = Depends(require_user)):
    u = s.get(User, int(claims["sub"]))
    if not u or not u.active:
        raise HTTPException(403, "user is inactive")
    project = s.get(Project, body.project_id)
    if not project:
        raise HTTPException(404, "project not found")
    if u.role != "admin":
        member = (s.query(ProjectMember)
                  .filter_by(project_id=project.id, user_id=u.id).first())
        if not member:
            raise HTTPException(403, "not a project member")
    write_audit(s, u.username, "switch_project", str(project.id), {})
    return {"token": create_token(u.id, project.id, u.token_version),
            "project_id": project.id}


@router.post("/auth/refresh")
def refresh(claims: dict = Depends(require_user),
            s: Session = Depends(get_session)):
    u = s.get(User, int(claims["sub"]))
    return {"token": create_token(u.id, int(claims["project_id"]),
                                  u.token_version)}


@router.post("/auth/change-password")
def change_password(body: PasswordIn,
                    s: Session = Depends(get_session),
                    claims: dict = Depends(require_user)):
    u = s.get(User, int(claims["sub"]))
    if not u or not u.active or not verify_password(body.old_password,
                                                    u.password_hash):
        raise HTTPException(400, "invalid current password")
    try:
        validate_password(body.new_password)
    except ValueError as e:
        raise HTTPException(400, str(e))
    u.password_hash = hash_password(body.new_password)
    u.password_changed_at = datetime.now(timezone.utc)
    u.token_version = int(u.token_version or 0) + 1
    s.commit()
    write_audit(s, u.username, "change_password", str(u.id), {})
    return {"ok": True,
            "token": create_token(u.id, int(claims["project_id"]),
                                  u.token_version)}


@router.post("/auth/totp/setup")
def totp_setup(body: TotpIn | None = None,
               s: Session = Depends(get_session),
               claims: dict = Depends(require_user)):
    u = s.get(User, int(claims["sub"]))
    if not u or not u.active:
        raise HTTPException(403, "user is inactive")
    if u.totp_enabled:
        if not body or not verify_code(
                decrypt_secret(u.totp_secret_encrypted or ""), body.code):
            raise HTTPException(400, "current one-time code required")
    secret = generate_secret()
    u.totp_secret_encrypted = encrypt_secret(secret)
    u.totp_enabled = False
    s.commit()
    return {"secret": secret,
            "uri": provisioning_uri(secret, u.username,
                                    get_settings().totp_issuer)}


@router.post("/auth/totp/enable")
def totp_enable(body: TotpIn, s: Session = Depends(get_session),
                claims: dict = Depends(require_user)):
    u = s.get(User, int(claims["sub"]))
    if not u or not u.active or not u.totp_secret_encrypted:
        raise HTTPException(400, "totp is not set up")
    step = matching_step(decrypt_secret(u.totp_secret_encrypted), body.code)
    if step is None:
        raise HTTPException(400, "invalid one-time code")
    u.totp_enabled = True
    u.totp_last_step = step
    s.commit()
    write_audit(s, u.username, "enable_totp", str(u.id), {})
    return {"enabled": True}


@router.post("/auth/totp/disable")
def totp_disable(body: TotpIn, s: Session = Depends(get_session),
                 claims: dict = Depends(require_user)):
    u = s.get(User, int(claims["sub"]))
    if not u or not u.active or not u.totp_enabled:
        raise HTTPException(400, "totp is not enabled")
    if not verify_code(decrypt_secret(u.totp_secret_encrypted or ""),
                       body.code):
        raise HTTPException(400, "invalid one-time code")
    u.totp_enabled = False
    u.totp_secret_encrypted = None
    u.totp_last_step = None
    s.commit()
    write_audit(s, u.username, "disable_totp", str(u.id), {})
    return {"enabled": False}


@router.get("/auth/oidc/enabled")
def oidc_enabled():
    return {"enabled": oidc.configured(),
            "issuer": get_settings().oidc_issuer if oidc.configured() else ""}


@router.get("/auth/oidc/start")
def oidc_start(project_id: int = 1):
    if not oidc.configured():
        raise HTTPException(404, "OIDC is not configured")
    from fastapi.responses import RedirectResponse
    url, state, nonce = oidc.start_flow(project_id)
    resp = RedirectResponse(url, status_code=302)
    resp.set_cookie("odf_oidc_state", nonce, httponly=True,
                    samesite="lax", max_age=600, path="/")
    return resp


@router.get("/auth/oidc/callback")
def oidc_callback(code: str, state: str, request: Request,
                  s: Session = Depends(get_session)):
    from fastapi.responses import RedirectResponse
    try:
        claims = oidc._decode_state(state)
        if request.cookies.get("odf_oidc_state") != claims.get("nonce"):
            raise ValueError("state mismatch")
        project_id, info = oidc.exchange(code, state)
        u = oidc.map_user(s, info, project_id)
    except Exception:
        raise HTTPException(401, "OIDC login failed")
    token = create_token(u.id, project_id, u.token_version)
    write_audit(s, u.username, "login_oidc", str(u.id), {})
    base = str(request.base_url).rstrip("/")
    resp = RedirectResponse("%s/ui/#/oidc?token=%s" % (base, token),
                            status_code=302)
    resp.delete_cookie("odf_oidc_state", path="/")
    return resp


@router.get("/auth/me")
def me(claims: dict = Depends(require_user),
       s: Session = Depends(get_session)):
    u = s.get(User, int(claims["sub"]))
    return {"id": u.id if u else None,
            "username": u.username if u else None,
            "role": u.role if u else None,
            "totp_enabled": bool(u.totp_enabled) if u else False,
            "project_id": claims.get("project_id")}
