from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from odf.assets.service import (create_asset, get_asset, list_assets,
                                list_versions, update_asset, update_draft)
from odf.db import get_session
from odf.modelstudio.content import (empty_dataset, empty_metric,
                                     validate_dataset, validate_metric)
from odf.modelstudio.service import (dataset_schema, preview_dataset,
                                     query_metric)
from odf.models import AssetVersion
from odf.services.approval import verify_token
from odf.services.audit import write_audit
from odf.services.auth import (claims_role, require_approver,
                                require_editor, require_user)
from odf.services.changes import apply as apply_change
from odf.services.changes import propose
from odf.services.masking import (create_column_policy,
                                  delete_column_policy,
                                  list_column_policies)
from odf.services.policies import (create_policy, delete_policy,
                                   list_policies)

router = APIRouter()


class ModelIn(BaseModel):
    name: str
    project_id: int = 1
    content: dict = Field(default_factory=dict)


class UpdateIn(BaseModel):
    name: str | None = None


class ContentIn(BaseModel):
    content: dict


class PreviewIn(BaseModel):
    limit: int = Field(100, ge=1, le=10000)
    content: dict | None = None


class RollbackIn(BaseModel):
    version: int


class PolicyIn(BaseModel):
    column: str
    op: str
    value: object
    roles: list[str] = []


class ColumnPolicyIn(BaseModel):
    column: str
    classification: str = "pii"
    mask_type: str = "redact"
    exempt_roles: list[str] = []


def _asset(s, asset_id, claims, type_):
    a = get_asset(s, asset_id)
    if not a or a.type != type_ or a.project_id != claims.get("project_id"):
        raise HTTPException(404, "%s not found" % type_)
    return a


def _list(s, claims, type_):
    return [{"id": a.id, "key": a.key, "name": a.name,
             "published": a.published_version_id is not None}
            for a in list_assets(s, claims["project_id"], type_)]


def _create(s, claims, type_, body, empty):
    if body.project_id != claims["project_id"]:
        raise HTTPException(403, "project mismatch")
    a = create_asset(s, body.project_id, type_, body.name,
                     body.content or empty(), claims["sub"], enabled=False)
    write_audit(s, claims["sub"], "create_%s" % type_, str(a.id),
                {"name": body.name})
    return {"id": a.id, "key": a.key}


def _get(s, a):
    draft = s.get(AssetVersion, a.draft_version_id) if a.draft_version_id else None
    pub = s.get(AssetVersion, a.published_version_id) if a.published_version_id else None
    return {"id": a.id, "key": a.key, "name": a.name,
            "draft_version": draft.version if draft else None,
            "published_version": pub.version if pub else None,
            "draft": draft.content_json if draft else None,
            "published": pub.content_json if pub else None}


def _update(s, claims, a, body, type_):
    a = update_asset(s, a.id, body.name, None)
    write_audit(s, claims["sub"], "update_%s" % type_, str(a.id),
                {"name": a.name})
    return {"id": a.id, "name": a.name}


def _draft(s, claims, a, body, type_):
    v = update_draft(s, a.id, body.content, claims["sub"])
    write_audit(s, claims["sub"], "update_%s_draft" % type_, str(a.id),
                {"version": v.version})
    return {"version": v.version}


def _versions(s, a):
    return [{"version": v.version, "status": v.status,
             "current": v.id == a.published_version_id,
             "created_by": v.created_by,
             "created_at": v.created_at.isoformat()}
            for v in list_versions(s, a.id)]


def _change(s, a, action, claims, token, payload=None):
    if not verify_token(a.id, action, token):
        raise HTTPException(403, "approval required")
    c = propose(s, a.project_id, claims["sub"], action, a.id, payload or {})
    try:
        apply_change(s, c.id, token)
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except (ValueError, KeyError) as e:
        raise HTTPException(400, str(e))


def _publish(s, a, claims, token, type_, validator):
    v = s.get(AssetVersion, a.draft_version_id) if a.draft_version_id else None
    if not v:
        raise HTTPException(400, "draft not found")
    errs = validator(s, v.content_json, a.project_id)
    if errs:
        raise HTTPException(400, {"errors": errs})
    _change(s, a, "publish_%s" % type_, claims, token)
    s.refresh(a)
    return {"version": s.get(AssetVersion, a.published_version_id).version}


