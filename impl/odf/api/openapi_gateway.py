import ipaddress
import json
import time
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from odf.api.metrics import inc
from odf.apistudio.service import ApiError, run_content
from odf.db import SessionLocal
from odf.models import AkSk, Asset, AssetVersion, Interface, Project
from odf.services.aksk import verify
from odf.services.audit import write_audit
from odf.services.crypto import decrypt_secret
from odf.services.grants import can_access
from odf.services.interface import execute_interface
from odf.services.ratelimit import check_rate, client_allowed, record_stat
from odf.settings import get_settings

router = APIRouter()


def extract_auth(header: str) -> tuple[str, str]:
    ak, _, sig = (header or "").partition(":")
    return ak, sig


def resolve_api_by_key(session, interface_key):
    return (session.query(Asset)
            .filter_by(type="api", key=interface_key).first())


def resolve_api_asset(session, project_key, interface_key):
    project = session.query(Project).filter_by(code=project_key).first()
    if not project:
        return None
    return (session.query(Asset)
            .filter_by(type="api", key=interface_key,
                       project_id=project.id).first())


def parse_params(body):
    try:
        data = json.loads(body or b"{}")
    except (ValueError, TypeError):
        raise HTTPException(400, "invalid JSON body")
    if not isinstance(data, dict):
        raise HTTPException(400, "JSON body must be an object")
    return data


def resolve_access(session, ak, project_key, interface_key):
    project = session.query(Project).filter_by(code=project_key).first()
    if not project:
        raise HTTPException(403, "project not found")
    cred = session.query(AkSk).filter_by(ak=ak, enabled=True).first()
    if not cred:
        raise HTTPException(401, "missing access key")
    if cred.project_id != project.id:
        raise HTTPException(
            403, "interface permission denied")
    iface = (session.query(Interface)
             .filter_by(interface_key=interface_key, status=1).first())
    if not iface:
        raise HTTPException(404, "interface not found")
    if iface.project_id != project.id:
        raise HTTPException(
            403, "interface permission denied")
    return cred, iface


@router.post("/openapi/{interface_key}")
async def call_interface(interface_key: str, request: Request):
    body = await request.body()
    project_key = request.headers.get("projectKey")
    if not project_key:
        raise HTTPException(400, "missing projectKey header")
    auth = request.headers.get("Authorization", "")
    ak, _ = extract_auth(auth)
    with SessionLocal() as s:
        asset = resolve_api_by_key(s, interface_key)
        if asset is not None:
            project = s.query(Project).filter_by(code=project_key).first()
            if not project:
                raise HTTPException(403, "project not found")
            cred = s.query(AkSk).filter_by(ak=ak, enabled=True).first()
            if not cred:
                raise HTTPException(
                    401, "missing access key")
            if cred.project_id != project.id:
                raise HTTPException(
                    403, "interface permission denied")
            host = request.client.host if request.client else ""
            try:
                ipaddress.ip_address(host)
            except ValueError:
                host = "127.0.0.1"
            if not client_allowed(host, cred.ip_allowlist or []):
                raise HTTPException(403, "client IP is not allowed")
            ok = verify(ak, decrypt_secret(cred.sk_encrypted), request.method,
                        body, request.headers.get("Content-Type", ""),
                        request.headers.get("Date", "0"), request.url.path,
                        auth, int(time.time() * 1000))
            if not ok:
                raise HTTPException(401, "signature mismatch or expired")
            if not can_access(s, asset, project.id):
                raise HTTPException(
                    403, "interface permission denied")
            if not asset.enabled or not asset.published_version_id:
                raise HTTPException(404, "interface not found")
            version = s.get(AssetVersion, asset.published_version_id)
            if not version:
                raise HTTPException(404, "interface not found")
            content_auth = version.content_json.get("auth") or {}
            if not client_allowed(host, content_auth.get("ip_allowlist") or []):
                raise HTTPException(403, "client IP is not allowed")
            candidates = [c for c in (
                cred.rate_limit_per_min,
                content_auth.get("rate_limit_per_min"),
                get_settings().api_rate_default) if c and c > 0]
            limit = min(candidates) if candidates else 0
            day = datetime.now(timezone.utc).date()
            if not check_rate(s, "%s:%s" % (asset.id, ak), limit):
                record_stat(s, day, asset.id, ak, False, 0)
                inc("api_calls_total", status="rate_limited")
                raise HTTPException(429, "rate limit exceeded")
            started = time.time()
            params = parse_params(body)
            try:
                result = run_content(s, asset, version.content_json, params,
                                     role="viewer")
            except ApiError as e:
                inc("api_calls_total", status="error")
                record_stat(s, day, asset.id, ak, False,
                            (time.time() - started) * 1000)
                write_audit(s, actor=ak, action="openapi_call",
                            target=interface_key,
                            detail={"error": str(e)})
                raise HTTPException(400, str(e))
            inc("api_calls_total", status="success")
            record_stat(s, day, asset.id, ak, True,
                        (time.time() - started) * 1000)
            write_audit(s, actor=ak, action="openapi_call",
                        target=interface_key,
                        detail={"rows": result["row_count"]})
            return {"total": result["row_count"], "results": result["rows"]}

        cred, iface = resolve_access(s, ak, project_key, interface_key)
        host = request.client.host if request.client else ""
        try:
            ipaddress.ip_address(host)
        except ValueError:
            host = "127.0.0.1"
        if not client_allowed(host, cred.ip_allowlist or []):
            raise HTTPException(403, "client IP is not allowed")
        ok = verify(ak, decrypt_secret(cred.sk_encrypted), request.method, body,
                    request.headers.get("Content-Type", ""),
                    request.headers.get("Date", "0"), request.url.path,
                    auth, int(time.time() * 1000))
        if not ok:
            raise HTTPException(401, "signature mismatch or expired")
        limit = min([c for c in (cred.rate_limit_per_min,
                                  get_settings().api_rate_default)
                     if c and c > 0] or [0])
        if not check_rate(s, "iface:%s:%s" % (iface.id, ak), limit):
            raise HTTPException(429, "rate limit exceeded")
        params = parse_params(body)
        rows, total = execute_interface(s, iface.id, params)
        write_audit(s, actor=ak, action="openapi_call",
                    target=interface_key, detail={"rows": total})
        return {"total": total, "results": rows}
