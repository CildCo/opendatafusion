import io
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.db import Base, SessionLocal
from odf.main import app
from odf.models import FileObject, Project, User
from odf.services.auth import create_token
from odf.files import service


def _env(tmp_path, monkeypatch):
    monkeypatch.setattr(
        service, "get_settings",
        lambda: SimpleNamespace(file_dir=str(tmp_path),
                                file_max_mb=1))
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add_all([Project(id=1, code="f1", name="f1", status=1),
               Project(id=2, code="f2", name="f2", status=1)])
    s.commit()
    return s


def test_upload_dedupe_and_delete(tmp_path, monkeypatch):
    s = _env(tmp_path, monkeypatch)
    a = service.store_bytes(s, 1, "a.txt", "text/plain", b"hello", "u")
    b = service.store_bytes(s, 1, "b.txt", "text/plain", b"hello", "u")
    assert a["sha256"] == b["sha256"]
    assert s.query(FileObject).count() == 2
    files = [p for p in tmp_path.rglob("*") if p.is_file()]
    assert len(files) == 1
    service.delete_file(s, 1, a["id"], "u")
    assert len([p for p in tmp_path.rglob("*") if p.is_file()]) == 1
    service.delete_file(s, 1, b["id"], "u")
    assert len([p for p in tmp_path.rglob("*") if p.is_file()]) == 0


def test_size_and_project_scope(tmp_path, monkeypatch):
    s = _env(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        service.store_bytes(s, 1, "big.bin", "", b"x" * (1024 * 1024 + 1),
                            "u")
    out = service.store_bytes(s, 1, "a.txt", "text/plain", b"a", "u")
    with pytest.raises(ValueError):
        service.get_file(s, 2, out["id"])
    with pytest.raises(ValueError):
        service.delete_file(s, 2, out["id"], "u")
    assert service.safe_name("../../etc/passwd") == "passwd"


def _user(uid, role):
    with SessionLocal() as s:
        u = s.get(User, uid)
        if not u:
            u = User(id=uid, username="file%d" % uid, password_hash="x",
                     role=role, active=True)
            s.add(u)
        else:
            u.role = role
            u.active = True
        s.commit()


def test_file_routes(tmp_path, monkeypatch):
    _user(1, "admin")
    monkeypatch.setattr(
        service, "get_settings",
        lambda: SimpleNamespace(file_dir=str(tmp_path),
                                file_max_mb=1))
    c = TestClient(app)
    h = {"Authorization": "Bearer " + create_token(1, 1)}
    r = c.post("/api/v1/files",
               files={"file": ("hello.txt", io.BytesIO(b"hi"),
                               "text/plain")}, headers=h)
    assert r.status_code == 200
    fid = r.json()["id"]
    listed = c.get("/api/v1/files", headers=h).json()
    assert listed[0]["name"] == "hello.txt"
    down = c.get(f"/api/v1/files/{fid}/download", headers=h)
    assert down.status_code == 200 and down.content == b"hi"
    assert c.get(f"/api/v1/files/{fid}/download",
                 headers={"Authorization": "Bearer "
                          + create_token(1, 2)}).status_code == 404
    assert c.delete(f"/api/v1/files/{fid}", headers=h).status_code == 200


def test_store_recreates_missing_blob(tmp_path, monkeypatch):
    s = _env(tmp_path, monkeypatch)
    a = service.store_bytes(s, 1, "a.txt", "text/plain", b"heal", "u")
    for p in tmp_path.rglob("*"):
        if p.is_file():
            p.unlink()
    b = service.store_bytes(s, 1, "b.txt", "text/plain", b"heal", "u")
    assert a["sha256"] == b["sha256"]
    assert any(p.is_file() for p in tmp_path.rglob("*"))


def test_stream_upload_size_and_chunks(tmp_path, monkeypatch):
    import io as _io
    s = _env(tmp_path, monkeypatch)
    size = 512 * 1024 + 1
    out = service.store_stream(s, 1, "big.bin", "application/octet-stream",
                               _io.BytesIO(b"x" * size), "u")
    assert out["size"] == size
    f, chunks = service.open_file(s, 1, out["id"])
    total = sum(len(c) for c in chunks)
    assert total == size
    with pytest.raises(ValueError):
        service.store_stream(s, 1, "too.bin", "", _io.BytesIO(
            b"x" * (1024 * 1024 + 2)), "u")
