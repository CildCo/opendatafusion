import shutil
import tempfile
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, unquote, urlparse

import pyarrow.fs as fs

from odf.connectors.base import Source


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
        "mode": (query.get("mode") or ["object"])[0],
    }


def filesystem(opts):
    scheme = "https" if opts["endpoint"].startswith("https://") else "http"
    host = opts["endpoint"].split("://", 1)[-1]
    return fs.S3FileSystem(
        access_key=opts["access_key"] or None,
        secret_key=opts["secret_key"] or None,
        endpoint_override=host, scheme=scheme, region=opts["region"])


def object_path(opts):
    return "%s/%s" % (opts["bucket"], opts["key"])


def _supported(path):
    from odf.filesource import SUFFIXES
    return Path(path).suffix.lower() in SUFFIXES


def object_keys(dsn):
    opts = options(dsn)
    client = filesystem(opts)
    if opts["mode"] != "prefix":
        info = client.get_file_info(object_path(opts))
        if not info.is_file:
            raise ValueError("object not found")
        return [opts["key"]]
    prefix = ("%s/%s" % (opts["bucket"], opts["key"].lstrip("/"))).rstrip("/")
    info = client.get_file_info(fs.FileSelector(prefix, recursive=True))
    keys = []
    for item in info:
        if not item.is_file:
            continue
        key = item.path.split("/", 1)[-1]
        if _supported(key):
            keys.append(key)
    if not keys:
        raise ValueError("no supported objects under the prefix")
    return sorted(keys)


def ping(dsn):
    opts = options(dsn)
    client = filesystem(opts)
    if opts["mode"] == "prefix":
        prefix = ("%s/%s" % (opts["bucket"],
                             opts["key"].lstrip("/"))).rstrip("/")
        if not client.get_file_info(fs.FileSelector(prefix,
                                                    recursive=False)):
            bucket = client.get_file_info(opts["bucket"])
            if not bucket.is_dir:
                raise ValueError("bucket not found")
        return True
    info = client.get_file_info(object_path(opts))
    if not info.is_file:
        raise ValueError("object not found")
    return True


def _download_key(opts, key, dest):
    stream = filesystem(opts).open_input_stream(
        "%s/%s" % (opts["bucket"], key))
    with stream, open(dest, "wb") as out:
        shutil.copyfileobj(stream, out)
    return Path(dest)


def download(dsn, dest):
    opts = options(dsn)
    return _download_key(opts, opts["key"], dest)


def _table_for_key(key):
    from odf.filesource import table_name_for
    return table_name_for(Path(key))


def table_name(opts):
    return _table_for_key(opts["key"])


def _temp_root():
    from odf.filesource import _allowed_roots
    root = _allowed_roots()[0]
    root.mkdir(parents=True, exist_ok=True)
    return root


def describe(dsn):
    from odf import filesource
    opts = options(dsn)
    out = []
    for key in object_keys(dsn):
        suffix = Path(key).suffix.lower()
        if suffix not in filesource.SUFFIXES:
            continue
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False,
                                          dir=_temp_root())
        tmp.close()
        try:
            _download_key(opts, key, tmp.name)
            columns = filesource.describe(Path(tmp.name))
        finally:
            Path(tmp.name).unlink(missing_ok=True)
        out.append({"key": key, "table": _table_for_key(key),
                    "columns": columns})
    return out


def temp_files(dsn):
    opts = options(dsn)
    directory = tempfile.mkdtemp(prefix=".odf-s3-", dir=_temp_root())
    paths = []
    try:
        for key in object_keys(dsn):
            suffix = Path(key).suffix.lower()
            path = Path(directory) / (_table_for_key(key) + suffix)
            _download_key(opts, key, path)
            paths.append(path)
    except Exception:
        shutil.rmtree(directory, ignore_errors=True)
        raise
    return paths, directory


def temp_file(dsn):
    paths, directory = temp_files(dsn)
    if len(paths) != 1:
        shutil.rmtree(directory, ignore_errors=True)
        raise ValueError(
            "prefix contains more than one object; query by table")
    return paths[0], directory


def as_file_ds(path):
    from odf.services.crypto import encrypt_secret
    return SimpleNamespace(kind="file",
                           dsn_encrypted=encrypt_secret(str(path)))


def execute(dsn, sql, params=None, max_rows=1000):
    from odf import filesource
    paths, directory = temp_files(dsn)
    try:
        if len(paths) == 1:
            return filesource.execute(as_file_ds(paths[0]), sql, params,
                                      max_rows)
        return filesource.execute_paths(paths, sql, params, max_rows)
    finally:
        shutil.rmtree(directory, ignore_errors=True)


class S3Source(Source):
    def __init__(self, ds, dag):
        from odf.services.datasource import get_dsn
        self.dsn = get_dsn(ds)
        self.dag = dag

    def read(self, cursor, limit):
        from odf.connectors.file import FileSource
        from odf.filesource import table_name_for
        paths, directory = temp_files(self.dsn)
        try:
            table = (self.dag.get("source_table") or "").split(".")[-1]
            chosen = None
            for path in paths:
                if table_name_for(path) == table:
                    chosen = path
                    break
            if chosen is None:
                if len(paths) == 1:
                    chosen = paths[0]
                else:
                    raise ValueError("object not found for table: %s" % table)
            source = FileSource(as_file_ds(chosen), self.dag)
            return source.read(cursor, limit)
        finally:
            shutil.rmtree(directory, ignore_errors=True)
