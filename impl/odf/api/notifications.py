from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.services.auth import require_user
from odf.services.notifications import (list_for, mark_all_read,
                                        mark_read)

router = APIRouter()


@router.get("/notifications")
def list_(limit: int = 50, unread: bool = False,
          s: Session = Depends(get_session),
          claims: dict = Depends(require_user)):
    return list_for(s, claims["project_id"], int(claims["sub"]),
                    limit=limit, unread_only=unread)


@router.post("/notifications/{notification_id}/read")
def read(notification_id: int, s: Session = Depends(get_session),
         claims: dict = Depends(require_user)):
    try:
        mark_read(s, claims["project_id"], int(claims["sub"]),
                  notification_id)
    except ValueError as error:
        raise HTTPException(404, str(error))
    return {"ok": True}


@router.post("/notifications/read-all")
def read_all(s: Session = Depends(get_session),
             claims: dict = Depends(require_user)):
    return {"marked": mark_all_read(s, claims["project_id"],
                                    int(claims["sub"]))}
