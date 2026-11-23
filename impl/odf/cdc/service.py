import re
from datetime import datetime, timezone

import httpx

from odf.models import CdcSource
from odf.services.audit import write_audit
from odf.services.crypto import decrypt_secret, encrypt_secret
from odf.settings import get_settings

STATES = {"RUNNING": "running", "PAUSED": "paused", "FAILED": "failed",
          "STOPPED": "stopped", "UNASSIGNED": "pending"}
CONNECTOR_CLASSES = {
    "postgres": "io.debezium.connector.postgresql.PostgresConnector",
    "mysql": "io.debezium.connector.mysql.MySqlConnector",
    "oracle": "io.debezium.connector.oracle.OracleConnector",
    "mssql": "io.debezium.connector.sqlserver.SqlServerConnector",
}
CONNECTOR_CLASS = CONNECTOR_CLASSES["postgres"]


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


def connector_payload(config: dict, password: str | None,
                      name: str = "") -> dict:
    import zlib
    engine = str(config.get("engine") or "postgres").lower()
    if engine not in CONNECTOR_CLASSES:
        raise ValueError("unsupported cdc engine: %s" % engine)
    database = _require(config, "database")
    payload = {
        "connector.class": CONNECTOR_CLASSES[engine],
        "tasks.max": "1",
        "database.hostname": _require(config, "host"),
        "database.user": _require(config, "user"),
        "database.password": password or "",
        "topic.prefix": str(config.get("topic_prefix") or "odf"),
    }
    tables = str(config.get("table_list") or "").strip()
    if tables:
        payload["table.include.list"] = tables
    if engine == "postgres":
        payload.update({
            "plugin.name": "pgoutput",
            "database.port": str(config.get("port") or 5432),
            "database.dbname": database,
            "schema.include.list": str(config.get("schema_list") or "public"),
            "publication.autocreate.mode": "filtered",
        })
    elif engine == "mysql":
        seed = "%s/%s" % (config.get("host"), database)
        payload.update({
            "database.port": str(config.get("port") or 3306),
            "database.include.list": str(config.get("schema_list")
                                         or database),
            "database.server.id": str(zlib.crc32(seed.encode()) % 1000000
                                      + 1000),
            "schema.history.internal.kafka.bootstrap.servers": str(
                config.get("kafka_bootstrap") or "kafka:9092"),
            "schema.history.internal.kafka.topic": "schema-history-%s" % (
                name or config.get("topic_prefix") or "odf"),
        })
    elif engine == "mssql":
        payload.update({
            "database.port": str(config.get("port") or 1433),
            "database.names": database,
            "database.encrypt": "false",
            "schema.include.list": str(config.get("schema_list") or "dbo"),
            "schema.history.internal.kafka.bootstrap.servers": str(
                config.get("kafka_bootstrap") or "kafka:9092"),
            "schema.history.internal.kafka.topic": "schema-history-%s" % (
                name or config.get("topic_prefix") or "odf"),
        })
    else:
        payload.update({
            "database.port": str(config.get("port") or 1521),
            "database.dbname": database,
            "database.connector": "logminer",
            "database.connection.adapter": "logminer",
            "schema.include.list": str(config.get("schema_list")
                                       or database.upper()),
            "schema.history.internal.kafka.bootstrap.servers": str(
                config.get("kafka_bootstrap") or "kafka:9092"),
            "schema.history.internal.kafka.topic": "schema-history-%s" % (
                name or config.get("topic_prefix") or "odf"),
        })
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
    existing = (session.query(CdcSource)
                .filter_by(project_id=project_id, name=name).first())
    if existing:
        raise ValueError("cdc source already exists")
    from odf.services.platform import get_doc
    platform_cdc = get_doc(session, mask=True)["cdc"]
    config = dict(config or {})
    if not config.get("topic_prefix") and platform_cdc.get("topic_prefix"):
        config["topic_prefix"] = platform_cdc["topic_prefix"]
    if not config.get("kafka_bootstrap")             and platform_cdc.get("kafka_bootstrap"):
        config["kafka_bootstrap"] = platform_cdc["kafka_bootstrap"]
    connector = connector_name(project_id, name)
    payload = connector_payload(config, password, connector)
    response = _client().put("/connectors/%s/config" % connector,
                             json=payload)
    response.raise_for_status()
    source = CdcSource(project_id=project_id, name=name,
                       connector_name=connector, status="pending",
                       config_json=config,
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


def parse_connector_status(payload: dict) -> dict:
    connector = payload.get("connector") or {}
    state = connector.get("state") or "UNKNOWN"
    tasks = []
    for task in payload.get("tasks") or []:
        tasks.append({"id": task.get("id"),
                      "state": task.get("state") or "UNKNOWN",
                      "trace": (task.get("trace") or "")[:2000]})
    return {"state": state, "tasks": tasks,
            "failed_tasks": sum(1 for t in tasks
                                if t["state"].upper() == "FAILED"),
            "trace": (connector.get("trace") or "")[:2000]}


def connector_detail(session, source: CdcSource) -> dict:
    response = _client().get("/connectors/%s/status" % source.connector_name)
    response.raise_for_status()
    detail = parse_connector_status(response.json())
    config = (source.config_json or {}).copy()
    config.pop("password", None)
    detail.update({"id": source.id, "name": source.name,
                   "connector_name": source.connector_name,
                   "status": source.status, "config": config,
                   "created_at": source.created_at.isoformat()})
    return detail


def update_tables(session, source: CdcSource, table_list: str,
                  actor: str) -> CdcSource:
    config = dict(source.config_json or {})
    config["table_list"] = table_list
    password = decrypt_secret(source.password_encrypted) \
        if source.password_encrypted else ""
    payload = connector_payload(config, password,
                                source.connector_name)
    response = _client().put(
        "/connectors/%s/config" % source.connector_name, json=payload)
    response.raise_for_status()
    source.config_json = config
    source.updated_at = _now()
    session.commit()
    write_audit(session, actor, "update_cdc_tables", str(source.id),
                {"connector": source.connector_name,
                 "table_list": table_list})
    return source
