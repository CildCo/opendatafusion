from fastapi import (APIRouter, Depends, File, Form, HTTPException,
                     UploadFile)
import json

from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.services.auth import require_platform_admin
from odf.services.platform import (get_doc, overview, public_doc, update_doc)

router = APIRouter()


class RetentionIn(BaseModel):
    apply: bool = False
    days: dict = {}


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


@router.get("/platform/retention")
def retention(s: Session = Depends(get_session),
              claims: dict = Depends(require_platform_admin)):
    from odf.services.retention import counts, policies
    return {"policies": policies(), "counts": counts(s)}


@router.post("/platform/retention/prune")
def retention_prune(body: RetentionIn, s: Session = Depends(get_session),
                    claims: dict = Depends(require_platform_admin)):
    from odf.services.audit import write_audit
    from odf.services.retention import prune
    try:
        result = prune(s, body.days, apply=bool(body.apply))
    except ValueError as error:
        raise HTTPException(400, str(error))
    if body.apply:
        removed = {k: v["removed"] for k, v in result.items()
                   if v["removed"]}
        write_audit(s, claims["sub"], "retention_prune", "retention",
                    {"removed": removed})
    return result


@router.get("/platform/doctor")
def doctor(s: Session = Depends(get_session),
           claims: dict = Depends(require_platform_admin)):
    from odf.services.doctor import check
    return check(s)


@router.get("/platform/overview")
def platform_overview(s: Session = Depends(get_session),
                      claims: dict = Depends(require_platform_admin)):
    return overview(s)


@router.get("/platform/runtime")
def runtime(s: Session = Depends(get_session),
            claims: dict = Depends(require_platform_admin)):
    from sqlalchemy import func
    from odf import __version__
    from odf.models import Asset, Job, Project, User
    from odf.settings import get_settings
    settings = get_settings()
    running = (s.query(Job).filter(Job.status == "running").count())
    workers = {row[0] for row in s.query(Job.locked_by).filter(
        Job.status == "running", Job.locked_by.isnot(None)).all()}
    return {"version": __version__, "license": "Apache-2.0",
            "database": s.bind.dialect.name,
            "scheduler": "single leader (advisory lock)",
            "queue": {
                "queued": s.query(Job).filter(Job.status == "queued").count(),
                "running": running, "workers": len(workers)},
            "platform": {
                "projects": s.query(func.count(Project.id)).scalar() or 0,
                "users": s.query(func.count(User.id)).scalar() or 0,
                "assets": s.query(func.count(Asset.id)).scalar() or 0},
            "capacity": {"query_max_rows": settings.query_max_rows,
                         "file_mb": settings.file_max_mb}}


@router.get("/platform/backup/export")
def backup_export(s: Session = Depends(get_session),
                  claims: dict = Depends(require_platform_admin)):
    from odf.services.audit import write_audit
    from odf.services.backup import export_bytes
    payload = export_bytes(s)
    write_audit(s, claims["sub"], "backup_export", "platform",
                {"bytes": len(payload)})
    return Response(content=payload, media_type="application/json",
                    headers={"Content-Disposition":
                             "attachment; filename=odf-backup.json"})


@router.post("/platform/backup/restore")
async def backup_restore(file: UploadFile = File(...),
                         confirm: str = Form(...),
                         s: Session = Depends(get_session),
                         claims: dict = Depends(require_platform_admin)):
    from odf.services.audit import write_audit
    from odf.services.backup import restore
    if confirm != "RESTORE":
        raise HTTPException(400, "confirmation must be RESTORE")
    raw = await file.read()
    if len(raw) > 200 * 1024 * 1024:
        raise HTTPException(400, "backup is too large")
    try:
        counts = restore(s, raw, claims.get("sub", ""))
    except (ValueError, json.JSONDecodeError) as error:
        raise HTTPException(400, str(error))
    write_audit(s, claims["sub"], "backup_restore", "platform",
                {"tables": len(counts)})
    return {"restored": counts}


@router.post("/platform/lineage/test")
def lineage_test(s: Session = Depends(get_session),
                 claims: dict = Depends(require_platform_admin)):
    from odf.lineage.openlineage import send_test
    try:
        return send_test(s)
    except ValueError as error:
        raise HTTPException(400, str(error))


@router.post("/platform/catalog/sync")
def catalog_sync_now(s: Session = Depends(get_session),
                     claims: dict = Depends(require_platform_admin)):
    from odf.lineage.catalog_sync import push
    from odf.services.audit import write_audit
    try:
        out = push(s)
    except ValueError as error:
        raise HTTPException(400, str(error))
    write_audit(s, claims["sub"], "catalog_sync", "platform", out)
    return out


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
