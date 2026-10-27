import hashlib
import re
import secrets

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.engine.profiles import profiles as engine_profiles
from odf.engine.profiles import spark_default_image
from odf.services.audit import write_audit
from odf.services.auth import require_approver, require_editor, require_user
from odf.services.engine_jobs import (cancel_job, get_job, job_out, list_jobs,
                                      savepoint_job, submit_job)
from odf.settings import get_settings

router = APIRouter()

_NAME = r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$"
_READ_ONLY = re.compile(r"(?is)^\s*(select|with|show|describe|explain|use)\b")
MAX_STATEMENT = 100_000


class JobIn(BaseModel):
    engine: str = Field(pattern=r"^(spark|flink)$")
    name: str = Field(min_length=1, max_length=63, pattern=_NAME)
    spec: dict = {}
    asset_id: int | None = None


class SqlIn(BaseModel):
    statement: str = Field(min_length=1, max_length=MAX_STATEMENT)
    properties: dict[str, str] = {}


class SavepointIn(BaseModel):
    target_directory: str = Field(default="", max_length=1024)
    stop: bool = False


def _error(error: ValueError) -> HTTPException:
    message = str(error)
    if "not configured" in message:
        return HTTPException(503, message)
    if "already exists" in message:
        return HTTPException(409, message)
    if "does not belong" in message:
        return HTTPException(404, message)
    return HTTPException(400, message)


def _check_spark(spec: dict) -> None:
    settings = get_settings()
    allowed = [item.strip() for item in
               settings.k8s_allowed_images.split(",") if item.strip()]
    image = spec.get("image") or spark_default_image(settings)
    if allowed and not any(image.startswith(prefix) for prefix in allowed):
        raise HTTPException(400, "image is not allowed")
    if not (spec.get("main_application_file") or "").startswith(
            ("local://", "s3://", "s3a://")):
        raise HTTPException(
            400, "main application file must use local:// or s3://")


def _check_flink(spec: dict) -> None:
    if not (spec.get("statement") or "").strip():
        raise HTTPException(400, "flink job requires a statement")


@router.get("/engine/profiles")
def engine_profiles_view(claims: dict = Depends(require_user)):
    return engine_profiles(get_settings())


@router.post("/engine/jobs", status_code=201)
def create_job(body: JobIn, session: Session = Depends(get_session),
               claims: dict = Depends(require_editor)):
    if body.engine == "spark":
        _check_spark(body.spec)
    else:
        _check_flink(body.spec)
    try:
        job = submit_job(session, claims["project_id"], body.engine,
                         body.name, body.spec, claims["sub"],
                         asset_id=body.asset_id)
    except ValueError as error:
        raise _error(error)
    return job_out(job)


@router.get("/engine/jobs")
def list_engine_jobs(status: str | None = Query(default=None),
                     engine: str | None = Query(default=None),
                     limit: int = Query(default=100, ge=1, le=500),
                     session: Session = Depends(get_session),
                     claims: dict = Depends(require_user)):
    rows = list_jobs(session, claims["project_id"], status, engine, limit)
    return [job_out(job) for job in rows]


@router.get("/engine/jobs/{job_id}")
def engine_job(job_id: int, session: Session = Depends(get_session),
               claims: dict = Depends(require_user)):
    job = get_job(session, claims["project_id"], job_id)
    if not job:
        raise HTTPException(404, "engine job not found")
    return job_out(job)


@router.delete("/engine/jobs/{job_id}")
def cancel_engine_job(job_id: int, session: Session = Depends(get_session),
                      claims: dict = Depends(require_editor)):
    job = get_job(session, claims["project_id"], job_id)
    if not job:
        raise HTTPException(404, "engine job not found")
    try:
        cancel_job(session, job, claims["sub"])
    except ValueError as error:
        raise _error(error)
    except Exception:
        raise HTTPException(502, "engine cancel failed")
    return job_out(job)


@router.post("/engine/jobs/{job_id}/savepoint")
def savepoint_engine_job(job_id: int, body: SavepointIn,
                         session: Session = Depends(get_session),
                         claims: dict = Depends(require_editor)):
    job = get_job(session, claims["project_id"], job_id)
    if not job:
        raise HTTPException(404, "engine job not found")
    try:
        return savepoint_job(session, job, body.target_directory, body.stop,
                             claims["sub"])
    except ValueError as error:
        raise _error(error)
    except Exception:
        raise HTTPException(502, "flink savepoint failed")


@router.post("/engine/sql")
def execute_sql(body: SqlIn, session: Session = Depends(get_session),
                claims: dict = Depends(require_approver)):
    statement = body.statement.strip()
    read_only = bool(_READ_ONLY.match(statement))
    if not read_only and not get_settings().engine_sql_write_enabled:
        raise HTTPException(403, "write statements are disabled")
    name = "sql-%s" % secrets.token_hex(4)
    spec = {"statement": statement, "properties": body.properties,
            "attached": True}
    try:
        job = submit_job(session, claims["project_id"], "flink", name, spec,
                         claims["sub"])
    except ValueError as error:
        raise _error(error)
    write_audit(session, claims["sub"], "engine_sql", job.name, {
        "sql_sha256": hashlib.sha256(statement.encode("utf-8")).hexdigest(),
        "read_only": read_only,
        "statement_preview": statement[:300],
    })
    return {"job_id": job.id, "name": job.name, "result": job.result_json}
