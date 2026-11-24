import json
import os
import shlex
import subprocess
import tempfile
import time

from odf.connectors.base import Source

MAX_OUTPUT = 64 * 1024 * 1024


def _policy():
    from odf.db import SessionLocal
    from odf.services.platform import get_doc
    with SessionLocal() as session:
        doc = get_doc(session, mask=False).get("airbyte") or {}
    return {
        "enabled": bool(doc.get("enabled")),
        "image_allowlist": [x.strip() for x in
                            (doc.get("image_allowlist") or "").split(",")
                            if x.strip()],
        "command_allowlist": [x.strip() for x in
                              (doc.get("command_allowlist") or "").split(",")
                              if x.strip()],
        "timeout_s": max(5, min(int(doc.get("timeout_s") or 300), 3600)),
    }


def _parse(dsn):
    data = json.loads(dsn)
    if not isinstance(data, dict) or not data.get("image"):
        raise ValueError("airbyte connector needs an image or command")
    config = data.get("config")
    if not isinstance(config, dict):
        raise ValueError("airbyte connector configuration must be an object")
    return data["image"], data.get("runtime") or "docker", config


def _allowed(image, runtime, policy):
    if not policy["enabled"]:
        raise ValueError("Airbyte connectors are disabled by the platform "
                         "administrator")
    if runtime == "docker":
        if not any(image.startswith(prefix)
                   for prefix in policy["image_allowlist"]):
            raise ValueError("connector image is not in the allowlist")
        return
    if runtime == "command":
        if not policy["command_allowlist"] or not any(
                image.startswith(prefix)
                for prefix in policy["command_allowlist"]):
            raise ValueError("connector command is not in the allowlist")
        return
    raise ValueError("runtime must be docker or command")


def _split(image):
    parts = shlex.split(image, posix=os.name != "nt")
    return [part.strip('"') for part in parts]


def _command(image, runtime, args, workdir):
    if runtime == "docker":
        return ["docker", "run", "--rm", "-i", "-v",
                "%s:/airbyte" % workdir, image, *args]
    return [*_split(image), *args]


def _write(workdir, name, value):
    path = os.path.join(workdir, name)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(value, handle)
    return path


def _error(proc, stderr_path):
    proc.wait(timeout=10)
    try:
        with open(stderr_path, encoding="utf-8", errors="replace") as handle:
            text = handle.read(2000).strip()
    except OSError:
        text = ""
    return text or "connector exited with code %s" % proc.returncode


def _stream(image, runtime, config, command, catalog=None, state=None,
            limit=None, policy=None, stderr_path=None):
    with tempfile.TemporaryDirectory(prefix="odf-airbyte-") as workdir:
        _write(workdir, "config.json", config)
        args = [command, "--config",
                "/airbyte/config.json" if runtime == "docker"
                else os.path.join(workdir, "config.json")]
        if catalog is not None:
            _write(workdir, "catalog.json", catalog)
            args += ["--catalog",
                     "/airbyte/catalog.json" if runtime == "docker"
                     else os.path.join(workdir, "catalog.json")]
        if state is not None:
            _write(workdir, "state.json", state)
            args += ["--state",
                     "/airbyte/state.json" if runtime == "docker"
                     else os.path.join(workdir, "state.json")]
        env = dict(os.environ)
        env.setdefault("AIRBYTE_ENTRYPOINT", "")
        err_handle = (open(stderr_path, "w", encoding="utf-8")
                      if stderr_path else subprocess.DEVNULL)
        # Airbyte connectors execute administrator-allowlisted code by design;
        # the platform switch, image/command allowlist and timeout are the
        # security boundary.
        # codeql[py/command-line-injection]
        proc = subprocess.Popen(  # codeql[py/command-line-injection]
            _command(image, runtime, args, workdir),
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=err_handle, text=True, encoding="utf-8",
            errors="replace", env=env)
        messages = []
        rows = []
        outputs = None
        deadline = time.time() + (policy or {}).get("timeout_s", 300)
        size = 0
        stop_at = None
        try:
            for line in proc.stdout:
                if stop_at is not None and time.time() > stop_at:
                    proc.terminate()
                    break
                size += len(line)
                if size > MAX_OUTPUT:
                    proc.kill()
                    raise ValueError("connector output exceeds the limit")
                line = line.strip()
                if not line:
                    continue
                try:
                    message = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(message, dict):
                    continue
                kind = message.get("type")
                if kind == "LOG" or kind == "TRACE":
                    continue
                messages.append(message)
                if kind == "RECORD":
                    if limit and len(rows) >= limit:
                        if stop_at is None:
                            stop_at = time.time() + 5
                        continue
                    record = message.get("record") or {}
                    data = record.get("data")
                    rows.append(data if isinstance(data, dict)
                                else {"data": data})
                elif kind == "STATE":
                    outputs = message.get("state")
                if time.time() > deadline:
                    proc.kill()
                    raise ValueError("connector timed out")
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        finally:
            if proc.poll() is None:
                proc.kill()
            if hasattr(err_handle, "close"):
                err_handle.close()
        return messages, rows, outputs


