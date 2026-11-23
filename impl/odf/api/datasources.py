from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.connectors.registry import (build_dsn, capabilities, catalog,
                                     masked_config, parse_dsn,
                                     require_spec)
from odf.models import Datasource
from odf.services.audit import write_audit
from odf.services.auth import require_editor, require_user
from odf.services.datasource import (DatasourceInUse, check_connection,
                                     create_datasource, delete_datasource,
                                     get_dsn, mask_dsn, normalize_dsn,
                                     update_datasource)

router = APIRouter()


class DsIn(BaseModel):
    name: str
    dsn: str | None = None
    config: dict | None = None
    kind: str = "postgres"
    project_id: int | None = None


class DsUpdateIn(BaseModel):
    name: str | None = None
    dsn: str | None = None
    config: dict | None = None


class DsTestIn(BaseModel):
    kind: str
    dsn: str | None = None
    config: dict | None = None
    datasource_id: int | None = None


def _build(kind: str, dsn: str | None, config: dict | None,
           current: str | None = None) -> str:
    require_spec(kind)
    if config:
        if current:
            from odf.connectors.registry import parse_dsn
            merged = parse_dsn(kind, current)
            for key, value in config.items():
                if key.startswith("has_"):
                    continue
                if value in (None, ""):
                    continue
                merged[key] = value
            config = merged
        return build_dsn(kind, config)
    if dsn:
        return normalize_dsn(kind, dsn)
    raise ValueError("connection details are required")


@router.get("/datasources/connectors")
def connectors(claims: dict = Depends(require_user)):
    return catalog()


@router.post("/datasources/test")
def test_body(body: DsTestIn, s: Session = Depends(get_session),
              claims: dict = Depends(require_editor)):
    try:
        current = None
        if body.datasource_id is not None:
            existing = s.get(Datasource, body.datasource_id)
            if not existing or existing.project_id != claims["project_id"]:
                raise ValueError("datasource not found")
            current = get_dsn(existing)
        dsn = _build(body.kind, body.dsn, body.config, current=current)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return check_connection(dsn, kind=body.kind)


@router.post("/datasources")
def create(body: DsIn, s: Session = Depends(get_session),
           claims: dict = Depends(require_editor)):
    if body.project_id is not None and             body.project_id != claims["project_id"]:
        raise HTTPException(403, "project mismatch")
    try:
        dsn = _build(body.kind, body.dsn, body.config)
        ds = create_datasource(s, claims["project_id"], body.name, dsn,
                               body.kind)
    except ValueError as e:
        raise HTTPException(400, str(e))
    write_audit(s, claims["sub"], "create_datasource", str(ds.id),
                {"name": body.name, "kind": body.kind})
    return {"id": ds.id, "name": ds.name, "dsn": mask_dsn(get_dsn(ds))}


@router.get("/datasources")
def list_ds(s: Session = Depends(get_session),
            claims: dict = Depends(require_user)):
    rows = []
    for d in (s.query(Datasource)
              .filter_by(project_id=claims["project_id"]).all()):
        dsn = get_dsn(d)
        try:
            config = masked_config(d.kind, dsn)
        except Exception:
            config = {}
        rows.append({"id": d.id, "name": d.name, "kind": d.kind,
                     "dsn": mask_dsn(dsn), "config": config,
                     "capabilities": capabilities(d.kind)})
    return rows


@router.put("/datasources/{datasource_id}")
def update(datasource_id: int, body: DsUpdateIn,
           s: Session = Depends(get_session),
           claims: dict = Depends(require_editor)):
    try:
        ds = s.get(Datasource, datasource_id)
        if not ds or ds.project_id != claims["project_id"]:
            raise ValueError("datasource not found")
        dsn = None
        if body.config is not None:
            dsn = _build(ds.kind, None, body.config, current=get_dsn(ds))
        elif body.dsn:
            dsn = _build(ds.kind, body.dsn, None)
        ds = update_datasource(s, claims["project_id"], datasource_id,
                               body.name, dsn)
    except ValueError as e:
        raise HTTPException(400, str(e))
    write_audit(s, claims["sub"], "update_datasource", str(ds.id),
                {"name": ds.name, "dsn_changed": bool(body.dsn)})
    return {"id": ds.id, "name": ds.name,
            "dsn": mask_dsn(get_dsn(ds))}


@router.delete("/datasources/{datasource_id}", status_code=204)
def remove(datasource_id: int, force: bool = False,
           s: Session = Depends(get_session),
           claims: dict = Depends(require_editor)):
    try:
        blockers = delete_datasource(s, claims["project_id"], datasource_id,
                                     force)
    except DatasourceInUse as e:
        parts = ["%d %s" % (v, k) for k, v in e.blockers.items() if v]
        raise HTTPException(
            409, "datasource is in use: %s; pass force=true to delete"
            % ", ".join(parts))
    except ValueError as e:
        raise HTTPException(404, str(e))
    write_audit(s, claims["sub"], "delete_datasource", str(datasource_id),
                blockers)
    return None


@router.post("/datasources/{datasource_id}/test")
def test(datasource_id: int, s: Session = Depends(get_session),
         claims: dict = Depends(require_user)):
    ds = s.get(Datasource, datasource_id)
    if not ds or ds.project_id != claims["project_id"]:
        raise HTTPException(404, "datasource not found")
    return check_connection(get_dsn(ds), kind=ds.kind)
