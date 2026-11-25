from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.assets.service import create_asset
from odf.db import Base
from odf.models import Project
from odf.services.doctor import check, check_backup


def _env():
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Project(id=1, code="p", name="P", status=1))
    s.commit()
    return s


def test_doctor_reports_counts_and_database():
    s = _env()
    create_asset(s, 1, "pipeline", "p", {"nodes": [], "edges": []}, "admin")
    out = check(s)
    assert out["database"]["reachable"] is True
    assert out["counts"]["projects"] == 1
    assert out["counts"]["assets"]["pipeline"] == 1
    assert "migrations" in out
    assert out["disk"]["path"]
    assert set(out["retention_days"]) == {"query_run", "job", "notification",
                                          "alert", "webhook_delivery",
                                          "contract_check"}


def test_backup_check_accepts_sql_dump(tmp_path):
    path = tmp_path / "dump.sql"
    path.write_text("CREATE TABLE demo (id int);\n", encoding="utf-8")
    out = check_backup(str(path))
    assert out["ok"] is True
    assert out["kind"] == "plain"


def test_backup_check_rejects_missing_and_empty(tmp_path):
    assert check_backup(str(tmp_path / "missing.sql"))["ok"] is False
    empty = tmp_path / "empty.gz"
    empty.write_bytes(b"")
    assert check_backup(str(empty))["ok"] is False


def test_backup_check_reads_gzip(tmp_path):
    import gzip
    path = tmp_path / "dump.sql.gz"
    with gzip.open(path, "wb") as handle:
        handle.write(b"CREATE TABLE demo (id int);\n")
    out = check_backup(str(path))
    assert out["ok"] is True
    assert out["kind"] == "gzip"
