import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.services.aksk_admin import issue_aksk, list_aksk, revoke_aksk
from odf.models import ProjectMember, User
from odf.services.audit import write_audit
from odf.services.auth import (require_admin, require_approver,
                               require_editor, require_platform_admin,
                               require_project_admin, require_user)
from odf.services.platform import is_platform_admin
from odf.services.projects import (add_member, create_project, list_members,
                                   list_projects, list_projects_for_user,
                                   remove_member)

router = APIRouter()


class ProjectIn(BaseModel):
    code: str
    name: str
    environment: str = "dev"


class ProjectUpdateIn(BaseModel):
    name: str | None = None
    status: int | None = None
    environment: str | None = None
    quota: dict | None = None


class MemberIn(BaseModel):
    user_id: int
    role: str = "viewer"


class KeyPolicyIn(BaseModel):
    ip_allowlist: list[str] | None = None
    rate_limit_per_min: int | None = None


class BundleIn(BaseModel):
    bundle: dict


class PromoteIn(BaseModel):
    source_project_id: int


def _project(p):
    return {"id": p.id, "code": p.code, "name": p.name,
            "status": p.status, "environment": p.environment,
            "quota": p.quota_json or {}}


@router.get("/projects")
def projects(s: Session = Depends(get_session),
             claims: dict = Depends(require_admin)):
    return [_project(p) for p in list_projects(s)]


@router.get("/projects/mine")
def mine(s: Session = Depends(get_session),
         claims: dict = Depends(require_user)):
    user = s.get(User, int(claims["sub"]))
    if not user or not user.active:
        raise HTTPException(403, "user is inactive")
    return [_project(p) for p in list_projects_for_user(s, user)]


@router.get("/projects/onboarding")
def onboarding(s: Session = Depends(get_session),
               claims: dict = Depends(require_user)):
    from odf.models import Asset, Datasource
    project_id = claims["project_id"]
    counts = {
        "datasources": s.query(Datasource)
        .filter_by(project_id=project_id).count(),
        "pipelines": s.query(Asset).filter_by(
            project_id=project_id, type="pipeline").count(),
        "datasets": s.query(Asset).filter_by(
            project_id=project_id, type="dataset").count(),
        "dashboards": s.query(Asset).filter_by(
            project_id=project_id, type="dashboard").count(),
        "apis": s.query(Asset).filter_by(
            project_id=project_id, type="api").count(),
    }
    steps = [
        {"key": "datasource", "done": counts["datasources"] > 0,
         "link": "/datasources"},
        {"key": "pipeline", "done": counts["pipelines"] > 0,
         "link": "/pipelines"},
        {"key": "dataset", "done": counts["datasets"] > 0,
         "link": "/datasets"},
        {"key": "dashboard", "done": counts["dashboards"] > 0,
         "link": "/dashboards"},
        {"key": "api", "done": counts["apis"] > 0, "link": "/apis"},
    ]
    return {"steps": steps, "counts": counts,
            "complete": all(step["done"] for step in steps)}


@router.post("/projects/sample")
def sample(claims: dict = Depends(require_editor),
           s: Session = Depends(get_session)):
    from odf.services.sample import create_sample
    result = create_sample(s, claims["project_id"], claims["sub"])
    write_audit(s, claims["sub"], "create_sample_project",
                str(claims["project_id"]), {})
    return result


@router.get("/projects/{project_id}/bundle")
def export_project_bundle(project_id: int,
                          s: Session = Depends(get_session),
                          claims: dict = Depends(require_project_admin)):
    _scope(s, claims, project_id)
    from odf.services.bundles import export_bundle
    try:
        bundle = export_bundle(s, project_id)
    except ValueError as error:
        raise HTTPException(404, str(error))
    body = json.dumps(bundle, ensure_ascii=False, indent=2, default=str)
    return Response(
        content=body, media_type="application/json",
        headers={"Content-Disposition":
                 'attachment; filename="odf-bundle-%d.json"' % project_id})


@router.post("/projects/{project_id}/bundle/validate")
def validate_project_bundle(project_id: int, body: BundleIn,
                            s: Session = Depends(get_session),
                            claims: dict = Depends(require_project_admin)):
    _scope(s, claims, project_id)
    from odf.services.bundles import validate_bundle
    try:
        return validate_bundle(s, project_id, body.bundle)
    except ValueError as error:
        raise HTTPException(400, str(error))


@router.post("/projects/{project_id}/bundle/import")
def import_project_bundle(project_id: int, body: BundleIn,
                          s: Session = Depends(get_session),
                          claims: dict = Depends(require_project_admin)):
    _scope(s, claims, project_id)
    from odf.services.bundles import import_bundle
    try:
        result = import_bundle(s, project_id, body.bundle, claims["sub"])
    except ValueError as error:
        raise HTTPException(400, str(error))
    write_audit(s, claims["sub"], "import_project_bundle",
                str(project_id), {k: result[k] for k in
                                  ("created", "updated", "skipped")})
    return result


@router.post("/projects/{project_id}/promote")
def promote_project(project_id: int, body: PromoteIn,
                    s: Session = Depends(get_session),
                    claims: dict = Depends(require_platform_admin)):
    from odf.models import Project
    from odf.services.bundles import promote_project as promote
    source = s.get(Project, body.source_project_id)
    target = s.get(Project, project_id)
    if not source or not target:
        raise HTTPException(404, "project not found")
    try:
        result = promote(s, source.id, target.id, claims["sub"])
    except ValueError as error:
        raise HTTPException(400, str(error))
    write_audit(s, claims["sub"], "promote_project_bundle",
                str(target.id), {"source_project_id": source.id,
                                 "import": result["import"]})
    return result


