from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.services.auth import require_editor, require_user
from odf.services.dependencies import (add_dependency, delete_dependency,
                                       list_dependencies)

router = APIRouter()


class DependencyIn(BaseModel):
    downstream_type: str
    downstream_id: int
    upstream_type: str
    upstream_id: int


@router.get("/dependencies")
def list_(s: Session = Depends(get_session),
          claims: dict = Depends(require_user)):
    return list_dependencies(s, claims["project_id"])


@router.post("/dependencies", status_code=201)
def create(body: DependencyIn, s: Session = Depends(get_session),
           claims: dict = Depends(require_editor)):
    try:
        row = add_dependency(s, claims["project_id"],
                             body.downstream_type, body.downstream_id,
                             body.upstream_type, body.upstream_id)
    except ValueError as error:
        raise HTTPException(400, str(error))
    return {"id": row.id}


@router.delete("/dependencies/{dependency_id}", status_code=204)
def remove(dependency_id: int, s: Session = Depends(get_session),
           claims: dict = Depends(require_editor)):
    try:
        delete_dependency(s, claims["project_id"], dependency_id)
    except ValueError as error:
        raise HTTPException(404, str(error))
    return None
