from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.services.auth import require_admin
from odf.services.ratelimit import stats

router = APIRouter()


@router.get("/api-stats")
def api_stats(days: int = 7, s: Session = Depends(get_session),
              claims: dict = Depends(require_admin)):
    return stats(s, claims["project_id"], days)
