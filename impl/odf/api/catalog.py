from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.models import User
from odf.services.auth import claims_role, require_editor, require_user
from odf.services.catalog import (add_comment, create_tag, dataset_detail,
                                  dataset_history, dataset_profile,
                                  dataset_sample, impact, lineage,
                                  link_column_term, list_comments,
                                  list_datasets, list_tags, search_catalog,
                                  set_comment_status, tag_dataset,
                                  term_columns, unlink_column_term,
                                  untag_dataset)

router = APIRouter()


class TagIn(BaseModel):
    project_id: int = 1
    name: str


class TagDatasetIn(BaseModel):
    dataset_id: int
    tag_id: int


class CommentIn(BaseModel):
    body: str


class CommentStatusIn(BaseModel):
    status: str


class TermLinkIn(BaseModel):
    term_id: int


@router.get("/catalog/datasets")
def datasets(s: Session = Depends(get_session),
             claims: dict = Depends(require_user)):
    return list_datasets(s, claims["project_id"])


@router.get("/catalog/export")
def export(s: Session = Depends(get_session),
           claims: dict = Depends(require_user)):
    import json
    from fastapi import Response
    from odf.lineage.catalog_sync import export_project
    from odf.services.audit import write_audit
    payload = export_project(s, claims["project_id"])
    write_audit(s, claims["sub"], "export_catalog", str(claims["project_id"]),
                {"projects": 1})
    return Response(
        content=json.dumps(payload, ensure_ascii=False, default=str),
        media_type="application/json",
        headers={"Content-Disposition":
                 "attachment; filename=odf-catalog.json"})


@router.get("/catalog/datasets/{dataset_id}")
def detail(dataset_id: int, s: Session = Depends(get_session),
           claims: dict = Depends(require_user)):
    d = dataset_detail(s, dataset_id, claims["project_id"])
    if not d:
        raise HTTPException(404, "dataset not found")
    return d


@router.get("/catalog/datasets/{dataset_id}/sample")
def sample(dataset_id: int, limit: int = 20,
           s: Session = Depends(get_session),
           claims: dict = Depends(require_user)):
    try:
        return dataset_sample(s, claims["project_id"], dataset_id, limit,
                             role=claims_role(s, claims),
                             actor=claims["sub"])
    except ValueError as e:
        code = 404 if str(e) == "dataset not found" else 400
        raise HTTPException(code, str(e))


@router.post("/catalog/datasets/{dataset_id}/pii-scan")
def pii_scan(dataset_id: int, apply: bool = False,
             s: Session = Depends(get_session),
             claims: dict = Depends(require_editor)):
    from odf.services.audit import write_audit
    from odf.services.pii import apply as apply_policies
    from odf.services.pii import scan
    try:
        result = (apply_policies(s, claims["project_id"], dataset_id,
                                 claims["sub"])
                  if apply else scan(s, claims["project_id"], dataset_id))
    except ValueError as e:
        raise HTTPException(404 if str(e) == "dataset not found" else 400,
                            str(e))
    write_audit(s, claims["sub"], "scan_pii", str(dataset_id),
                {"findings": len(result["findings"]),
                 "applied": result.get("applied", 0)})
    return result


@router.get("/catalog/datasets/{dataset_id}/profile")
def profile(dataset_id: int, sample: int = 50000,
            s: Session = Depends(get_session),
            claims: dict = Depends(require_user)):
    try:
        return dataset_profile(s, claims["project_id"], dataset_id, sample,
                               role=claims_role(s, claims),
                               actor=claims["sub"])
    except ValueError as e:
        code = 404 if str(e) == "dataset not found" else 400
        raise HTTPException(code, str(e))


@router.get("/catalog/datasets/{dataset_id}/history")
def history(dataset_id: int, limit: int = 50,
            s: Session = Depends(get_session),
            claims: dict = Depends(require_user)):
    try:
        return dataset_history(s, claims["project_id"], dataset_id, limit)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/catalog/datasets/{dataset_id}/comments")
def comments(dataset_id: int, status: str | None = None, limit: int = 100,
             s: Session = Depends(get_session),
             claims: dict = Depends(require_user)):
    try:
        return list_comments(s, claims["project_id"], dataset_id, status,
                             limit)
    except ValueError as e:
        raise HTTPException(404 if str(e) == "dataset not found" else 400,
                            str(e))


@router.post("/catalog/datasets/{dataset_id}/comments", status_code=201)
def add_comment_(dataset_id: int, body: CommentIn,
                 s: Session = Depends(get_session),
                 claims: dict = Depends(require_user)):
    user = s.get(User, int(claims["sub"]))
    actor = user.username if user else claims["sub"]
    try:
        return add_comment(s, claims["project_id"], dataset_id,
                           actor, body.body)
    except ValueError as e:
        raise HTTPException(404 if str(e) == "dataset not found" else 400,
                            str(e))


@router.patch("/catalog/comments/{comment_id}")
def update_comment(comment_id: int, body: CommentStatusIn,
                   s: Session = Depends(get_session),
                   claims: dict = Depends(require_user)):
    user = s.get(User, int(claims["sub"]))
    actor = user.username if user else claims["sub"]
    try:
        return set_comment_status(s, claims["project_id"], comment_id,
                                  actor, body.status)
    except ValueError as e:
        raise HTTPException(404 if "not found" in str(e) else 400, str(e))


@router.post("/catalog/datasets/{dataset_id}/columns/{column}/terms",
             status_code=201)
def link_term(dataset_id: int, column: str, body: TermLinkIn,
              s: Session = Depends(get_session),
              claims: dict = Depends(require_editor)):
    try:
        return link_column_term(s, claims["project_id"], dataset_id, column,
                                body.term_id, claims["sub"])
    except ValueError as e:
        raise HTTPException(404 if "not found" in str(e) else 400, str(e))


@router.delete("/catalog/datasets/{dataset_id}/columns/{column}/terms/{term_id}")
def unlink_term(dataset_id: int, column: str, term_id: int,
                s: Session = Depends(get_session),
                claims: dict = Depends(require_editor)):
    try:
        return {"removed": unlink_column_term(
            s, claims["project_id"], dataset_id, column, term_id)}
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/catalog/terms/{term_id}/columns")
def term_columns_(term_id: int, s: Session = Depends(get_session),
                  claims: dict = Depends(require_user)):
    try:
        return term_columns(s, claims["project_id"], term_id)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/catalog/search")
def search(q: str, limit: int = 50, s: Session = Depends(get_session),
           claims: dict = Depends(require_user)):
    return search_catalog(s, claims["project_id"], q, limit)


@router.get("/catalog/lineage")
def lineage_view(ref: str | None = None, depth: int = 5,
                 direction: str = "both",
                 s: Session = Depends(get_session),
                 claims: dict = Depends(require_user)):
    return lineage(s, claims["project_id"], ref, depth, direction)


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


@router.post("/catalog/tags/detach")
def detach(body: TagDatasetIn, s: Session = Depends(get_session),
           claims: dict = Depends(require_user)):
    try:
        removed = untag_dataset(s, body.dataset_id, body.tag_id,
                                claims["project_id"])
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"removed": removed}
