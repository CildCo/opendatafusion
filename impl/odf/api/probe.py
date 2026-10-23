import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/livez")
def livez():
    return {"status": "ok"}


@router.get("/readyz")
def readyz():
    from odf.db import engine
    try:
        with engine.connect() as c:
            c.execute(text("select 1"))
    except Exception:
        logger.exception("database readiness check failed")
        return JSONResponse(status_code=503,
                            content={"status": "degraded",
                                     "database": "unavailable"})
    return {"status": "ok", "database": "ok"}


@router.get("/healthz")
def healthz():
    return readyz()
