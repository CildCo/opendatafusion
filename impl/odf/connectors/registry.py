"""Connector registry: the single source of truth for datasource types.

Each connector declares its capability set, the form fields the console
renders, and how to build or parse its DSN.  The API, metadata sync, query
paths and the console all read this registry so a type can never advertise a
capability it does not implement.
"""
from urllib.parse import quote, unquote, urlparse

from sqlalchemy.engine import make_url

FIELDS = {
    "host": {"key": "host", "label": "Host", "type": "text",
             "required": True, "placeholder": "db.example.com"},
    "port": {"key": "port", "label": "Port", "type": "number",
             "required": True},
    "database": {"key": "database", "label": "Database", "type": "text",
                 "required": True, "placeholder": "analytics"},
    "username": {"key": "username", "label": "Username", "type": "text",
                 "required": True},
    "password": {"key": "password", "label": "Password", "type": "password",
                 "required": False, "secret": True},
    "sslmode": {"key": "sslmode", "label": "SSL mode", "type": "select",
                "required": False},
    "path": {"key": "path", "label": "File path", "type": "text",
             "required": True, "placeholder": "/data/odf/files/sales.csv"},
    "url": {"key": "url", "label": "Base URL", "type": "url",
            "required": True, "placeholder": "https://api.example.com"},
    "service": {"key": "service", "label": "Service", "type": "text",
                "required": True, "placeholder": "ORCLPDB1"},
    "catalog": {"key": "catalog", "label": "Catalog", "type": "text",
                "required": True, "placeholder": "iceberg"},
    "schema": {"key": "schema", "label": "Schema", "type": "text",
               "required": False, "placeholder": "sales"},
    "secure": {"key": "secure", "label": "TLS", "type": "select",
               "required": False},
    "bootstrap": {"key": "bootstrap", "label": "Bootstrap servers",
                  "type": "text", "required": True,
                  "placeholder": "kafka:9092"},
}


def field(key, **overrides):
    row = dict(FIELDS[key])
    row.update(overrides)
    return row


def _caps(test=True, metadata=True, query=True, source=True, sink=False,
          cdc=False):
    return {"test": test, "metadata": metadata, "query": query,
            "source": source, "sink": sink, "cdc": cdc}


SSLMODES = ["disable", "allow", "prefer", "require", "verify-ca",
            "verify-full"]

SPECS = [
    {"kind": "postgres", "label": "PostgreSQL", "group": "database",
     "capabilities": _caps(sink=True, cdc=True),
     "fields": [field("host"), field("port", default=5432),
                field("database"), field("username"), field("password"),
                field("sslmode", options=SSLMODES)]},
    {"kind": "mysql", "label": "MySQL", "group": "database",
     "capabilities": _caps(sink=True, cdc=True),
     "fields": [field("host"), field("port", default=3306),
                field("database"), field("username"), field("password")]},
    {"kind": "mariadb", "label": "MariaDB", "group": "database",
     "capabilities": _caps(sink=True, cdc=True),
     "fields": [field("host"), field("port", default=3306),
                field("database"), field("username"), field("password")]},
    {"kind": "sqlite", "label": "SQLite", "group": "database",
     "capabilities": _caps(sink=True),
     "fields": [field("path", placeholder="sqlite:////data/app.db")]},
    {"kind": "oracle", "label": "Oracle", "group": "database",
     "capabilities": _caps(cdc=True),
     "fields": [field("host"), field("port", default=1521),
                field("service"), field("username"), field("password")]},
    {"kind": "mssql", "label": "SQL Server", "group": "database",
     "capabilities": _caps(),
     "fields": [field("host"), field("port", default=1433),
                field("database"), field("username"), field("password")]},
    {"kind": "tidb", "label": "TiDB", "group": "database",
     "capabilities": _caps(sink=True),
     "fields": [field("host"), field("port", default=4000),
                field("database"), field("username"), field("password")]},
    {"kind": "doris", "label": "Apache Doris", "group": "database",
     "capabilities": _caps(),
     "fields": [field("host"), field("port", default=9030),
                field("database"), field("username"), field("password")]},
    {"kind": "starrocks", "label": "StarRocks", "group": "database",
     "capabilities": _caps(),
     "fields": [field("host"), field("port", default=9030),
                field("database"), field("username"), field("password")]},
    {"kind": "oceanbase", "label": "OceanBase (MySQL)", "group": "database",
     "capabilities": _caps(sink=True),
     "fields": [field("host"), field("port", default=2881),
                field("database"), field("username"), field("password")]},
    {"kind": "opengauss", "label": "openGauss", "group": "database",
     "capabilities": _caps(),
     "fields": [field("host"), field("port", default=5432),
                field("database"), field("username"), field("password"),
                field("sslmode", options=SSLMODES)]},
    {"kind": "kingbase", "label": "KingbaseES", "group": "database",
     "capabilities": _caps(),
     "fields": [field("host"), field("port", default=5432),
                field("database"), field("username"), field("password"),
                field("sslmode", options=SSLMODES)]},
    {"kind": "mongodb", "label": "MongoDB", "group": "database",
     "capabilities": _caps(query=False, source=False),
     "fields": [field("host"), field("port", default=27017),
                field("database"), field("username", required=False),
                field("password")]},
    {"kind": "gaussdb", "label": "GaussDB / openGauss", "group": "database",
     "capabilities": _caps(),
     "fields": [field("host"), field("port", default=5432),
                field("database"), field("username"), field("password"),
                field("sslmode", options=SSLMODES)]},
    {"kind": "duckdb", "label": "DuckDB", "group": "analytics",
     "capabilities": _caps(),
     "fields": [field("path", placeholder="duckdb:///data/analytics.db")]},
    {"kind": "clickhouse", "label": "ClickHouse", "group": "analytics",
     "capabilities": _caps(),
     "fields": [field("host"), field("port", default=8123),
                field("database", required=False, default="default"),
                field("username", default="default"), field("password"),
                field("secure", options=["false", "true"])]},
    {"kind": "trino", "label": "Trino / Iceberg", "group": "analytics",
     "capabilities": _caps(),
     "fields": [field("host"), field("port", default=8080),
                field("catalog"), field("schema"), field("username"),
                field("password"),
                field("secure", options=["false", "true"])]},
    {"kind": "file", "label": "Local file", "group": "file",
     "capabilities": _caps(sink=False),
     "fields": [field("path")]},
    {"kind": "kafka", "label": "Kafka", "group": "stream",
     "capabilities": _caps(metadata=False, query=False, source=True,
                           sink=True),
     "fields": [field("bootstrap")]},
    {"kind": "http", "label": "HTTP API", "group": "api",
     "capabilities": _caps(metadata=False, query=False, sink=True),
     "fields": [field("url")]},
    {"kind": "es", "label": "Elasticsearch", "group": "api",
     "capabilities": _caps(query=False, sink=True),
     "fields": [field("url")]},
]

