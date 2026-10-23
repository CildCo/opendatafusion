from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.services.audit import write_audit
from odf.services.auth import require_editor, require_user
from odf.models import Datasource
from odf.services.metadata import list_tables, sync_datasource

router = APIRouter()


def _ds(s, datasource_id, claims):
    ds = s.get(Datasource, datasource_id)
    if not ds or ds.project_id != claims["project_id"]:
        raise HTTPException(404, "datasource not found")
    return ds


@router.get("/datasources/{datasource_id}/tables")
def tables(datasource_id: int, s: Session = Depends(get_session),
           claims: dict = Depends(require_user)):
    _ds(s, datasource_id, claims)
    return list_tables(s, datasource_id)


@router.post("/datasources/{datasource_id}/sync")
def sync(datasource_id: int, s: Session = Depends(get_session),
         claims: dict = Depends(require_editor)):
    _ds(s, datasource_id, claims)
    try:
        tables = sync_datasource(s, datasource_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    write_audit(s, claims["sub"], "sync_metadata", str(datasource_id),
                {"tables": tables})
    return {"tables": tables}
