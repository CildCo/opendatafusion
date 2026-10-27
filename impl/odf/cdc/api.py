import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from odf.cdc import service
from odf.db import get_session
from odf.services.auth import require_editor, require_user

router = APIRouter()


class SourceIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    config: dict = {}
    password: str = ""


def _error(error: Exception) -> HTTPException:
    message = str(error)
    if "not configured" in message:
        return HTTPException(503, message)
    if "already exists" in message:
        return HTTPException(409, message)
    return HTTPException(400, message)


def _source(session, project_id, source_id):
    source = service.get_source(session, project_id, source_id)
    if not source:
        raise HTTPException(404, "cdc source not found")
    return source


@router.post("/cdc/sources", status_code=201)
def create_source(body: SourceIn, session: Session = Depends(get_session),
                  claims: dict = Depends(require_editor)):
    try:
        source = service.create_source(
            session, claims["project_id"], body.name, body.config,
            body.password, claims["sub"])
    except ValueError as error:
        raise _error(error)
    except httpx.HTTPStatusError:
        raise HTTPException(502, "debezium rejected the connector")
    except httpx.HTTPError:
        raise HTTPException(502, "debezium is unreachable")
    return service.source_out(source)


@router.get("/cdc/sources")
def list_sources(session: Session = Depends(get_session),
                 claims: dict = Depends(require_user)):
    return [service.source_out(row)
            for row in service.list_sources(session, claims["project_id"])]


@router.get("/cdc/sources/{source_id}")
def get_source(source_id: int, session: Session = Depends(get_session),
               claims: dict = Depends(require_user)):
    return service.source_out(_source(session, claims["project_id"],
                                      source_id))


@router.post("/cdc/sources/{source_id}/status")
def refresh_source(source_id: int, session: Session = Depends(get_session),
                   claims: dict = Depends(require_user)):
    source = _source(session, claims["project_id"], source_id)
    try:
        return service.refresh_status(session, source)
    except ValueError as error:
        raise _error(error)
    except httpx.HTTPError:
        raise HTTPException(502, "debezium is unreachable")


@router.post("/cdc/sources/{source_id}/pause")
def pause_source(source_id: int, session: Session = Depends(get_session),
                 claims: dict = Depends(require_editor)):
    source = _source(session, claims["project_id"], source_id)
    try:
        service.pause_source(session, source, claims["sub"])
    except ValueError as error:
        raise _error(error)
    except httpx.HTTPStatusError:
        raise HTTPException(502, "debezium rejected the request")
    except httpx.HTTPError:
        raise HTTPException(502, "debezium is unreachable")
    return service.source_out(source)


@router.post("/cdc/sources/{source_id}/resume")
def resume_source(source_id: int, session: Session = Depends(get_session),
                  claims: dict = Depends(require_editor)):
    source = _source(session, claims["project_id"], source_id)
    try:
        service.resume_source(session, source, claims["sub"])
    except ValueError as error:
        raise _error(error)
    except httpx.HTTPStatusError:
        raise HTTPException(502, "debezium rejected the request")
    except httpx.HTTPError:
        raise HTTPException(502, "debezium is unreachable")
    return service.source_out(source)


@router.delete("/cdc/sources/{source_id}", status_code=204)
def delete_source(source_id: int, session: Session = Depends(get_session),
                  claims: dict = Depends(require_editor)):
    source = _source(session, claims["project_id"], source_id)
    try:
        service.delete_source(session, source, claims["sub"])
    except ValueError as error:
        raise _error(error)
    except httpx.HTTPStatusError:
        raise HTTPException(502, "debezium rejected the request")
    except httpx.HTTPError:
        raise HTTPException(502, "debezium is unreachable")
    return None
