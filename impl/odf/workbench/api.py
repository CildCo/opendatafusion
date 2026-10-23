from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.services.auth import claims_role, require_editor
from odf.workbench.federation import run_federated
from odf.workbench.service import run_query

router = APIRouter()


class FedSource(BaseModel):
    alias: str
    datasource_id: int
    table: str


class FedIn(BaseModel):
    sources: list[FedSource]
    sql: str
    limit: int = Field(1000, ge=1, le=10000)


class QueryIn(BaseModel):
    datasource_id: int
    sql: str
    limit: int = Field(1000, ge=1, le=10000)


@router.post("/workbench/query")
def query(body: QueryIn, s: Session = Depends(get_session),
          claims: dict = Depends(require_editor)):
    try:
        return run_query(s, claims["project_id"], body.datasource_id,
                         body.sql, body.limit, claims["sub"],
                         role=claims_role(s, claims))
    except ValueError as e:
        raise HTTPException(404 if "not found" in str(e) else 400, str(e))


@router.post("/workbench/federated")
def federated(body: FedIn, s: Session = Depends(get_session),
              claims: dict = Depends(require_editor)):
    from odf.models import Datasource
    from odf.services.masking import datasource_has_policies
    if claims_role(s, claims) != "admin":
        for src in body.sources:
            ds = s.get(Datasource, src.datasource_id)
            if ds and ds.project_id == claims["project_id"] and                     datasource_has_policies(s, ds.id):
                raise HTTPException(
                    400, "federation is disabled for governed datasources")
    try:
        return run_federated(
            s, claims["project_id"],
            [x.model_dump() for x in body.sources],
            body.sql, body.limit, claims["sub"])
    except ValueError as e:
        raise HTTPException(404 if "datasource not found" in str(e) else 400,
                            str(e))