def _rollback(s, a, body, claims, token, type_):
    _change(s, a, "rollback_%s" % type_, claims, token,
            {"version": body.version})
    s.refresh(a)
    return {"version": s.get(AssetVersion, a.published_version_id).version}


@router.get("/datasets")
def datasets(s: Session = Depends(get_session),
             claims: dict = Depends(require_user)):
    return _list(s, claims, "dataset")


@router.post("/datasets")
def create_dataset(body: ModelIn, s: Session = Depends(get_session),
                   claims: dict = Depends(require_editor)):
    return _create(s, claims, "dataset", body, empty_dataset)


@router.get("/datasets/{asset_id}")
def get_dataset(asset_id: int, s: Session = Depends(get_session),
                claims: dict = Depends(require_user)):
    return _get(s, _asset(s, asset_id, claims, "dataset"))


@router.put("/datasets/{asset_id}")
def update_dataset(asset_id: int, body: UpdateIn,
                   s: Session = Depends(get_session),
                   claims: dict = Depends(require_editor)):
    return _update(s, claims, _asset(s, asset_id, claims, "dataset"),
                   body, "dataset")


@router.put("/datasets/{asset_id}/draft")
def draft_dataset(asset_id: int, body: ContentIn,
                  s: Session = Depends(get_session),
                  claims: dict = Depends(require_editor)):
    return _draft(s, claims, _asset(s, asset_id, claims, "dataset"),
                  body, "dataset")


@router.post("/datasets/{asset_id}/validate")
def validate_dataset_route(asset_id: int, body: ContentIn,
                           s: Session = Depends(get_session),
                           claims: dict = Depends(require_user)):
    a = _asset(s, asset_id, claims, "dataset")
    errs = validate_dataset(s, body.content, a.project_id)
    return {"valid": not errs, "errors": errs}


@router.get("/datasets/{asset_id}/schema")
def schema_dataset(asset_id: int, s: Session = Depends(get_session),
                   claims: dict = Depends(require_user)):
    a = _asset(s, asset_id, claims, "dataset")
    try:
        return dataset_schema(s, a.id)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/datasets/{asset_id}/preview")
def preview_dataset_route(asset_id: int, body: PreviewIn,
                          s: Session = Depends(get_session),
                          claims: dict = Depends(require_editor)):
    a = _asset(s, asset_id, claims, "dataset")
    try:
        result = preview_dataset(s, a.id, body.content, body.limit,
                                 role=claims_role(s, claims))
    except ValueError as e:
        raise HTTPException(400, str(e))
    write_audit(s, claims["sub"], "query_dataset", str(a.id),
                {"rows": result["row_count"]})
    return result


@router.get("/datasets/{asset_id}/policies")
def policies(asset_id: int, s: Session = Depends(get_session),
             claims: dict = Depends(require_user)):
    a = _asset(s, asset_id, claims, "dataset")
    return list_policies(s, a.project_id, a.id)


@router.post("/datasets/{asset_id}/policies")
def add_policy(asset_id: int, body: PolicyIn,
               s: Session = Depends(get_session),
               claims: dict = Depends(require_editor)):
    a = _asset(s, asset_id, claims, "dataset")
    try:
        return create_policy(s, a.project_id, a.id, body.column, body.op,
                             body.value, body.roles, claims["sub"])
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/datasets/{asset_id}/policies/{policy_id}")
def remove_policy(asset_id: int, policy_id: int,
                  s: Session = Depends(get_session),
                  claims: dict = Depends(require_editor)):
    a = _asset(s, asset_id, claims, "dataset")
    try:
        return delete_policy(s, a.project_id, a.id, policy_id,
                             claims["sub"])
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/datasets/{asset_id}/column-policies")
def column_policies(asset_id: int, s: Session = Depends(get_session),
                    claims: dict = Depends(require_user)):
    a = _asset(s, asset_id, claims, "dataset")
    return list_column_policies(s, a.project_id, a.id)


