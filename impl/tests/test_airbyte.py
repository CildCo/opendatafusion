import json
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.connectors import airbyte
from odf.connectors.registry import build_dsn, masked_config
from odf.db import Base, SessionLocal
from odf.models import Datasource, Project
from odf.services.crypto import encrypt_secret
from odf.services.metadata import sync_datasource
from odf.services.platform import update_doc

SCRIPT = r'''
import json
import sys

args = sys.argv[1:]
command = args[0] if args else "spec"

def arg(name):
    if name in args:
        return args[args.index(name) + 1]
    return None

if command == "check":
    print(json.dumps({"type": "CONNECTION_STATUS",
                      "connectionStatus": {"status": "SUCCEEDED"}}))
elif command == "discover":
    print(json.dumps({"type": "CATALOG", "catalog": {"streams": [{
        "name": "users",
        "json_schema": {"type": "object", "properties": {
            "id": {"type": "integer"}, "name": {"type": "string"}}}}]}}))
elif command == "read":
    for i in range(1, 4):
        print(json.dumps({"type": "RECORD", "record": {
            "stream": "users", "data": {"id": i, "name": "u%d" % i}}}))
    print(json.dumps({"type": "STATE", "state": {"cursor": 3}}))
'''


def _dsn(tmp_path):
    script = tmp_path / "fake_airbyte.py"
    script.write_text(SCRIPT, encoding="utf-8")
    image = "%s %s" % (sys.executable, script)
    return image, build_dsn("airbyte", {
        "image": image, "runtime": "command",
        "config": json.dumps({"token": "secret"})})


def _enable(tmp_path):
    _, dsn = _dsn(tmp_path)
    image = json.loads(dsn)["image"]
    with SessionLocal() as s:
        update_doc(s, {"airbyte": {
            "enabled": True,
            "command_allowlist": sys.executable,
            "image_allowlist": "",
            "timeout_s": 30,
        }}, "test")


def test_discover_check_and_read(tmp_path):
    _enable(tmp_path)
    image, dsn = _dsn(tmp_path)
    assert image
    found = airbyte.tables(dsn)
    assert found[0]["table"] == "users"
    assert {c["name"] for c in found[0]["columns"]} == {"id", "name"}
    assert airbyte.check(dsn, 5) is True

    class DS:
        kind = "airbyte"
        dsn_encrypted = encrypt_secret(dsn)

    source = airbyte.AirbyteSource(DS(), {"source_table": "airbyte.users",
                                          "cursor_column": "id"})
    rows, cursor = source.read(None, 2)
    assert len(rows) == 2
    assert rows[0] == {"id": 1, "name": "u1"}
    assert json.loads(cursor) == {"cursor": 3}


def test_metadata_sync_and_masking(tmp_path):
    _enable(tmp_path)
    image, dsn = _dsn(tmp_path)
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Project(id=1, code="p", name="p", status=1))
    s.add(Datasource(id=1, project_id=1, name="ab", kind="airbyte",
                     dsn_encrypted=encrypt_secret(dsn)))
    s.commit()
    assert sync_datasource(s, 1) == 1
    config = masked_config("airbyte", dsn)
    assert config["config"] == ""
    assert config["has_config"] is True
    assert config["image"] == image


def test_command_runtime_requires_allowlist(tmp_path):
    _enable(tmp_path)
    _, dsn = _dsn(tmp_path)
    with SessionLocal() as s:
        update_doc(s, {"airbyte": {"command_allowlist": "/not/this"}}, "test")
    try:
        airbyte.tables(dsn)
    except ValueError as error:
        assert "allowlist" in str(error)
    else:
        raise AssertionError("unlisted command must fail")
