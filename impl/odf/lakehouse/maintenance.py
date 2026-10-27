import logging
import re

from odf.connectors.trino import quote_ident
from odf.lakehouse.service import list_tables

_log = logging.getLogger("odf.lakehouse")

_RETENTION = re.compile(r"^\d+[smhd]$")
_SIZE = re.compile(r"^\d+(?:B|KB|MB|GB)$")


def _retention(value: str) -> str:
    value = (value or "").strip()
    if not _RETENTION.match(value):
        raise ValueError("retention must look like 7d or 12h")
    return value


def _size(value: str) -> str:
    value = (value or "").strip()
    if not _SIZE.match(value):
        raise ValueError("file size threshold must look like 128MB")
    return value


def _failure(error) -> str:
    """Return a fixed reason; the detail goes to the server log, never to the
    caller."""
    text = str(error)
    _log.warning("maintenance step failed: %s", text)
    if "GC is disabled" in text:
        return "failed: snapshot cleanup is disabled for this catalog"
    return "failed"


def maintain(client, schema: str, tables=None, optimize: bool = True,
             expire_snapshots: bool = True, retention: str = "7d",
             file_size_threshold: str = "128MB") -> list:
    schema_sql = quote_ident(schema)
    names = list(tables) if tables else [t["table"]
                                         for t in list_tables(client, schema)]
    retention = _retention(retention)
    threshold = _size(file_size_threshold)
    results = []
    for name in names:
        table_sql = "%s.%s" % (schema_sql, quote_ident(name))
        entry = {"table": name, "optimize": "skipped", "expire": "skipped"}
        if optimize:
            try:
                client.execute(
                    "ALTER TABLE %s EXECUTE optimize("
                    "file_size_threshold => '%s')" % (table_sql, threshold))
                entry["optimize"] = "ok"
            except Exception as error:
                entry["optimize"] = _failure(error)
        if expire_snapshots:
            try:
                client.execute(
                    "ALTER TABLE %s EXECUTE expire_snapshots("
                    "retention_threshold => '%s')" % (table_sql, retention))
                entry["expire"] = "ok"
            except Exception as error:
                entry["expire"] = _failure(error)
        results.append(entry)
    return results
