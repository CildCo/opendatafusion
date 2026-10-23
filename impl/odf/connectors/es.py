import json

import httpx

from odf.connectors.base import Sink, Source
from odf.services.datasource import get_dsn


def _base(ds):
    return get_dsn(ds).rstrip("/")


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
        r = httpx.post("%s/%s/_search" % (self.base, self.index),
                       json=body, timeout=30)
        r.raise_for_status()
        rows = [h["_source"] for h in r.json()["hits"]["hits"]]
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
        r = httpx.post("%s/_bulk" % self.base, content=body,
                       headers={"Content-Type": "application/x-ndjson"},
                       timeout=30)
        r.raise_for_status()
        if r.json().get("errors"):
            raise ValueError("es bulk errors")
        return len(rows)
