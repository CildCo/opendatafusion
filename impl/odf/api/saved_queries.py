from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.models import Datasource, SavedQuery
from odf.services.auth import require_user

router = APIRouter()


class SavedQueryIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    tab: str = "single"
    datasource_id: int | None = None
    sql: str = ""
    sources: list[dict] = []
    limit: int = 1000


def _out(row):
    return {"id": row.id, "name": row.name, "tab": row.tab,
            "datasource_id": row.datasource_id, "sql": row.sql_text,
            "sources": row.sources_json or [], "limit": row.row_limit,
            "created_at": row.created_at.isoformat()}


@router.get("/saved-queries")
def list_(s: Session = Depends(get_session),
          claims: dict = Depends(require_user)):
    rows = (s.query(SavedQuery)
            .filter_by(project_id=claims["project_id"],
                       owner_id=int(claims["sub"]))
            .order_by(SavedQuery.id.desc()).limit(100).all())
    return {"items": [_out(row) for row in rows], "total": len(rows)}


@router.post("/saved-queries")
def create(body: SavedQueryIn, s: Session = Depends(get_session),
           claims: dict = Depends(require_user)):
    if body.tab not in ("single", "federated"):
        raise HTTPException(400, "tab must be single or federated")
    if body.datasource_id is not None:
        ds = s.get(Datasource, body.datasource_id)
        if not ds or ds.project_id != claims["project_id"]:
            raise HTTPException(404, "datasource not found")
    limit = max(1, min(int(body.limit or 1000), 10000))
    row = SavedQuery(project_id=claims["project_id"],
                     owner_id=int(claims["sub"]),
                     name=body.name.strip(), tab=body.tab,
                     datasource_id=body.datasource_id,
                     sql_text=body.sql or "",
                     sources_json=body.sources or [], row_limit=limit)
    s.add(row)
    s.commit()
    s.refresh(row)
    return _out(row)


@router.delete("/saved-queries/{query_id}", status_code=204)
def remove(query_id: int, s: Session = Depends(get_session),
           claims: dict = Depends(require_user)):
    row = s.get(SavedQuery, query_id)
    if not row or row.project_id != claims["project_id"] or \
            row.owner_id != int(claims["sub"]):
        raise HTTPException(404, "saved query not found")
    s.delete(row)
    s.commit()
    return None
