import math
import re
from datetime import date, datetime
from decimal import Decimal
from urllib.parse import unquote, urlparse

import httpx

_PARAM = re.compile(r"(?<![:\w]):([A-Za-z_][A-Za-z0-9_]*)")


class TrinoError(Exception):
    pass


def literal(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            raise ValueError("cannot render a non-finite number")
        return repr(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (str, date, datetime)):
        text = value.isoformat() if not isinstance(value, str) else value
        return "'" + text.replace("'", "''") + "'"
    if isinstance(value, (list, tuple)):
        return "ARRAY[" + ", ".join(literal(v) for v in value) + "]"
    raise ValueError("cannot render parameter of type %s"
                     % type(value).__name__)


def render_params(sql: str, params: dict | None) -> str:
    if params is None:
        return sql

    def replace(match):
        name = match.group(1)
        if name not in params:
            raise ValueError("missing parameter: %s" % name)
        return literal(params[name])

    return _PARAM.sub(replace, sql)


class TrinoClient:
    def __init__(self, base_url, user, catalog="", schema="", password=None,
                 client=None, timeout=60.0, max_pages=200):
        self.base_url = base_url.rstrip("/")
        self.user = user
        self.catalog = catalog
        self.schema = schema
        self.password = password
        self._max_pages = max_pages
        headers = {"X-Trino-User": user}
        if catalog:
            headers["X-Trino-Catalog"] = catalog
        if schema:
            headers["X-Trino-Schema"] = schema
        auth = (user, password) if password else None
        self._client = client or httpx.Client(
            base_url=self.base_url, timeout=timeout, headers=headers,
            auth=auth)

    @classmethod
    def from_dsn(cls, dsn, **kwargs):
        parsed = urlparse((dsn or "").strip())
        if parsed.scheme not in ("trino", "trino+http", "trino+https"):
            raise ValueError("unsupported trino dsn")
        secure = parsed.scheme == "trino+https"
        host = parsed.hostname or "localhost"
        port = parsed.port or (8443 if secure else 8080)
        base = "%s://%s:%d" % ("https" if secure else "http", host, port)
        parts = [unquote(p) for p in parsed.path.split("/") if p]
        return cls(
            base,
            unquote(parsed.username or "odf"),
            parts[0] if parts else "",
            parts[1] if len(parts) > 1 else "",
            password=unquote(parsed.password) if parsed.password else None,
            **kwargs)

    def _payload(self, response):
        response.raise_for_status()
        payload = response.json()
        error = payload.get("error")
        if error:
            raise TrinoError(error.get("message") or "trino query failed")
        return payload

    def query(self, sql, max_rows=1000):
        response = self._client.post(
            "/v1/statement", content=sql.encode("utf-8"),
            headers={"Content-Type": "text/plain"})
        payload = self._payload(response)
        columns = [c.get("name") for c in payload.get("columns") or []]
        rows = []
        pages = 0
        while True:
            if not columns and payload.get("columns"):
                columns = [c.get("name") for c in payload["columns"]]
            for item in payload.get("data") or []:
                rows.append(dict(zip(columns, item)))
                if len(rows) >= max_rows:
                    return {"columns": columns, "rows": rows[:max_rows],
                            "row_count": max_rows, "truncated": True}
            next_uri = payload.get("nextUri")
            pages += 1
            if not next_uri or pages >= self._max_pages:
                break
            payload = self._payload(self._client.get(next_uri))
        return {"columns": columns, "rows": rows, "row_count": len(rows),
                "truncated": False}

    def execute(self, sql):
        self.query(sql, max_rows=1)

    def ping(self):
        try:
            self.query("select 1", max_rows=1)
            return True
        except (TrinoError, httpx.HTTPError, ValueError):
            return False


def client_for_datasource(ds, **kwargs):
    from odf.services.datasource import get_dsn

    return TrinoClient.from_dsn(get_dsn(ds), **kwargs)
