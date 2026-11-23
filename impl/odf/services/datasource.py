import re
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from odf.models import Datasource
from odf.services.crypto import decrypt_secret, encrypt_secret
from odf.settings import get_settings


def mask_dsn(dsn: str) -> str:
    # Greedy up to the last '@' so passwords containing '@' are fully hidden.
    masked = re.sub(r"(://[^:/@]+:)(.*)(@[^@/]+(?::\d+)?(?:/|$))",
                    r"\1***\3", dsn)
    return re.sub(
        r"(?i)(password|passwd|secret_key|secret_access_key)=([^&]+)",
        r"\1=***", masked)


def normalize_dsn(kind: str, dsn: str) -> str:
    dsn = (dsn or "").strip()
    kind = (kind or "").lower()
    if kind in ("mysql", "mariadb", "tidb", "doris", "starrocks",
                "oceanbase"):
        for prefix in ("mysql://", "mariadb://"):
            if dsn.startswith(prefix):
                return "mysql+pymysql://" + dsn[len(prefix):]
    if kind in ("opengauss", "kingbase", "gaussdb"):
        for prefix in ("postgres://", "postgresql://"):
            if dsn.startswith(prefix):
                return "postgresql+psycopg://" + dsn[len(prefix):]
    if kind == "oracle":
        for prefix in ("oracle://", "oracle+cx_oracle://"):
            if dsn.startswith(prefix):
                return "oracle+oracledb://" + dsn[len(prefix):]
    if kind in ("mssql", "sqlserver"):
        for prefix in ("mssql://", "sqlserver://"):
            if dsn.startswith(prefix):
                return "mssql+pymssql://" + dsn[len(prefix):]
    return dsn


def connect_args_for(kind: str, dsn: str = "", timeout: int = 5) -> dict:
    kind = (kind or "").lower()
    if kind == "sqlite" or (dsn or "").startswith("sqlite"):
        return {}
    if kind == "oracle":
        return {"tcp_connect_timeout": timeout}
    if kind in ("mssql", "sqlserver") or (dsn or "").startswith("mssql+pymssql"):
        return {"login_timeout": timeout}
    if kind == "clickhouse":
        return {}
    if kind == "trino":
        return {}
    if kind == "duckdb":
        return {}
    return {"connect_timeout": timeout}


def get_dsn(ds: Datasource) -> str:
    return normalize_dsn(ds.kind, decrypt_secret(ds.dsn_encrypted))


def prepare_connection(conn, dialect: str, timeout_ms: int | None = None):
    if dialect == "postgresql" and timeout_ms:
        conn.execute(text("set statement_timeout = %d" % timeout_ms))
    elif dialect in ("mysql", "mariadb"):
        conn.execute(text(
            "SET SESSION sql_mode = CONCAT(@@sql_mode, ',ANSI_QUOTES')"))
        if timeout_ms:
            conn.execute(text("SET SESSION MAX_EXECUTION_TIME = %d"
                              % timeout_ms))


def _url_for(dsn: str):
    if dsn.startswith("postgres://"):
        dsn = "postgresql://" + dsn[len("postgres://"):]
    return make_url(dsn)


def _default_port(name: str):
    return {"postgresql": 5432, "mysql": 3306, "mssql": 1433}.get(name)


def _norm_host(host: str | None) -> str:
    host = (host or "").lower().rstrip(".")
    if host in ("127.0.0.1", "::1", "localhost"):
        return "localhost"
    return host


def is_control_database(dsn: str, control: str | None = None) -> bool:
    """True when a datasource points at ODF's own control database."""
    control = control or get_settings().database_url
    try:
        target = _url_for(dsn)
        own = _url_for(control)
    except Exception:
        return False
    if target.get_backend_name() != own.get_backend_name():
        return False
    if own.get_backend_name() == "sqlite":
        if not own.database or not target.database:
            return own.database == target.database
        if ":memory:" in (own.database, target.database):
            return own.database == target.database
        return (Path(own.database).resolve()
                == Path(target.database).resolve())
    return (_norm_host(target.host) == _norm_host(own.host)
            and (target.port or _default_port(target.get_backend_name()))
            == (own.port or _default_port(own.get_backend_name()))
            and (target.database or "").lstrip("/")
            == (own.database or "").lstrip("/"))


def create_datasource(session, project_id: int, name: str, dsn: str,
                      kind: str) -> Datasource:
    if is_control_database(dsn):
        raise ValueError("control database cannot be used as a datasource")
    ds = Datasource(project_id=project_id, name=name, kind=kind,
                    dsn_encrypted=encrypt_secret(dsn))
    session.add(ds)
    session.commit()
    session.refresh(ds)
    return ds