@router.post("/projects")
def create(body: ProjectIn, s: Session = Depends(get_session),
           claims: dict = Depends(require_platform_admin)):
    if body.environment not in ("dev", "staging", "prod"):
        raise HTTPException(400, "environment must be dev, staging or prod")
    p = create_project(s, body.code, body.name, body.environment)
    write_audit(s, claims["sub"], "create_project", str(p.id),
                {"code": p.code, "name": p.name})
    return _project(p)


@router.put("/projects/{project_id}")
def update(project_id: int, body: ProjectUpdateIn,
           s: Session = Depends(get_session),
           claims: dict = Depends(require_platform_admin)):
    from odf.models import Project
    project = s.get(Project, project_id)
    if not project:
        raise HTTPException(404, "project not found")
    if body.name is not None:
        project.name = body.name
    if body.status is not None:
        project.status = body.status
    if body.environment is not None:
        if body.environment not in ("dev", "staging", "prod"):
            raise HTTPException(400,
                                "environment must be dev, staging or prod")
        project.environment = body.environment
    if body.quota is not None:
        project.quota_json = body.quota
    s.commit()
    write_audit(s, claims["sub"], "update_project", str(project.id),
                {"status": project.status, "quota": project.quota_json})
    return _project(project)


def _scope(s, claims, project_id):
    user = s.get(User, int(claims["sub"]))
    if is_platform_admin(user):
        return
    if int(claims["project_id"]) != int(project_id):
        raise HTTPException(404, "project not found")


@router.get("/projects/{project_id}/usage")
def project_usage(project_id: int, s: Session = Depends(get_session),
                  claims: dict = Depends(require_project_admin)):
    _scope(s, claims, project_id)
    from odf.services.quota import usage
    return usage(s, project_id)


@router.get("/projects/{project_id}/members")
def members(project_id: int, s: Session = Depends(get_session),
            claims: dict = Depends(require_project_admin)):
    _scope(s, claims, project_id)
    rows = list_members(s, project_id)
    users = {u.id: u for u in s.query(User).filter(
        User.id.in_([m.user_id for m in rows])).all()} if rows else {}
    return [{"id": m.id, "user_id": m.user_id,
             "username": (users.get(m.user_id).username
                          if users.get(m.user_id) else None),
             "role": m.role} for m in rows]


@router.get("/projects/{project_id}/users/lookup")
def lookup_user(project_id: int, username: str,
                s: Session = Depends(get_session),
                claims: dict = Depends(require_project_admin)):
    _scope(s, claims, project_id)
    u = s.query(User).filter_by(username=username).first()
    if not u:
        raise HTTPException(404, "user not found")
    member = (s.query(ProjectMember)
              .filter_by(project_id=project_id, user_id=u.id).first())
    return {"id": u.id, "username": u.username, "active": bool(u.active),
            "member": member is not None}


@router.post("/projects/{project_id}/members")
def add(project_id: int, body: MemberIn, s: Session = Depends(get_session),
        claims: dict = Depends(require_project_admin)):
    _scope(s, claims, project_id)
    m = add_member(s, project_id, body.user_id, body.role)
    write_audit(s, claims["sub"], "add_project_member", str(project_id),
                {"user_id": body.user_id, "role": body.role})
    return {"id": m.id, "user_id": m.user_id, "role": m.role}


@router.delete("/projects/{project_id}/members/{user_id}", status_code=204)
def remove(project_id: int, user_id: int, s: Session = Depends(get_session),
           claims: dict = Depends(require_project_admin)):
    _scope(s, claims, project_id)
    if not remove_member(s, project_id, user_id):
        raise HTTPException(404, "member not found")
    write_audit(s, claims["sub"], "remove_project_member", str(project_id),
                {"user_id": user_id})


@router.post("/projects/{project_id}/aksk")
def issue(project_id: int, s: Session = Depends(get_session),
          claims: dict = Depends(require_approver)):
    row, sk = issue_aksk(s, project_id)
    return {"ak": row.ak, "sk": sk}          # SK shown once


@router.get("/projects/{project_id}/aksk")
def list_keys(project_id: int, s: Session = Depends(get_session),
              claims: dict = Depends(require_approver)):
    return [{"ak": r.ak, "enabled": r.enabled} for r in list_aksk(s, project_id)]


@router.put("/projects/{project_id}/aksk/{ak}")
def key_policy(project_id: int, ak: str, body: KeyPolicyIn,
               s: Session = Depends(get_session),
               claims: dict = Depends(require_approver)):
    from odf.models import AkSk
    import ipaddress
    row = s.query(AkSk).filter_by(ak=ak, project_id=project_id).first()
    if not row:
        raise HTTPException(404, "key not found")
    if body.ip_allowlist is not None:
        for item in body.ip_allowlist:
            try:
                ipaddress.ip_network(item, strict=False)
            except (TypeError, ValueError):
                raise HTTPException(400, "invalid CIDR: %s" % item)
        row.ip_allowlist = body.ip_allowlist
    if body.rate_limit_per_min is not None:
        if not 0 <= body.rate_limit_per_min <= 100000:
            raise HTTPException(400, "invalid rate limit")
        row.rate_limit_per_min = body.rate_limit_per_min
    s.commit()
    return {"ak": row.ak, "ip_allowlist": row.ip_allowlist or [],
            "rate_limit_per_min": row.rate_limit_per_min}


@router.delete("/projects/{project_id}/aksk/{ak}")
def revoke(project_id: int, ak: str, s: Session = Depends(get_session),
           claims: dict = Depends(require_approver)):
    try:
        return {"ak": revoke_aksk(s, ak).ak, "enabled": False}
    except ValueError as e:
        raise HTTPException(404, str(e))
