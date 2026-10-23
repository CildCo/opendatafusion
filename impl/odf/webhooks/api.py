from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.services.auth import require_editor, require_user
from odf.webhooks import service

router = APIRouter()


class WebhookIn(BaseModel):
    name: str
    url: str
    events: list[str] = []
    enabled: bool = True
    secret: str | None = None


class WebhookUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    events: list[str] | None = None
    enabled: bool | None = None
    rotate_secret: bool = False


def _value(e):
    msg = str(e)
    return HTTPException(404 if "not found" in msg else 400, msg)


@router.get("/webhooks/events")
def events(claims: dict = Depends(require_user)):
    return sorted(service.EVENTS - {"webhook.test"})


@router.get("/webhooks")
def list_(s: Session = Depends(get_session),
          claims: dict = Depends(require_user)):
    return service.list_subscriptions(s, claims["project_id"])


@router.post("/webhooks")
def create(body: WebhookIn, s: Session = Depends(get_session),
           claims: dict = Depends(require_editor)):
    try:
        return service.create_subscription(
            s, claims["project_id"], body.name, body.url, body.events,
            body.enabled, claims["sub"], body.secret)
    except ValueError as e:
        raise _value(e)


@router.put("/webhooks/{webhook_id}")
def update(webhook_id: int, body: WebhookUpdate,
           s: Session = Depends(get_session),
           claims: dict = Depends(require_editor)):
    try:
        return service.update_subscription(
            s, claims["project_id"], webhook_id, body.model_dump(
                exclude_none=True), claims["sub"])
    except ValueError as e:
        raise _value(e)


@router.delete("/webhooks/{webhook_id}")
def delete(webhook_id: int, s: Session = Depends(get_session),
           claims: dict = Depends(require_editor)):
    try:
        service.delete_subscription(s, claims["project_id"], webhook_id,
                                    claims["sub"])
        return {"deleted": True}
    except ValueError as e:
        raise _value(e)


@router.post("/webhooks/{webhook_id}/test")
def test(webhook_id: int, s: Session = Depends(get_session),
         claims: dict = Depends(require_editor)):
    try:
        return service.queue_test(s, claims["project_id"], webhook_id,
                                  claims["sub"])
    except ValueError as e:
        raise _value(e)


@router.get("/webhooks/{webhook_id}/deliveries")
def deliveries(webhook_id: int, s: Session = Depends(get_session),
               claims: dict = Depends(require_user)):
    try:
        return service.list_deliveries(s, claims["project_id"], webhook_id)
    except ValueError as e:
        raise _value(e)
