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
    return re.sub(r"(?i)(password|passwd)=([^&]+)", r"\1=***", masked)


def normalize_dsn(kind: str, dsn: str) -> str:
    dsn = (dsn or "").strip()
    kind = (kind or "").lower()
    if kind in ("mysql", "mariadb"):
        for prefix in ("mysql://", "mariadb://"):
            if dsn.startswith(prefix):
                return "mysql+pymysql://" + dsn[len(prefix):]
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


def test_connection(dsn: str, timeout: int = 5, kind: str | None = None) -> bool:
    if (kind or "").lower() == "trino":
        try:
            from odf.trino.client import TrinoClient
            return TrinoClient.from_dsn(dsn, timeout=timeout).ping()
        except Exception:
            return False
    if (kind or "").lower() == "clickhouse":
        try:
            from odf import clickhouse
            client = clickhouse.client_from_dsn(dsn)
            try:
                client.command("SELECT 1")
            finally:
                client.close()
            return True
        except Exception:
            return False
    args = connect_args_for(kind or "", dsn, timeout)
    try:
        e = create_engine(dsn, connect_args=args)
        with e.connect() as c:
            c.execute(text("select 1"))
        return True
    except Exception:
        return False
