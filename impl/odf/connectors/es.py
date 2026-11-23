import base64
import json
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from odf.connectors.base import Sink, Source
from odf.services.datasource import get_dsn
from odf.services.net import request as outbound
from odf.settings import get_settings


def _base(ds):
    return get_dsn(ds).rstrip("/")


def _endpoint(base):
    parts = urlsplit(base)
    headers = {}
    if parts.username:
        token = "%s:%s" % (unquote(parts.username),
                           unquote(parts.password or ""))
        headers["Authorization"] = "Basic " + base64.b64encode(
            token.encode()).decode()
        host = parts.hostname or ""
        if parts.port:
            host += ":" + str(parts.port)
        base = urlunsplit(parts._replace(netloc=host))
    return base, headers


def _call(base, path, method="GET", body=None, headers=None):
    settings = get_settings()
    base, auth = _endpoint(base)
    allowed = tuple(item.strip() for item in
                    (settings.http_allowed_hosts or "").split(",")
                    if item.strip())
    payload = json.dumps(body).encode() if body is not None else None
    code, _, data = outbound(
        base + path, method=method, body=payload,
        headers={**auth, **(headers or {})},
        allow_private=settings.http_allow_private, allowed_hosts=allowed,
        timeout=30, max_bytes=settings.http_max_response_mb * 1024 * 1024)
    if code >= 400:
        raise ValueError("elasticsearch answered HTTP %d" % code)
    return json.loads(data) if data else {}


class ESSource(Source):
    def __init__(self, ds, dag):
        self.base = _base(ds)
        self.index = dag["source_table"]
        self.query = dag.get("query") or {"match_all": {}}
        self.cursor_field = dag.get("cursor_column")

    def read(self, cursor, limit):
        body = {"size": limit, "query": self.query}
        if cursor and self.cursor_field:
            body["query"] = {"range": {self.cursor_field: {"gt": cursor}}}
            body["sort"] = [{self.cursor_field: "asc"}]
        data = _call(self.base, "/%s/_search" % quote(self.index, safe=""),
                     method="POST",
                     body=body, headers={"Content-Type": "application/json"})
        rows = [h["_source"] for h in data["hits"]["hits"]]
        new_cursor = cursor
        if self.cursor_field and rows:
            new_cursor = max(str(x.get(self.cursor_field, "")) for x in rows)
        return rows, new_cursor


class ESSink(Sink):
    def __init__(self, ds, dag):
        self.base = _base(ds)
        self.index = dag["sink_table"]
        self.pk = dag.get("pk")

    def write(self, rows):
        if not rows:
            return 0
        lines = []
        for row in rows:
            meta = {"index": {"_index": self.index}}
            if self.pk and self.pk in row:
                meta["index"]["_id"] = str(row[self.pk])
            lines.append(json.dumps(meta))
            lines.append(json.dumps(row, ensure_ascii=False, default=str))
        body = "\n".join(lines) + "\n"
        settings = get_settings()
        base, auth = _endpoint(self.base)
        allowed = tuple(item.strip() for item in
                        (settings.http_allowed_hosts or "").split(",")
                        if item.strip())
        code, _, data = outbound(
            base + "/_bulk", method="POST", body=body.encode(),
            headers={**auth, "Content-Type": "application/x-ndjson"},
            allow_private=settings.http_allow_private,
            allowed_hosts=allowed, timeout=30,
            max_bytes=settings.http_max_response_mb * 1024 * 1024)
        if code >= 400:
            raise ValueError("elasticsearch answered HTTP %d" % code)
        if json.loads(data or b"{}").get("errors"):
            raise ValueError("es bulk errors")
        return len(rows)