@router.post("/datasets/{asset_id}/column-policies")
def add_column_policy(asset_id: int, body: ColumnPolicyIn,
                      s: Session = Depends(get_session),
                      claims: dict = Depends(require_editor)):
    a = _asset(s, asset_id, claims, "dataset")
    try:
        return create_column_policy(
            s, a.project_id, a.id, body.column, body.classification,
            body.mask_type, body.exempt_roles, claims["sub"])
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/datasets/{asset_id}/column-policies/{policy_id}")
def remove_column_policy(asset_id: int, policy_id: int,
                         s: Session = Depends(get_session),
                         claims: dict = Depends(require_editor)):
    a = _asset(s, asset_id, claims, "dataset")
    try:
        return delete_column_policy(s, a.project_id, a.id, policy_id,
                                    claims["sub"])
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/datasets/{asset_id}/versions")
def versions_dataset(asset_id: int, s: Session = Depends(get_session),
                     claims: dict = Depends(require_user)):
    return _versions(s, _asset(s, asset_id, claims, "dataset"))


@router.post("/datasets/{asset_id}/publish")
def publish_dataset(asset_id: int, approval_token: str,
                    s: Session = Depends(get_session),
                    claims: dict = Depends(require_approver)):
    a = _asset(s, asset_id, claims, "dataset")
    return _publish(s, a, claims, approval_token, "dataset", validate_dataset)


@router.post("/datasets/{asset_id}/rollback")
def rollback_dataset(asset_id: int, body: RollbackIn, approval_token: str,
                     s: Session = Depends(get_session),
                     claims: dict = Depends(require_approver)):
    a = _asset(s, asset_id, claims, "dataset")
    return _rollback(s, a, body, claims, approval_token, "dataset")


@router.get("/metrics")
def metrics(s: Session = Depends(get_session),
            claims: dict = Depends(require_user)):
    return _list(s, claims, "metric")


@router.post("/metrics")
def create_metric(body: ModelIn, s: Session = Depends(get_session),
                  claims: dict = Depends(require_editor)):
    return _create(s, claims, "metric", body, empty_metric)


@router.get("/metrics/{asset_id}")
def get_metric(asset_id: int, s: Session = Depends(get_session),
               claims: dict = Depends(require_user)):
    return _get(s, _asset(s, asset_id, claims, "metric"))


@router.put("/metrics/{asset_id}")
def update_metric(asset_id: int, body: UpdateIn,
                  s: Session = Depends(get_session),
                  claims: dict = Depends(require_editor)):
    return _update(s, claims, _asset(s, asset_id, claims, "metric"),
                   body, "metric")


@router.put("/metrics/{asset_id}/draft")
def draft_metric(asset_id: int, body: ContentIn,
                 s: Session = Depends(get_session),
                 claims: dict = Depends(require_editor)):
    return _draft(s, claims, _asset(s, asset_id, claims, "metric"),
                  body, "metric")


@router.post("/metrics/{asset_id}/validate")
def validate_metric_route(asset_id: int, body: ContentIn,
                          s: Session = Depends(get_session),
                          claims: dict = Depends(require_user)):
    a = _asset(s, asset_id, claims, "metric")
    errs = validate_metric(s, body.content, a.project_id)
    return {"valid": not errs, "errors": errs}


@router.post("/metrics/{asset_id}/query")
def query_metric_route(asset_id: int, body: PreviewIn,
                       s: Session = Depends(get_session),
                       claims: dict = Depends(require_editor)):
    a = _asset(s, asset_id, claims, "metric")
    try:
        result = query_metric(s, a.id, body.content, body.limit,
                              role=claims_role(s, claims))
    except ValueError as e:
        raise HTTPException(400, str(e))
    write_audit(s, claims["sub"], "query_metric", str(a.id),
                {"rows": result["row_count"]})
    return result


@router.get("/metrics/{asset_id}/versions")
def versions_metric(asset_id: int, s: Session = Depends(get_session),
                    claims: dict = Depends(require_user)):
    return _versions(s, _asset(s, asset_id, claims, "metric"))


@router.post("/metrics/{asset_id}/publish")
def publish_metric(asset_id: int, approval_token: str,
                   s: Session = Depends(get_session),
                   claims: dict = Depends(require_approver)):
    a = _asset(s, asset_id, claims, "metric")
    return _publish(s, a, claims, approval_token, "metric", validate_metric)


@router.post("/metrics/{asset_id}/rollback")
def rollback_metric(asset_id: int, body: RollbackIn, approval_token: str,
                    s: Session = Depends(get_session),
                    claims: dict = Depends(require_approver)):
    a = _asset(s, asset_id, claims, "metric")
    return _rollback(s, a, body, claims, approval_token, "metric")
