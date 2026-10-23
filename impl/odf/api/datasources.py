from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.models import Datasource
from odf.services.audit import write_audit
from odf.services.auth import require_editor, require_user
from odf.services.datasource import (create_datasource, get_dsn, mask_dsn,
                                     test_connection)

router = APIRouter()


class DsIn(BaseModel):
    name: str
    dsn: str
    kind: str = "postgres"
    project_id: int | None = None


@router.post("/datasources")
def create(body: DsIn, s: Session = Depends(get_session),
           claims: dict = Depends(require_editor)):
    if body.project_id is not None and             body.project_id != claims["project_id"]:
        raise HTTPException(403, "project mismatch")
    try:
        ds = create_datasource(s, claims["project_id"], body.name, body.dsn,
                               body.kind)
    except ValueError as e:
        raise HTTPException(400, str(e))
    write_audit(s, claims["sub"], "create_datasource", str(ds.id),
                {"name": body.name, "kind": body.kind})
    return {"id": ds.id, "name": ds.name, "dsn": mask_dsn(get_dsn(ds))}


@router.get("/datasources")
def list_ds(s: Session = Depends(get_session),
            claims: dict = Depends(require_user)):
    return [{"id": d.id, "name": d.name, "kind": d.kind,
             "dsn": mask_dsn(get_dsn(d))}
            for d in s.query(Datasource)
            .filter_by(project_id=claims["project_id"]).all()]


@router.post("/datasources/{datasource_id}/test")
def test(datasource_id: int, s: Session = Depends(get_session),
         claims: dict = Depends(require_user)):
    ds = s.get(Datasource, datasource_id)
    if not ds or ds.project_id != claims["project_id"]:
        raise HTTPException(404, "datasource not found")
    if ds.kind == "file":
        from odf import filesource
        try:
            filesource.describe(filesource.path_for(ds))
            return {"ok": True}
        except Exception:
            return {"ok": False}
    return {"ok": test_connection(get_dsn(ds), kind=ds.kind)}
