from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.db import Base
from odf.lakehouse import schedule as schedule_service
from odf.lakehouse.service import health, time_travel
from odf.models import Datasource, Job, LakehouseMaintenance, Project
from odf.services.crypto import encrypt_secret


def _env():
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Project(id=1, code="p", name="P", status=1))
    s.add(Datasource(id=1, project_id=1, name="lake", kind="trino",
                     dsn_encrypted=encrypt_secret(
                         "trino://u@trino:8080/iceberg/odf_p1")))
    s.commit()
    return s


def test_schedule_crud_due_and_job(tmp_path, monkeypatch):
    s = _env()
    row = schedule_service.upsert(
        s, 1, 1, "odf_p1", "orders", "0 0 3 * * *", True, True, True,
        "7d", "128MB", "admin")
    assert row["schema_name"] == "odf_p1"
    assert schedule_service.list_schedules(s, 1)[0]["cron"] == "0 0 3 * * *"
    record = s.get(LakehouseMaintenance, row["id"])
    record.last_run_at = datetime.now(timezone.utc) - timedelta(days=2)
    s.commit()
    assert [x.id for x in schedule_service.due(
        s, datetime.now(timezone.utc))] == [row["id"]]
    job = schedule_service.enqueue(s, record)
    assert job.project_id == 1
    assert schedule_service.enqueue(s, record).id == job.id

    called = {}

    def fake_maintain(client, schema, tables, optimize, expire, retention,
                      threshold):
        called["tables"] = tables
        return [{"table": tables[0], "optimize": "ok", "expire": "ok"}]

    monkeypatch.setattr(schedule_service, "maintain", fake_maintain)
    monkeypatch.setattr(schedule_service, "client_for_datasource",
                        lambda ds: object())
    from odf.services.jobs import process_job
    process_job(s, job, "worker")
    s.refresh(job)
    assert job.status == "success"
    assert called["tables"] == ["orders"]
    assert s.get(LakehouseMaintenance, row["id"]).last_status == "ok"


class _Client:
    catalog = "iceberg"

    def __init__(self):
        self.sql = []

    def query(self, sql, max_rows=100):
        self.sql.append(sql)
        if "$files" in sql:
            return {"rows": [
                {"file_path": "a", "file_size_in_bytes": 100,
                 "record_count": 1},
                {"file_path": "b", "file_size_in_bytes": 200,
                 "record_count": 1},
                {"file_path": "c", "file_size_in_bytes": 300,
                 "record_count": 1},
            ]}
        if "$snapshots" in sql:
            return {"rows": [{"snapshot_id": 1, "committed_at": "now"},
                             {"snapshot_id": 2, "committed_at": "now"}]}
        if "$partitions" in sql:
            return {"rows": [{"partition": "p", "file_count": 3,
                              "record_count": 3, "total_size": 600}]}
        return {"columns": ["id"], "rows": [{"id": 1}], "row_count": 1}


def test_health_and_time_travel():
    client = _Client()
    out = health(client, "odf_p1", "orders")
    assert out["files"] == 3
    assert out["size_bytes"] == 600
    assert out["snapshots"] == 2
    assert out["status"] in ("ok", "warning")
    result = time_travel(client, "odf_p1", "orders", snapshot_id=7)
    assert result["rows"] == [{"id": 1}]
    assert "FOR VERSION AS OF 7" in client.sql[-1]