def _catalog_from(messages):
    for message in messages:
        if message.get("type") == "CATALOG":
            return message.get("catalog") or {}
    return {}


def tables(dsn):
    image, runtime, config = _parse(dsn)
    policy = _policy()
    _allowed(image, runtime, policy)
    messages, _, _ = _stream(image, runtime, config, "discover",
                             policy=policy)
    catalog = _catalog_from(messages)
    out = []
    for stream in catalog.get("streams") or []:
        if not isinstance(stream, dict) or not stream.get("name"):
            continue
        schema = stream.get("json_schema") or {}
        props = schema.get("properties") or {}
        out.append({"schema": "airbyte", "table": stream["name"],
                    "columns": [{"name": name,
                                 "type": _type(spec)}
                                for name, spec in props.items()]})
    if not out:
        raise ValueError("connector discovered no streams")
    return out


def _type(spec):
    if not isinstance(spec, dict):
        return "unknown"
    if isinstance(spec.get("type"), list):
        spec = {"type": (spec["type"] or ["unknown"])[0]}
    kind = str(spec.get("type") or "object")
    if kind == "integer":
        return "bigint"
    if kind == "number":
        return "double"
    if kind == "boolean":
        return "boolean"
    if kind == "array":
        return "array"
    if kind == "object":
        return "object"
    return "text"


def check(dsn, timeout=5):
    image, runtime, config = _parse(dsn)
    policy = _policy()
    policy["timeout_s"] = max(timeout, policy["timeout_s"])
    _allowed(image, runtime, policy)
    messages, _, _ = _stream(image, runtime, config, "check",
                             policy=policy)
    for message in messages:
        if message.get("type") == "CONNECTION_STATUS":
            status = (message.get("connectionStatus") or {})
            if status.get("status") == "SUCCEEDED":
                return True
            raise ValueError(status.get("message") or "connector check failed")
    raise ValueError("connector returned no connection status")


class AirbyteSource(Source):
    def __init__(self, ds, dag):
        from odf.services.datasource import get_dsn
        self.image, self.runtime, self.config = _parse(get_dsn(ds))
        table = dag.get("source_table") or ""
        self.stream = table.split(".", 1)[-1]
        self.cursor_column = dag.get("cursor_column") or ""
        self.policy = _policy()
        _allowed(self.image, self.runtime, self.policy)

    def read(self, cursor, limit):
        state = None
        if cursor:
            try:
                state = json.loads(cursor)
            except ValueError:
                state = None
        messages, _, _ = _stream(self.image, self.runtime, self.config,
                                 "discover", policy=self.policy)
        catalog = _catalog_from(messages)
        stream = None
        for item in catalog.get("streams") or []:
            if item.get("name") == self.stream:
                stream = item
                break
        if not stream:
            raise ValueError("stream not found: %s" % self.stream)
        wanted = {"streams": [{"stream": stream,
                               "sync_mode": "full_refresh",
                               "destination_sync_mode": "append"}]}
        if self.cursor_column:
            wanted["streams"][0]["sync_mode"] = "incremental"
            wanted["streams"][0]["cursor_field"] = [self.cursor_column]
        with tempfile.NamedTemporaryFile(
                prefix="odf-airbyte-err-", delete=False) as err:
            err_path = err.name
        try:
            _, rows, new_state = _stream(
                self.image, self.runtime, self.config, "read",
                catalog=wanted, state=state, limit=limit,
                policy=self.policy, stderr_path=err_path)
        finally:
            try:
                os.unlink(err_path)
            except OSError:
                pass
        if new_state is None:
            return rows, cursor
        return rows, json.dumps(new_state, sort_keys=True)
