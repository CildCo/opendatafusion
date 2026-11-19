from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.services.audit import list_audit
from odf.services.auth import require_admin

router = APIRouter()


@router.get("/audit")
def audit(limit: int = 100, s: Session = Depends(get_session),
          claims: dict = Depends(require_admin)):
    return list_audit(s, limit)
