from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.services.audit import write_audit
from odf.services.auth import require_editor, require_user
from odf.services.templates import apply_template, list_templates

router = APIRouter()


class ApplyIn(BaseModel):
    name: str = ""
    datasource_id: int | None = None
    table: str = ""
    schema_name: str = ""
    target_datasource_id: int | None = None
    target_table: str = ""
    pk: str = "id"


@router.get("/templates")
def templates(type: str | None = None,
              claims: dict = Depends(require_user)):
    return {"items": list_templates(type)}


@router.post("/templates/{template_id}/apply")
def apply(template_id: str, body: ApplyIn,
          s: Session = Depends(get_session),
          claims: dict = Depends(require_editor)):
    try:
        result = apply_template(s, claims["project_id"], template_id,
                                body.model_dump(), claims["sub"])
    except ValueError as error:
        raise HTTPException(400, str(error))
    write_audit(s, claims["sub"], "apply_template", template_id,
                {"asset_id": result["id"], "type": result["type"]})
    return result
