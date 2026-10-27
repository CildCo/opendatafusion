import re
from datetime import datetime, timezone

import httpx

from odf.models import CdcSource
from odf.services.audit import write_audit
from odf.services.crypto import encrypt_secret
from odf.settings import get_settings

STATES = {"RUNNING": "running", "PAUSED": "paused", "FAILED": "failed",
          "STOPPED": "stopped", "UNASSIGNED": "pending"}
CONNECTOR_CLASS = (
    "io.debezium.connector.postgresql.PostgresConnector")


def _now():
    return datetime.now(timezone.utc)


def _client():
    settings = get_settings()
    if not settings.debezium_url:
        raise ValueError("debezium is not configured")
    return httpx.Client(base_url=settings.debezium_url.rstrip("/"),
                        timeout=15.0)


def connector_name(project_id: int, name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    slug = (slug or "source")[:40].strip("-")
    return "odf-p%d-%s" % (project_id, slug)


def _require(config: dict, key: str) -> str:
    value = str(config.get(key) or "").strip()
    if not value:
        raise ValueError("%s is required" % key)
    return value


def connector_payload(config: dict, password: str | None) -> dict:
    payload = {
        "connector.class": CONNECTOR_CLASS,
        "tasks.max": "1",
        "plugin.name": "pgoutput",
        "database.hostname": _require(config, "host"),
        "database.port": str(config.get("port") or 5432),
        "database.user": _require(config, "user"),
        "database.password": password or "",
        "database.dbname": _require(config, "database"),
        "topic.prefix": str(config.get("topic_prefix") or "odf"),
        "schema.include.list": str(config.get("schema_list") or "public"),
        "publication.autocreate.mode": "filtered",
    }
    tables = str(config.get("table_list") or "").strip()
    if tables:
        payload["table.include.list"] = tables
    return payload


def source_out(source: CdcSource) -> dict:
    return {
        "id": source.id,
        "project_id": source.project_id,
        "name": source.name,
        "connector_name": source.connector_name,
        "status": source.status,
        "config": source.config_json or {},
        "created_by": source.created_by,
        "created_at": source.created_at,
        "updated_at": source.updated_at,
    }


def get_source(session, project_id: int, source_id: int):
    source = session.get(CdcSource, source_id)
    if not source or source.project_id != project_id:
        return None
    return source


def list_sources(session, project_id: int) -> list:
    return (session.query(CdcSource)
            .filter_by(project_id=project_id)
            .order_by(CdcSource.id.desc()).all())


def create_source(session, project_id: int, name: str, config: dict,
                  password: str | None, actor: str) -> CdcSource:
    payload = connector_payload(config or {}, password)
    existing = (session.query(CdcSource)
                .filter_by(project_id=project_id, name=name).first())
    if existing:
        raise ValueError("cdc source already exists")
    connector = connector_name(project_id, name)
    response = _client().put("/connectors/%s/config" % connector,
                             json=payload)
    response.raise_for_status()
    source = CdcSource(project_id=project_id, name=name,
                       connector_name=connector, status="pending",
                       config_json=dict(config or {}),
                       password_encrypted=encrypt_secret(password or ""),
                       created_by=actor)
    session.add(source)
    session.commit()
    session.refresh(source)
    write_audit(session, actor, "create_cdc_source", str(source.id),
                {"name": name, "connector": connector})
    try:
        refresh_status(session, source)
    except (httpx.HTTPError, ValueError):
        pass
    return source


def refresh_status(session, source: CdcSource) -> dict:
    response = _client().get("/connectors/%s/status" % source.connector_name)
    response.raise_for_status()
    payload = response.json()
    state = (payload.get("connector") or {}).get("state") or "UNKNOWN"
    source.status = STATES.get(state.upper(), "unknown")
    source.updated_at = _now()
    session.commit()
    return {"status": source.status, "connector": state,
            "tasks": len(payload.get("tasks") or [])}


def pause_source(session, source: CdcSource, actor: str) -> CdcSource:
    response = _client().put(
        "/connectors/%s/pause" % source.connector_name)
    response.raise_for_status()
    source.status = "paused"
    source.updated_at = _now()
    session.commit()
    write_audit(session, actor, "pause_cdc_source", str(source.id),
                {"connector": source.connector_name})
    return source


def resume_source(session, source: CdcSource, actor: str) -> CdcSource:
    response = _client().put(
        "/connectors/%s/resume" % source.connector_name)
    response.raise_for_status()
    source.status = "running"
    source.updated_at = _now()
    session.commit()
    write_audit(session, actor, "resume_cdc_source", str(source.id),
                {"connector": source.connector_name})
    return source


def delete_source(session, source: CdcSource, actor: str) -> None:
    source_id, connector = source.id, source.connector_name
    response = _client().delete("/connectors/%s" % connector)
    if response.status_code not in (204, 404):
        response.raise_for_status()
    session.delete(source)
    session.commit()
    write_audit(session, actor, "delete_cdc_source", str(source_id),
                {"connector": connector})