def check_connection(dsn: str, timeout: int = 5,
                     kind: str | None = None) -> dict:
    kind = (kind or "").lower()
    try:
        if kind == "trino":
            from odf.trino.client import TrinoClient
            ok = TrinoClient.from_dsn(dsn, timeout=timeout).ping()
            if not ok:
                return {"ok": False, "error": "trino did not answer"}
            return {"ok": True, "error": None}
        if kind == "clickhouse":
            from odf import clickhouse
            client = clickhouse.client_from_dsn(dsn)
            try:
                client.command("SELECT 1")
            finally:
                client.close()
            return {"ok": True, "error": None}
        if kind in ("http", "es"):
            return _check_http(dsn, timeout, kind)
        if kind == "mongodb":
            from odf.connectors import mongo
            mongo.ping(dsn, timeout)
            return {"ok": True, "error": None}
        if kind == "kafka":
            from odf.connectors import kafka
            kafka.ping(dsn, timeout)
            return {"ok": True, "error": None}
        if kind == "s3":
            from odf.connectors import s3
            s3.ping(dsn)
            return {"ok": True, "error": None}
        if kind == "hive":
            from odf.connectors import hive
            hive.ping(dsn)
            return {"ok": True, "error": None}
        if kind == "dm":
            from odf.connectors import dm
            dm.ping(dsn)
            return {"ok": True, "error": None}
        args = connect_args_for(kind, dsn, timeout)
        e = create_engine(dsn, connect_args=args)
        try:
            with e.connect() as c:
                c.execute(text("select 1"))
        finally:
            e.dispose()
        return {"ok": True, "error": None}
    except Exception as error:
        return {"ok": False, "error": _safe_error(error, dsn)}


def _check_http(dsn: str, timeout: int, kind: str) -> dict:
    from odf.services.net import request as outbound
    settings = get_settings()
    allowed = tuple(item.strip() for item in
                    (settings.http_allowed_hosts or "").split(",")
                    if item.strip())
    path = "/_cluster/health" if kind == "es" else ""
    code, _, payload = outbound(
        dsn.rstrip("/") + path, timeout=timeout,
        allow_private=settings.http_allow_private, allowed_hosts=allowed,
        max_bytes=1024 * 1024)
    if code >= 500:
        return {"ok": False, "error": "endpoint answered HTTP %d" % code}
    return {"ok": True, "error": None}


def _safe_error(error: Exception, dsn: str) -> str:
    """Map driver errors to a small set of client-safe reasons.

    Raw driver messages can include connection strings, stack details or
    server internals, so only a curated label is returned to the console.
    """
    text = (str(error) or "").lower()
    if "outside the configured file roots" in text:
        return "file path is outside the allowed roots"
    if "unsupported file type" in text:
        return "unsupported file type"
    if "no such file" in text or "not found" in text:
        return "file not found"
    if "not allowed" in text:
        return "address or host is not allowed"
    if ("resolve" in text or "name or service" in text or
            "getaddrinfo" in text or "nodename" in text):
        return "host cannot be resolved"
    if ("authentication" in text or "password" in text or
            "access denied" in text or "login failed" in text or
            "invalid user" in text):
        return "authentication failed"
    if "timed out" in text or "timeout" in text:
        return "connection timed out"
    if "refused" in text:
        return "connection refused"
    if "http 5" in text or "server error" in text:
        return "endpoint returned a server error"
    if "http 4" in text or "unauthorized" in text or "forbidden" in text:
        return "endpoint rejected the request"
    return "connection failed"


def test_connection(dsn: str, timeout: int = 5, kind: str | None = None) -> bool:
    return bool(check_connection(dsn, timeout, kind).get("ok"))


class DatasourceInUse(ValueError):
    def __init__(self, blockers: dict):
        super().__init__("datasource is in use")
        self.blockers = blockers


def update_datasource(session, project_id: int, datasource_id: int,
                      name: str | None = None,
                      dsn: str | None = None) -> Datasource:
    ds = session.get(Datasource, datasource_id)
    if not ds or ds.project_id != project_id:
        raise ValueError("datasource not found")
    if name:
        ds.name = name.strip()
    if dsn:
        dsn = normalize_dsn(ds.kind, dsn)
        if is_control_database(dsn):
            raise ValueError("control database cannot be used as a datasource")
        ds.dsn_encrypted = encrypt_secret(dsn)
    session.commit()
    session.refresh(ds)
    return ds


def delete_datasource(session, project_id: int, datasource_id: int,
                      force: bool = False) -> dict:
    from odf.models import (Column, Dataset, DatasetTag, QualityResult,
                            QualityRule, StandardMapping)

    ds = session.get(Datasource, datasource_id)
    if not ds or ds.project_id != project_id:
        raise ValueError("datasource not found")
    datasets = session.query(Dataset).filter_by(datasource_id=ds.id).all()
    ids = [d.id for d in datasets]
    rules = (session.query(QualityRule).filter(QualityRule.dataset_id.in_(ids))
             .all() if ids else [])
    rule_ids = [r.id for r in rules]
    blockers = {
        "datasets": len(ids),
        "quality_rules": len(rules),
        "tags": (session.query(DatasetTag).filter(
            DatasetTag.dataset_id.in_(ids)).count() if ids else 0),
        "mappings": (session.query(StandardMapping).filter(
            StandardMapping.dataset_id.in_(ids)).count() if ids else 0),
    }
    if any(blockers.values()) and not force:
        raise DatasourceInUse(blockers)
    if rule_ids:
        session.query(QualityResult).filter(
            QualityResult.rule_id.in_(rule_ids)).delete(
                synchronize_session=False)
        session.query(QualityRule).filter(
            QualityRule.id.in_(rule_ids)).delete(synchronize_session=False)
    if ids:
        session.query(DatasetTag).filter(
            DatasetTag.dataset_id.in_(ids)).delete(synchronize_session=False)
        session.query(StandardMapping).filter(
            StandardMapping.dataset_id.in_(ids)).delete(
                synchronize_session=False)
        session.query(Column).filter(Column.dataset_id.in_(ids)).delete(
            synchronize_session=False)
        session.query(Dataset).filter(Dataset.id.in_(ids)).delete(
            synchronize_session=False)
    session.delete(ds)
    session.commit()
    return blockers