SPEC_BY_KIND = {row["kind"]: row for row in SPECS}
GROUPS = [
    {"key": "database", "label": "Databases"},
    {"key": "analytics", "label": "Analytics engines"},
    {"key": "file", "label": "Files"},
    {"key": "api", "label": "APIs and search"},
    {"key": "stream", "label": "Streaming"},
]


def get_spec(kind):
    return SPEC_BY_KIND.get((kind or "").lower())


def require_spec(kind):
    spec = get_spec(kind)
    if not spec:
        raise ValueError("unsupported datasource kind: %s" % kind)
    return spec


def capabilities(kind):
    spec = get_spec(kind)
    return dict(spec["capabilities"]) if spec else {}


def supports(kind, capability):
    return bool(capabilities(kind).get(capability))


def catalog():
    return {"groups": GROUPS, "connectors": SPECS}


def build_dsn(kind, values):
    """Build a DSN from console form values, validating required fields."""
    spec = require_spec(kind)
    kind = spec["kind"]
    values = {k: v for k, v in (values or {}).items() if v not in (None, "")}
    for item in spec["fields"]:
        key = item["key"]
        if values.get(key) in (None, "") and "default" in item:
            values[key] = item["default"]
        if item.get("required") and not str(values.get(key, "")).strip():
            raise ValueError("%s is required" % item["label"])
    if kind == "file":
        return str(values.get("path", "")).strip()
    if kind in ("http", "es"):
        return str(values.get("url", "")).strip()
    if kind == "kafka":
        return "kafka://" + str(values.get("bootstrap", "")).strip()
    if kind == "mongodb":
        auth = ""
        if values.get("username"):
            auth = "%s:%s@" % (_q(values["username"]),
                               _q(values.get("password", "")))
        return "mongodb://%s%s:%s/%s" % (
            auth, values["host"], values.get("port") or 27017,
            _q(values.get("database", "")))
    if kind == "sqlite":
        path = str(values.get("path", "")).strip()
        if path.startswith("sqlite:"):
            return path
        return "sqlite:///" + path
    if kind == "duckdb":
        path = str(values.get("path", "")).strip()
        if path.startswith("duckdb:"):
            return path
        return "duckdb:///" + path
    if kind == "clickhouse":
        secure = str(values.get("secure", "false")).lower() == "true"
        scheme = "clickhouse+https" if secure else "clickhouse"
        return "%s://%s:%s@%s:%s/%s" % (
            scheme, _q(values.get("username", "default")),
            _q(values.get("password", "")), values["host"],
            values.get("port") or 8123, _q(values.get("database", "default")))
    if kind == "trino":
        secure = str(values.get("secure", "false")).lower() == "true"
        scheme = "trino+https" if secure else "trino"
        user = _q(values.get("username", ""))
        password = values.get("password", "")
        auth = user + (":" + _q(password) if password else "")
        path = "/" + _q(values.get("catalog", ""))
        if values.get("schema"):
            path += "/" + _q(values["schema"])
        return "%s://%s@%s:%s%s" % (
            scheme, auth, values["host"], values.get("port") or 8080, path)
    if kind == "oracle":
        return "oracle+oracledb://%s:%s@%s:%s/%s" % (
            _q(values["username"]), _q(values.get("password", "")),
            values["host"], values.get("port") or 1521,
            _q(values["service"]))
    driver = {"postgres": "postgresql+psycopg", "mysql": "mysql+pymysql",
              "mariadb": "mysql+pymysql", "mssql": "mssql+pymssql",
              "tidb": "mysql+pymysql", "doris": "mysql+pymysql",
              "starrocks": "mysql+pymysql", "oceanbase": "mysql+pymysql",
              "opengauss": "postgresql+psycopg",
              "kingbase": "postgresql+psycopg",
              "gaussdb": "postgresql+psycopg"}[kind]
    database = _q(values.get("database", ""))
    query = ""
    if kind in ("postgres", "opengauss", "kingbase", "gaussdb") and             values.get("sslmode"):
        query = "?sslmode=" + _q(values["sslmode"])
    return "%s://%s:%s@%s:%s/%s%s" % (
        driver, _q(values["username"]), _q(values.get("password", "")),
        values["host"], values.get("port") or _default_port(kind),
        database, query)


