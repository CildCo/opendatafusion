from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.services.audit import write_audit
from odf.services.auth import require_editor, require_user
from odf.services.governance import (asset_governance, asset_usage,
                                     create_domain, create_term,
                                     delete_domain, delete_term,
                                     list_domains, list_terms,
                                     table_governance, update_asset_governance,
                                     update_domain, update_table_governance,
                                     update_term)

router = APIRouter()


class DomainIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str = ""
    owner: str = ""


class DomainPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    owner: str | None = None


class TermIn(BaseModel):
    term: str = Field(min_length=1, max_length=128)
    definition: str = ""
    domain_id: int | None = None
    owner: str = ""


class TermPatch(BaseModel):
    term: str | None = None
    definition: str | None = None
    domain_id: int | None = None
    owner: str | None = None


class AssetGovernanceIn(BaseModel):
    domain_id: int | None = None
    contract: dict | None = None


class TableGovernanceIn(BaseModel):
    domain_id: int | None = None


def _domain(row):
    return {"id": row.id, "name": row.name,
            "description": row.description, "owner": row.owner,
            "created_at": row.created_at.isoformat()}


def _term(session, row):
    from odf.models import Domain
    domain = session.get(Domain, row.domain_id) if row.domain_id else None
    return {"id": row.id, "term": row.term,
            "definition": row.definition, "owner": row.owner,
            "domain_id": row.domain_id,
            "domain_name": domain.name if domain else None,
            "created_at": row.created_at.isoformat()}


@router.get("/governance/domains")
def domains(s: Session = Depends(get_session),
            claims: dict = Depends(require_user)):
    return {"items": [_domain(row) for row in
                      list_domains(s, claims["project_id"])]}


@router.post("/governance/domains")
def add_domain(body: DomainIn, s: Session = Depends(get_session),
               claims: dict = Depends(require_editor)):
    try:
        row = create_domain(s, claims["project_id"], body.name,
                            body.description, body.owner)
    except ValueError as error:
        raise HTTPException(400, str(error))
    write_audit(s, claims["sub"], "create_domain", str(row.id),
                {"name": row.name})
    return _domain(row)


@router.put("/governance/domains/{domain_id}")
def edit_domain(domain_id: int, body: DomainPatch,
                s: Session = Depends(get_session),
                claims: dict = Depends(require_editor)):
    try:
        row = update_domain(s, claims["project_id"], domain_id,
                            body.name, body.description, body.owner)
    except ValueError as error:
        raise HTTPException(400, str(error))
    write_audit(s, claims["sub"], "update_domain", str(row.id),
                {"name": row.name})
    return _domain(row)


@router.delete("/governance/domains/{domain_id}", status_code=204)
def remove_domain(domain_id: int, s: Session = Depends(get_session),
                  claims: dict = Depends(require_editor)):
    try:
        delete_domain(s, claims["project_id"], domain_id)
    except ValueError as error:
        raise HTTPException(404, str(error))
    write_audit(s, claims["sub"], "delete_domain", str(domain_id), {})
    return None


@router.get("/governance/terms")
def terms(domain_id: int | None = None, s: Session = Depends(get_session),
          claims: dict = Depends(require_user)):
    return {"items": [_term(s, row) for row in
                      list_terms(s, claims["project_id"], domain_id)]}


@router.post("/governance/terms")
def add_term(body: TermIn, s: Session = Depends(get_session),
             claims: dict = Depends(require_editor)):
    try:
        row = create_term(s, claims["project_id"], body.term,
                          body.definition, body.domain_id, body.owner)
    except ValueError as error:
        raise HTTPException(400, str(error))
    write_audit(s, claims["sub"], "create_glossary_term", str(row.id),
                {"term": row.term})
    return _term(s, row)


@router.put("/governance/terms/{term_id}")
def edit_term(term_id: int, body: TermPatch,
              s: Session = Depends(get_session),
              claims: dict = Depends(require_editor)):
    try:
        row = update_term(s, claims["project_id"], term_id, body.term,
                          body.definition, body.domain_id, body.owner)
    except ValueError as error:
        raise HTTPException(400, str(error))
    write_audit(s, claims["sub"], "update_glossary_term", str(row.id),
                {"term": row.term})
    return _term(s, row)


@router.delete("/governance/terms/{term_id}", status_code=204)
def remove_term(term_id: int, s: Session = Depends(get_session),
                claims: dict = Depends(require_editor)):
    try:
        delete_term(s, claims["project_id"], term_id)
    except ValueError as error:
        raise HTTPException(404, str(error))
    write_audit(s, claims["sub"], "delete_glossary_term", str(term_id), {})
    return None


@router.get("/assets/{asset_id}/governance")
def get_asset_governance(asset_id: int, s: Session = Depends(get_session),
                         claims: dict = Depends(require_user)):
    try:
        return asset_governance(s, claims["project_id"], asset_id)
    except ValueError as error:
        raise HTTPException(404, str(error))


@router.put("/assets/{asset_id}/governance")
def set_asset_governance(asset_id: int, body: AssetGovernanceIn,
                         s: Session = Depends(get_session),
                         claims: dict = Depends(require_editor)):
    try:
        out = update_asset_governance(s, claims["project_id"], asset_id,
                                      body.domain_id, body.contract)
    except ValueError as error:
        raise HTTPException(400, str(error))
    write_audit(s, claims["sub"], "update_asset_governance", str(asset_id),
                {"domain_id": body.domain_id})
    return out


@router.get("/assets/{asset_id}/usage")
def get_asset_usage(asset_id: int, s: Session = Depends(get_session),
                    claims: dict = Depends(require_user)):
    try:
        return asset_usage(s, claims["project_id"], asset_id)
    except ValueError as error:
        raise HTTPException(404, str(error))


@router.get("/governance/tables/{dataset_id}")
def get_table_governance(dataset_id: int,
                         s: Session = Depends(get_session),
                         claims: dict = Depends(require_user)):
    try:
        return table_governance(s, claims["project_id"], dataset_id)
    except ValueError as error:
        raise HTTPException(404, str(error))


@router.put("/governance/tables/{dataset_id}")
def set_table_governance(dataset_id: int, body: TableGovernanceIn,
                         s: Session = Depends(get_session),
                         claims: dict = Depends(require_editor)):
    try:
        out = update_table_governance(s, claims["project_id"], dataset_id,
                                      body.domain_id)
    except ValueError as error:
        raise HTTPException(400, str(error))
    write_audit(s, claims["sub"], "update_table_governance",
                str(dataset_id), {"domain_id": body.domain_id})
    return out
