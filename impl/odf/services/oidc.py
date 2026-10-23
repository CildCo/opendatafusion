import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from jose import jwt

from odf.models import ProjectMember, User
from odf.services.crypto import decrypt_secret, encrypt_secret
from odf.services.users import create_user
from odf.settings import get_settings


def configured():
    s = get_settings()
    return bool(s.oidc_issuer and s.oidc_client_id and s.oidc_redirect_uri)


def _discovery():
    issuer = get_settings().oidc_issuer.rstrip("/")
    r = httpx.get(issuer + "/.well-known/openid-configuration", timeout=5)
    r.raise_for_status()
    return r.json()


def _state(project_id, verifier=None):
    s = get_settings()
    now = datetime.now(timezone.utc)
    return jwt.encode({"project_id": project_id,
                       "venc": encrypt_secret(
                           verifier or secrets.token_urlsafe(48)),
                       "nonce": secrets.token_urlsafe(16),
                       "iat": now,
                       "exp": now + timedelta(minutes=10)},
                      s.jwt_secret, algorithm="HS256")


def _decode_state(state):
    s = get_settings()
    return jwt.decode(state, s.jwt_secret, algorithms=["HS256"])


def start_flow(project_id):
    s = get_settings()
    meta = _discovery()
    verifier = secrets.token_urlsafe(48)
    raw_state = _state(project_id, verifier)
    claims = _decode_state(raw_state)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    query = urlencode({
        "response_type": "code", "client_id": s.oidc_client_id,
        "redirect_uri": s.oidc_redirect_uri, "scope": s.oidc_scopes,
        "state": raw_state, "code_challenge": challenge,
        "code_challenge_method": "S256"})
    return (meta["authorization_endpoint"] + "?" + query, raw_state,
            claims["nonce"])


def start(project_id):
    return start_flow(project_id)[0]


def exchange(code, state):
    s = get_settings()
    claims = _decode_state(state)
    meta = _discovery()
    token = httpx.post(meta["token_endpoint"], data={
        "grant_type": "authorization_code", "code": code,
        "redirect_uri": s.oidc_redirect_uri,
        "client_id": s.oidc_client_id,
        "client_secret": s.oidc_client_secret,
        "code_verifier": decrypt_secret(claims["venc"])}, timeout=10)
    token.raise_for_status()
    access = token.json().get("access_token")
    if not access:
        raise ValueError("OIDC token response missing access_token")
    info = httpx.get(meta["userinfo_endpoint"],
                     headers={"Authorization": "Bearer " + access},
                     timeout=10)
    info.raise_for_status()
    return int(claims["project_id"]), info.json()


def map_user(session, info, project_id):
    s = get_settings()
    subject = str(info.get("sub") or "").strip()
    if not subject:
        raise ValueError("OIDC user has no subject")
    user = session.query(User).filter_by(oidc_sub=subject).first()
    if not user:
        if not s.oidc_auto_provision:
            raise PermissionError("OIDC user is not provisioned")
        base = str(info.get("preferred_username") or info.get("email") or
                   subject).strip()[:48]
        base = "".join(c if c.isalnum() or c in "._-" else "_"
                       for c in base) or "oidc"
        username = base
        if session.query(User).filter_by(username=username).first():
            username = "%s_oidc_%s" % (base[:40],
                                       hashlib.sha256(
                                           subject.encode()).hexdigest()[:6])
        user = create_user(session, username, secrets.token_urlsafe(24),
                           role="viewer")
        user.oidc_sub = subject
        session.commit()
    if user.role != "admin":
        member = (session.query(ProjectMember)
                  .filter_by(project_id=project_id, user_id=user.id).first())
        if not member:
            raise PermissionError("not a project member")
    if not user.active:
        raise PermissionError("user is inactive")
    return user
