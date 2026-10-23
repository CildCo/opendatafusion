from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.services.auth import require_user
from odf.services.standards import (compliance, create_standard,
                                    list_mappings, list_standards,
                                    map_standard)

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
def standards(project_id: int = 1, s: Session = Depends(get_session),
              claims: dict = Depends(require_user)):
    return [{"id": x.id, "code": x.code, "name": x.name,
             "description": x.description}
            for x in list_standards(s, project_id)]


@router.post("/standards")
def create(body: StandardIn, s: Session = Depends(get_session),
           claims: dict = Depends(require_user)):
    x = create_standard(s, body.project_id, body.code, body.name,
                        body.description)
    return {"id": x.id, "code": x.code}


@router.post("/standards/map")
def map_(body: MappingIn, s: Session = Depends(get_session),
         claims: dict = Depends(require_user)):
    m = map_standard(s, body.standard_id, body.dataset_id, body.column_name)
    return {"id": m.id}


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
