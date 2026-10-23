from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.models import AuditLog
from odf.services.auth import require_admin

router = APIRouter()


@router.get("/audit")
def audit(limit: int = 100, s: Session = Depends(get_session),
          claims: dict = Depends(require_admin)):
    rows = (s.query(AuditLog).order_by(AuditLog.id.desc())
            .limit(min(limit, 500)).all())
    return [{"id": r.id, "actor": r.actor, "action": r.action,
             "target": r.target, "detail": r.detail_json,
             "at": r.at.isoformat()} for r in rows]