def parse_dsn(kind, dsn):
    """Split a stored DSN into form values. Secrets are returned as-is so the
    API can mask them before sending them to the console."""
    spec = require_spec(kind)
    kind = spec["kind"]
    dsn = (dsn or "").strip()
    if kind in ("file", "http", "es"):
        key = "path" if kind == "file" else "url"
        return {key: dsn}
    if kind == "kafka":
        return {"bootstrap": dsn[len("kafka://"):]
                if dsn.startswith("kafka://") else dsn}
    if kind == "mongodb":
        parsed = urlparse(dsn)
        return {"host": parsed.hostname or "", "port": parsed.port or 27017,
                "database": unquote((parsed.path or "").lstrip("/")),
                "username": unquote(parsed.username or ""),
                "password": unquote(parsed.password or "")}
    if kind == "sqlite":
        prefix = "sqlite:///"
        return {"path": dsn[len(prefix):] if dsn.startswith(prefix) else dsn}
    if kind == "duckdb":
        prefix = "duckdb:///"
        return {"path": dsn[len(prefix):] if dsn.startswith(prefix) else dsn}
    if kind == "clickhouse":
        from odf.clickhouse import parse_dsn as parse_clickhouse
        opts = parse_clickhouse(dsn)
        return {"host": opts["host"], "port": opts["port"],
                "database": opts["database"],
                "username": opts["username"], "password": opts["password"],
                "secure": "true" if opts["secure"] else "false"}
    if kind == "trino":
        parsed = urlparse(dsn)
        parts = [unquote(p) for p in parsed.path.split("/") if p]
        return {"host": parsed.hostname or "", "port": parsed.port or 8080,
                "catalog": parts[0] if parts else "",
                "schema": parts[1] if len(parts) > 1 else "",
                "username": unquote(parsed.username or ""),
                "password": unquote(parsed.password or ""),
                "secure": "true" if parsed.scheme == "trino+https" else "false"}
    if kind == "oracle":
        parsed = urlparse(dsn)
        return {"host": parsed.hostname or "", "port": parsed.port or 1521,
                "service": unquote(parsed.path.lstrip("/")),
                "username": unquote(parsed.username or ""),
                "password": unquote(parsed.password or "")}
    url = make_url(_normalize_driver(kind, dsn))
    values = {"host": url.host or "",
              "port": url.port or _default_port(kind),
              "database": (url.database or "").lstrip("/"),
              "username": url.username or "",
              "password": url.password or ""}
    if kind in ("postgres", "opengauss", "kingbase", "gaussdb"):
        values["sslmode"] = (url.query.get("sslmode") or "")
    return values


def masked_config(kind, dsn):
    values = parse_dsn(kind, dsn)
    for item in require_spec(kind)["fields"]:
        if item.get("secret") and values.get(item["key"]):
            values[item["key"]] = ""
            values["has_" + item["key"]] = True
    return values


def _normalize_driver(kind, dsn):
    if kind == "mysql" or kind == "mariadb":
        return dsn.replace("mysql://", "mysql+pymysql://", 1) \
            if dsn.startswith("mysql://") else dsn
    if kind == "postgres" and dsn.startswith("postgres://"):
        return "postgresql://" + dsn[len("postgres://"):]
    if kind == "mssql":
        return dsn.replace("mssql://", "mssql+pymssql://", 1) \
            if dsn.startswith("mssql://") else dsn
    return dsn


def _q(value):
    return quote(str(value if value is not None else ""), safe="")


def _default_port(kind):
    return {"postgres": 5432, "mysql": 3306, "mariadb": 3306,
            "mssql": 1433, "oracle": 1521, "clickhouse": 8123,
            "trino": 8080, "tidb": 4000, "doris": 9030,
            "starrocks": 9030, "oceanbase": 2881,
            "opengauss": 5432, "kingbase": 5432,
            "gaussdb": 5432, "mongodb": 27017}.get(kind)
