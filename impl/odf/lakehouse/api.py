import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.lakehouse.maintenance import maintain
from odf.lakehouse.properties import build_spec
from odf.lakehouse.service import (ensure_schema, list_tables, project_schema,
                                   table_columns)
from odf.models import Datasource
from odf.services.auth import require_editor, require_user
from odf.services.engine_jobs import submit_job
from odf.services.metadata import sync_datasource
from odf.settings import get_settings
from odf.trino.client import client_for_datasource

router = APIRouter()
_log = logging.getLogger("odf.lakehouse")


class DsIn(BaseModel):
    datasource_id: int


class MaintainIn(BaseModel):
    datasource_id: int
    schema_name: str | None = None
    tables: list[str] = []
    optimize: bool = True
    expire_snapshots: bool = True
    retention: str = "7d"
    file_size_threshold: str = "128MB"


class PropertiesIn(BaseModel):
    datasource_id: int
    schema_name: str | None = None
    properties: dict[str, str]


def _trino(session, project_id, datasource_id) -> Datasource:
    ds = session.get(Datasource, datasource_id)
    if not ds or ds.project_id != project_id:
        raise HTTPException(404, "datasource not found")
    if ds.kind != "trino":
        raise HTTPException(400, "lakehouse requires a trino datasource")
    return ds


@router.get("/lakehouse/tables")
def lakehouse_tables(datasource_id: int, schema: str | None = None,
                     session: Session = Depends(get_session),
                     claims: dict = Depends(require_user)):
    ds = _trino(session, claims["project_id"], datasource_id)
    client = client_for_datasource(ds)
    target = schema or getattr(client, "schema", "") or project_schema(
        claims["project_id"])
    try:
        tables = list_tables(client, target)
    except ValueError as error:
        _log.warning("lakehouse table listing failed: %s", error)
        raise HTTPException(400, "could not read the lakehouse catalog")
    except Exception:
        raise HTTPException(502, "trino query failed")
    return {"schema": target, "tables": tables}


@router.get("/lakehouse/tables/{table}/columns")
def lakehouse_columns(table: str, datasource_id: int,
                      schema: str | None = None,
                      session: Session = Depends(get_session),
                      claims: dict = Depends(require_user)):
    ds = _trino(session, claims["project_id"], datasource_id)
    client = client_for_datasource(ds)
    target = schema or getattr(client, "schema", "") or project_schema(
        claims["project_id"])
    try:
        return {"schema": target, "table": table,
                "columns": table_columns(client, target, table)}
    except ValueError as error:
        _log.warning("lakehouse column listing failed: %s", error)
        raise HTTPException(400, "could not read the lakehouse catalog")
    except Exception:
        raise HTTPException(502, "trino query failed")


@router.post("/lakehouse/schema")
def lakehouse_schema(body: DsIn, session: Session = Depends(get_session),
                     claims: dict = Depends(require_editor)):
    ds = _trino(session, claims["project_id"], body.datasource_id)
    try:
        schema = ensure_schema(client_for_datasource(ds),
                               claims["project_id"])
    except ValueError as error:
        _log.warning("lakehouse schema creation failed: %s", error)
        raise HTTPException(400, "could not create the lakehouse schema")
    except Exception:
        raise HTTPException(502, "trino query failed")
    return {"datasource_id": ds.id, "schema": schema}


@router.post("/lakehouse/sync")
def lakehouse_sync(body: DsIn, session: Session = Depends(get_session),
                   claims: dict = Depends(require_editor)):
    ds = _trino(session, claims["project_id"], body.datasource_id)
    try:
        count = sync_datasource(session, ds.id)
    except ValueError as error:
        _log.warning("lakehouse metadata sync failed: %s", error)
        raise HTTPException(400, "could not sync lakehouse metadata")
    return {"datasource_id": ds.id, "tables": count}


@router.post("/lakehouse/tables/{table}/properties", status_code=201)
def lakehouse_properties(table: str, body: PropertiesIn,
                         session: Session = Depends(get_session),
                         claims: dict = Depends(require_editor)):
    ds = _trino(session, claims["project_id"], body.datasource_id)
    client = client_for_datasource(ds)
    target = (body.schema_name or getattr(client, "schema", "")
              or project_schema(claims["project_id"]))
    qualified = "%s.%s.%s" % (getattr(client, "catalog", ""), target, table)
    try:
        spec = build_spec(qualified, body.properties, get_settings())
    except ValueError as error:
        _log.warning("lakehouse properties rejected: %s", error)
        raise HTTPException(400, "invalid table properties")
    name = "set-properties-%s" % secrets.token_hex(4)
    try:
        job = submit_job(session, claims["project_id"], "spark", name, spec,
                         claims["sub"])
    except ValueError as error:
        _log.warning("lakehouse properties job failed: %s", error)
        raise HTTPException(503, "spark engine is not available")
    return {"job_id": job.id, "name": job.name, "table": qualified,
            "properties": body.properties}


@router.post("/lakehouse/maintain")
def lakehouse_maintain(body: MaintainIn, session: Session = Depends(get_session),
                       claims: dict = Depends(require_editor)):
    ds = _trino(session, claims["project_id"], body.datasource_id)
    client = client_for_datasource(ds)
    target = (body.schema_name or getattr(client, "schema", "")
              or project_schema(claims["project_id"]))
    try:
        results = maintain(client, target,
                           body.tables or None, body.optimize,
                           body.expire_snapshots, body.retention,
                           body.file_size_threshold)
    except ValueError as error:
        _log.warning("lakehouse maintenance rejected: %s", error)
        raise HTTPException(400, "maintenance request is invalid")
    except Exception:
        raise HTTPException(502, "trino query failed")
    return {"schema": target, "results": results}
