from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.services.auth import require_user
from odf.services.catalog import (create_tag, dataset_detail, impact,
                                  lineage, list_datasets, list_tags,
                                  search_catalog, tag_dataset)

router = APIRouter()


class TagIn(BaseModel):
    project_id: int = 1
    name: str


class TagDatasetIn(BaseModel):
    dataset_id: int
    tag_id: int


@router.get("/catalog/datasets")
def datasets(s: Session = Depends(get_session),
             claims: dict = Depends(require_user)):
    return list_datasets(s, claims["project_id"])


@router.get("/catalog/datasets/{dataset_id}")
def detail(dataset_id: int, s: Session = Depends(get_session),
           claims: dict = Depends(require_user)):
    d = dataset_detail(s, dataset_id, claims["project_id"])
    if not d:
        raise HTTPException(404, "dataset not found")
    return d


@router.get("/catalog/search")
def search(q: str, limit: int = 50, s: Session = Depends(get_session),
           claims: dict = Depends(require_user)):
    return search_catalog(s, claims["project_id"], q, limit)


@router.get("/catalog/lineage")
def lineage_view(s: Session = Depends(get_session),
                 claims: dict = Depends(require_user)):
    return lineage(s, claims["project_id"])


@router.get("/catalog/impact")
def impact_view(ref: str, depth: int = 5,
                s: Session = Depends(get_session),
                claims: dict = Depends(require_user)):
    return impact(s, claims["project_id"], ref, depth)


@router.get("/catalog/tags")
def tags(s: Session = Depends(get_session),
         claims: dict = Depends(require_user)):
    return [{"id": t.id, "name": t.name}
            for t in list_tags(s, claims["project_id"])]


@router.post("/catalog/tags")
def create_tag_(body: TagIn, s: Session = Depends(get_session),
                claims: dict = Depends(require_user)):
    if body.project_id != claims["project_id"]:
        raise HTTPException(403, "project mismatch")
    t = create_tag(s, body.project_id, body.name)
    return {"id": t.id, "name": t.name}


@router.post("/catalog/tags/attach")
def attach(body: TagDatasetIn, s: Session = Depends(get_session),
           claims: dict = Depends(require_user)):
    try:
        row = tag_dataset(s, body.dataset_id, body.tag_id,
                          claims["project_id"])
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"id": row.id}
