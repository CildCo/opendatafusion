import csv
import io
import json

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.services.audit import list_audit
from odf.services.auth import require_admin

router = APIRouter()


@router.get("/audit")
def audit(limit: int = 100, actor: str | None = None,
          action: str | None = None, q: str | None = None,
          s: Session = Depends(get_session),
          claims: dict = Depends(require_admin)):
    return list_audit(s, limit, actor, action, q)


@router.get("/audit/export")
def export(actor: str | None = None, action: str | None = None,
           q: str | None = None, limit: int = 5000,
           s: Session = Depends(get_session),
           claims: dict = Depends(require_admin)):
    rows = list_audit(s, limit, actor, action, q)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "actor", "action", "target", "at", "detail"])
    for row in rows:
        writer.writerow([row["id"], row["actor"], row["action"],
                         row["target"], row["at"],
                         json.dumps(row["detail"], ensure_ascii=False)])
    return Response(buffer.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition":
                             'attachment; filename="audit.csv"'})
