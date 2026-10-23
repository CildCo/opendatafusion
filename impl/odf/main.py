import json
import logging
import time
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from odf.api import (alerts, approvals, audit, auth, catalog, changes,
                     dashboard, datasources, flows, health, interfaces, mcp,
                     probe,
                     metadata, openapi_gateway, projects, quality, runs,
                     standards, users)
from odf.api.metrics import EXCLUDED, record, router as metrics_router
import odf.apistudio.api as api_studio
import odf.appstudio.api as app_api
import odf.dashboards.api as dashboard_api
import odf.ops.api as ops_api
import odf.share.api as share_api
import odf.workbench.api as workbench_api
import odf.api.grants as grants_api
import odf.webhooks.api as webhooks_api
import odf.files.api as files_api
import odf.portal.api as portal_api
import odf.api.stats as stats_api
import odf.modelstudio.api as modelstudio_api
import odf.pipeline.api as pipeline_api
from odf.services.auth import require_approver, require_user
from odf.settings import get_settings

_request_log = logging.getLogger("odf.request")
if get_settings().log_json:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

app = FastAPI(title="ODF")
app.include_router(auth.router, prefix="/api/v1")
for r in (datasources.router, metadata.router, flows.router, runs.router,
          interfaces.router, health.router, mcp.router, users.router,
          projects.router, catalog.router, quality.router,
          standards.router, alerts.router, changes.router, audit.router,
          dashboard.router):
    app.include_router(r, prefix="/api/v1",
                       dependencies=[Depends(require_user)])
app.include_router(approvals.router, prefix="/api/v1",
                   dependencies=[Depends(require_approver)])
app.include_router(pipeline_api.router, prefix="/api/v1",
                   dependencies=[Depends(require_user)])
app.include_router(api_studio.router, prefix="/api/v1",
                   dependencies=[Depends(require_user)])
app.include_router(modelstudio_api.router, prefix="/api/v1",
                   dependencies=[Depends(require_user)])
app.include_router(app_api.router, prefix="/api/v1",
                   tags=["apps"], dependencies=[Depends(require_user)])
app.include_router(ops_api.router, prefix="/api/v1",
                   tags=["ops"], dependencies=[Depends(require_user)])
app.include_router(share_api.router, prefix="/api/v1",
                   tags=["share"], dependencies=[Depends(require_user)])
app.include_router(workbench_api.router, prefix="/api/v1",
                   tags=["workbench"], dependencies=[Depends(require_user)])
app.include_router(grants_api.router, prefix="/api/v1",
                   tags=["grants"], dependencies=[Depends(require_user)])
app.include_router(webhooks_api.router, prefix="/api/v1",
                   tags=["webhooks"], dependencies=[Depends(require_user)])
app.include_router(files_api.router, prefix="/api/v1",
                   tags=["files"], dependencies=[Depends(require_user)])
app.include_router(portal_api.router, prefix="/api/v1",
                   tags=["portal"], dependencies=[Depends(require_user)])
app.include_router(stats_api.router, prefix="/api/v1",
                   tags=["stats"], dependencies=[Depends(require_user)])
app.include_router(share_api.public_router, prefix="/api/v1",
                   tags=["public-share"])
app.include_router(dashboard_api.router, prefix="/api/v1",
                   dependencies=[Depends(require_user)])
app.include_router(probe.router)
from odf.observability import configure_observability
configure_observability(app)
app.include_router(openapi_gateway.router)
app.include_router(metrics_router)


MENU_PREFIXES = (
    ("/api/v1/datasources", "/datasources"),
    ("/api/v1/catalog", "/catalog"),
    ("/api/v1/pipelines", "/pipelines"),
    ("/api/v1/flows", "/flows"),
    ("/api/v1/apis", "/apis"),
    ("/api/v1/api-catalog", "/grants"),
    ("/api/v1/api-requests", "/grants"),
    ("/api/v1/api-grants", "/grants"),
    ("/api/v1/tools", "/tools"),
    ("/api/v1/mcp", "/tools"),
    ("/api/v1/datasets", "/datasets"),
    ("/api/v1/metrics", "/datasets"),
    ("/api/v1/dashboards", "/dashboards"),
    ("/api/v1/apps", "/apps"),
    ("/api/v1/workbench", "/workbench"),
    ("/api/v1/webhooks", "/webhooks"),
    ("/api/v1/files", "/files"),
    ("/api/v1/users", "/users"),
    ("/api/v1/audit", "/audit"),
    ("/api/v1/ops", "/ops"),
    ("/api/v1/api-stats", "/ops"),
    ("/api/v1/alerts", "/alerts"),
    ("/api/v1/changes", "/changes"),
    ("/api/v1/quality", "/quality"),
)


def _metric_path(request) -> str:
    route = request.scope.get("route")
    template = getattr(route, "path", None)
    if not template:
        return request.url.path
    static = template.split("{", 1)[0].rstrip("/")
    if static:
        idx = request.url.path.find(static)
        if idx > 0:
            return request.url.path[:idx] + template
    return template


@app.middleware("http")
async def request_context(request, call_next):
    rid = request.headers.get("X-Request-Id") or uuid.uuid4().hex
    started = time.time()
    try:
        response = await call_next(request)
    except Exception:
        if not request.url.path.startswith(EXCLUDED):
            record(request.method, request.url.path, 500,
                   time.time() - started)
        raise
    response.headers["X-Request-Id"] = rid
    elapsed = time.time() - started
    if not request.url.path.startswith(EXCLUDED):
        record(request.method, _metric_path(request),
               response.status_code, elapsed)
    if get_settings().log_json:
        _request_log.info(json.dumps({
            "request_id": rid, "method": request.method,
            "path": request.url.path, "status": response.status_code,
            "ms": int(elapsed * 1000)}))
    return response


@app.middleware("http")
async def menu_permission(request: Request, call_next):
    path = request.url.path
    menu = next((m for p, m in MENU_PREFIXES if path.startswith(p)), None)
    if menu is None:
        return await call_next(request)
    auth = request.headers.get("Authorization", "")
    scheme, _, token = auth.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return await call_next(request)
    from odf.db import SessionLocal
    from odf.models import PortalSetting, User
    from odf.services.auth import decode_token
    try:
        claims = decode_token(token)
    except Exception:
        return await call_next(request)
    with SessionLocal() as s:
        user = s.get(User, int(claims["sub"]))
        denied = False
        if user and user.active and user.role != "admin":
            row = (s.query(PortalSetting)
                   .filter_by(project_id=claims["project_id"]).first())
            allowed = row.allowed_menus if row else None
            hidden = (row.hidden_menus or []) if row else []
            denied = (menu not in allowed) if allowed is not None                 else (menu in hidden)
    if denied:
        return JSONResponse({"detail": "menu access denied"},
                            status_code=403)
    return await call_next(request)


@app.get("/")
def root():
    return RedirectResponse("/ui/")


_static = Path(__file__).parent / "static"
if _static.exists():
    app.mount("/ui", StaticFiles(directory=str(_static), html=True), name="ui")
