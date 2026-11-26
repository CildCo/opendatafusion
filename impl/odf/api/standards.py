from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.services.audit import write_audit
from odf.services.auth import require_editor, require_user
from odf.services.standards import (compliance, create_standard,
                                    delete_standard, list_mappings,
                                    list_standards, map_standard,
                                    unmap_standard, update_standard)

router = APIRouter()


class StandardIn(BaseModel):
    project_id: int = 1
    code: str
    name: str
    description: str = ""


class MappingIn(BaseModel):
    standard_id: int
    dataset_id: int
    column_name: str


@router.get("/standards")
def standards(project_id: int | None = None,
              s: Session = Depends(get_session),
              claims: dict = Depends(require_user)):
    if project_id is not None and project_id != claims["project_id"]:
        raise HTTPException(403, "project mismatch")
    return [{"id": x.id, "code": x.code, "name": x.name,
             "description": x.description}
            for x in list_standards(s, claims["project_id"])]


@router.post("/standards")
def create(body: StandardIn, s: Session = Depends(get_session),
           claims: dict = Depends(require_editor)):
    if body.project_id != claims["project_id"]:
        raise HTTPException(403, "project mismatch")
    x = create_standard(s, body.project_id, body.code, body.name,
                        body.description)
    write_audit(s, claims["sub"], "create_data_standard", str(x.id),
                {"code": x.code})
    return {"id": x.id, "code": x.code}


@router.put("/standards/{standard_id}")
def update(standard_id: int, body: StandardIn,
           s: Session = Depends(get_session),
           claims: dict = Depends(require_editor)):
    if body.project_id != claims["project_id"]:
        raise HTTPException(403, "project mismatch")
    try:
        x = update_standard(s, claims["project_id"], standard_id,
                            body.code, body.name, body.description)
    except ValueError as error:
        raise HTTPException(404, str(error))
    write_audit(s, claims["sub"], "update_data_standard", str(x.id), {})
    return {"id": x.id, "code": x.code}


@router.delete("/standards/{standard_id}", status_code=204)
def remove(standard_id: int, s: Session = Depends(get_session),
           claims: dict = Depends(require_editor)):
    try:
        delete_standard(s, claims["project_id"], standard_id)
    except ValueError as error:
        raise HTTPException(404, str(error))
    write_audit(s, claims["sub"], "delete_data_standard",
                str(standard_id), {})
    return None


@router.post("/standards/map")
def map_(body: MappingIn, s: Session = Depends(get_session),
         claims: dict = Depends(require_editor)):
    try:
        m = map_standard(s, claims["project_id"], body.standard_id,
                         body.dataset_id, body.column_name)
    except ValueError as error:
        raise HTTPException(404, str(error))
    write_audit(s, claims["sub"], "map_data_standard",
                str(body.dataset_id), {"standard_id": body.standard_id,
                                       "column": body.column_name})
    return {"id": m.id}


@router.delete("/standards/map/{mapping_id}", status_code=204)
def unmap(mapping_id: int, s: Session = Depends(get_session),
          claims: dict = Depends(require_editor)):
    try:
        unmap_standard(s, claims["project_id"], mapping_id)
    except ValueError as error:
        raise HTTPException(404, str(error))
    write_audit(s, claims["sub"], "unmap_data_standard",
                str(mapping_id), {})
    return None


@router.get("/standards/mappings/{dataset_id}")
def mappings(dataset_id: int, s: Session = Depends(get_session),
             claims: dict = Depends(require_user)):
    return [{"id": m.id, "standard_id": m.standard_id,
             "column": m.column_name}
            for m in list_mappings(s, dataset_id)]


@router.get("/standards/compliance/{dataset_id}")
def compliance_(dataset_id: int, s: Session = Depends(get_session),
                claims: dict = Depends(require_user)):
    return compliance(s, dataset_id)
