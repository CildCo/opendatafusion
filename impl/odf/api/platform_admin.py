from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.services.auth import require_platform_admin
from odf.services.platform import (get_doc, overview, public_doc, update_doc)

router = APIRouter()


@router.get("/platform/public")
def public(s: Session = Depends(get_session)):
    return public_doc(s)


@router.get("/platform/settings")
def settings(s: Session = Depends(get_session),
             claims: dict = Depends(require_platform_admin)):
    return get_doc(s)


@router.put("/platform/settings")
def save(body: dict, s: Session = Depends(get_session),
         claims: dict = Depends(require_platform_admin)):
    try:
        return update_doc(s, body, claims.get("sub", ""))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/platform/overview")
def platform_overview(s: Session = Depends(get_session),
                      claims: dict = Depends(require_platform_admin)):
    return overview(s)


class TestOidcIn(BaseModel):
    issuer: str


@router.post("/platform/identity/test-oidc")
def test_oidc(body: TestOidcIn,
              claims: dict = Depends(require_platform_admin)):
    import json
    from odf.services.net import request as outbound
    issuer = (body.issuer or "").rstrip("/")
    if not issuer:
        raise HTTPException(400, "issuer is required")
    try:
        _, _, payload = outbound(
            issuer + "/.well-known/openid-configuration", timeout=8)
        data = json.loads(payload.decode("utf-8", "replace"))
    except Exception as error:
        raise HTTPException(400, "discovery failed: %s" % error)
    return {"ok": True,
            "authorization_endpoint": data.get("authorization_endpoint"),
            "token_endpoint": data.get("token_endpoint"),
            "userinfo_endpoint": data.get("userinfo_endpoint")}


class TestLdapIn(BaseModel):
    url: str
    bind_dn: str = ""
    bind_password: str = ""


@router.post("/platform/identity/test-ldap")
def test_ldap(body: TestLdapIn,
              claims: dict = Depends(require_platform_admin)):
    if not body.url:
        raise HTTPException(400, "url is required")
    try:
        from ldap3 import Connection, Server
        server = Server(body.url, connect_timeout=8)
        connection = Connection(server, user=body.bind_dn or None,
                                password=body.bind_password or None,
                                auto_bind=True)
        connection.unbind()
    except Exception as error:
        raise HTTPException(400, "ldap bind failed: %s" % error)
    return {"ok": True}
