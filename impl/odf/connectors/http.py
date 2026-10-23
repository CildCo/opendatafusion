import json
from urllib.parse import urlencode

from odf.connectors.base import Sink, Source
from odf.services.net import request as outbound
from odf.settings import get_settings


def _path(data, path):
    for part in (path.split(".") if path else []):
        data = data[part]
    return data


def _hosts():
    raw = get_settings().http_allowed_hosts
    return tuple(item.strip() for item in raw.split(",") if item.strip())


def _url(url, params):
    if not params:
        return url
    sep = "&" if "?" in url else "?"
    return url + sep + urlencode(params, doseq=True)


def _call(url, params=None, method="GET", body=None, headers=None):
    settings = get_settings()
    code, _, payload = outbound(
        _url(url, params or {}), method=method, body=body,
        headers=headers or {}, allow_private=settings.http_allow_private,
        allowed_hosts=_hosts(), timeout=settings.http_timeout_s,
        max_bytes=settings.http_max_response_mb * 1024 * 1024)
    if not payload:
        return None
    return json.loads(payload)


class HTTPSource(Source):
    def __init__(self, ds, dag):
        self.url = dag.get("source_url")
        self.headers = dag.get("headers", {})
        self.params = dag.get("params", {})
        self.records_path = dag.get("records_path", "")
        self.cursor_field = dag.get("cursor_column")

    def read(self, cursor, limit):
        params = dict(self.params)
        params.setdefault("limit", limit)
        if cursor and self.cursor_field:
            params.setdefault("since", cursor)
        data = _call(self.url, params=params, headers=self.headers)
        rows = _path(data, self.records_path)
        if not isinstance(rows, list):
            rows = [rows]
        new_cursor = cursor
        if self.cursor_field and rows:
            new_cursor = max(str(x.get(self.cursor_field, "")) for x in rows)
        return rows, new_cursor


class HTTPSink(Sink):
    def __init__(self, ds, dag):
        self.url = dag.get("sink_url")
        self.headers = dag.get("sink_headers", {})

    def write(self, rows):
        headers = {"Content-Type": "application/json", **self.headers}
        for row in rows:
            _call(self.url, method="POST", headers=headers,
                  body=json.dumps(row).encode())
        return len(rows)
