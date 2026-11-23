import shutil
import tempfile
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, unquote, urlparse

from odf.connectors.base import Source
from odf.services.crypto import encrypt_secret


def options(dsn):
    parsed = urlparse(dsn or "")
    if parsed.scheme != "s3" or not parsed.netloc:
        raise ValueError("s3 datasource needs an s3://bucket/key dsn")
    query = parse_qs(parsed.query)
    endpoint = (query.get("endpoint") or [""])[0]
    if not endpoint:
        raise ValueError("s3 endpoint is required")
    return {
        "endpoint": endpoint.rstrip("/"),
        "bucket": unquote(parsed.netloc),
        "key": unquote(parsed.path.lstrip("/")),
        "access_key": (query.get("access_key") or [""])[0],
        "secret_key": (query.get("secret_key") or [""])[0],
        "region": (query.get("region") or ["us-east-1"])[0],
    }


def filesystem(opts):
    import pyarrow.fs as fs
    scheme = "https" if opts["endpoint"].startswith("https://") else "http"
    host = opts["endpoint"].split("://", 1)[-1]
    return fs.S3FileSystem(
        access_key=opts["access_key"] or None,
        secret_key=opts["secret_key"] or None,
        endpoint_override=host, scheme=scheme, region=opts["region"])


def object_path(opts):
    return "%s/%s" % (opts["bucket"], opts["key"])


def table_name(opts):
    from odf.filesource import table_name_for
    return table_name_for(Path(opts["key"]))


def ping(dsn):
    opts = options(dsn)
    info = filesystem(opts).get_file_info(object_path(opts))
    if not info.is_file:
        raise ValueError("object not found")
    return True


def download(dsn, dest):
    opts = options(dsn)
    stream = filesystem(opts).open_input_stream(object_path(opts))
    with stream, open(dest, "wb") as out:
        shutil.copyfileobj(stream, out)
    return Path(dest)


def _temp_root():
    from odf.filesource import _allowed_roots
    root = _allowed_roots()[0]
    root.mkdir(parents=True, exist_ok=True)
    return root


def describe(dsn):
    from odf import filesource
    opts = options(dsn)
    suffix = Path(opts["key"]).suffix.lower()
    if suffix not in filesource.SUFFIXES:
        raise ValueError("unsupported object type: %s" % suffix)
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False,
                                      dir=_temp_root())
    tmp.close()
    try:
        download(dsn, tmp.name)
        return filesource.describe(Path(tmp.name))
    finally:
        Path(tmp.name).unlink(missing_ok=True)


def temp_file(dsn):
    """Download the object with the same base name so DuckDB's table name
    matches the metadata table name."""
    opts = options(dsn)
    suffix = Path(opts["key"]).suffix.lower()
    name = table_name(opts) + suffix
    directory = tempfile.mkdtemp(prefix=".odf-s3-", dir=_temp_root())
    path = Path(directory) / name
    download(dsn, path)
    return path, directory


def as_file_ds(path):
    return SimpleNamespace(kind="file",
                           dsn_encrypted=encrypt_secret(str(path)))


def execute(dsn, sql, params=None, max_rows=1000):
    from odf import filesource
    path, directory = temp_file(dsn)
    try:
        return filesource.execute(as_file_ds(path), sql, params, max_rows)
    finally:
        shutil.rmtree(directory, ignore_errors=True)


class S3Source(Source):
    def __init__(self, ds, dag):
        from odf.services.datasource import get_dsn
        self.dsn = get_dsn(ds)
        self.dag = dag

    def read(self, cursor, limit):
        from odf.connectors.file import FileSource
        path, directory = temp_file(self.dsn)
        try:
            source = FileSource(as_file_ds(path), self.dag)
            return source.read(cursor, limit)
        finally:
            shutil.rmtree(directory, ignore_errors=True)
