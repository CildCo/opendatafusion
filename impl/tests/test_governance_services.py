from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.db import Base
from odf.models import (Asset, Column, Dataset, Datasource, Project,
                        QualityRule, User)


def _session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(Project(id=1, code="p1", name="P1", status=1,
                        quota_json={"max_assets": 1, "max_jobs": 1}))
    session.add(User(id=1, username="u", password_hash="x", role="editor",
                     active=True))
    session.commit()
    return session


def test_quota_blocks_assets_and_jobs():
    from odf.services.quota import check_asset, check_job, usage
    s = _session()
    check_asset(s, 1)
    s.add(Asset(project_id=1, type="pipeline", key="p", name="p",
                owner="u", enabled=True))
    s.commit()
    try:
        check_asset(s, 1)
        assert False
    except ValueError as error:
        assert "asset quota" in str(error)
    check_job(s, 1)
    from odf.services.jobs import enqueue_asset
    asset = s.query(Asset).first()
    enqueue_asset(s, asset.id, "pipeline")
    try:
        check_job(s, 1)
        assert False
    except ValueError as error:
        assert "job quota" in str(error)
    assert usage(s, 1)["assets"] == 1


def test_datasource_health_records_history():
    from odf.models import DatasourceHealth
    from odf.services.datasource_health import record, recent
    s = _session()
    ds = Datasource(project_id=1, name="ds", kind="sqlite",
                    dsn_encrypted="x")
    s.add(ds)
    s.commit()
    record(s, ds.id, "test", True, "", 12)
    record(s, ds.id, "sync", False, "boom", 30)
    rows = recent(s, ds.id)
    assert [row["status"] for row in rows] == ["failed", "ok"]
    assert rows[0]["error"] == "boom"


def test_delete_datasource_removes_health_history():
    from odf.models import DatasourceHealth
    from odf.services.datasource import delete_datasource
    from odf.services.datasource_health import record
    s = _session()
    ds = Datasource(project_id=1, name="ds", kind="sqlite",
                    dsn_encrypted="x")
    s.add(ds)
    s.commit()
    record(s, ds.id, "test", True, "", 5)
    delete_datasource(s, 1, ds.id, force=True)
    assert (s.query(DatasourceHealth)
            .filter_by(datasource_id=ds.id).count()) == 0


def test_pii_scan_finds_and_masks_columns(monkeypatch):
    from odf.models import ColumnPolicy
    from odf.services import pii
    s = _session()
    ds = Datasource(project_id=1, name="ds", kind="sqlite",
                    dsn_encrypted="x")
    s.add(ds)
    s.commit()
    dataset = Dataset(datasource_id=ds.id, schema_name="main", table_name="t")
    s.add(dataset)
    s.flush()
    s.add(Column(dataset_id=dataset.id, name="email", data_type="TEXT"))
    s.add(Column(dataset_id=dataset.id, name="amount", data_type="INTEGER"))
    s.commit()
    monkeypatch.setattr("odf.services.catalog.dataset_sample",
                        lambda *args, **kwargs: {
                            "rows": [{"email": "a@example.com", "amount": 1},
                                     {"email": "b@example.com", "amount": 2}]})
    result = pii.scan(s, 1, dataset.id)
    assert [f["column"] for f in result["findings"]] == ["email"]
    applied = pii.apply(s, 1, dataset.id, "tester")
    assert applied["applied"] == 1
    policy = s.query(ColumnPolicy).filter_by(column_name="email").first()
    assert policy and policy.source == "scan"


def test_backup_export_and_restore_roundtrip():
    from odf.services.backup import export_bytes, restore
    s = _session()
    s.add(Asset(project_id=1, type="pipeline", key="p", name="p",
                owner="u", enabled=True))
    s.commit()
    payload = export_bytes(s)
    s.query(Asset).delete()
    s.commit()
    counts = restore(s, payload, "tester")
    assert counts["asset"] == 1
    assert s.query(Asset).count() == 1


def test_quality_schedule_fields_roundtrip():
    from odf.services.quality import rule_summaries
    s = _session()
    ds = Datasource(project_id=1, name="ds", kind="sqlite",
                    dsn_encrypted="x")
    s.add(ds)
    s.commit()
    dataset = Dataset(datasource_id=ds.id, schema_name="main", table_name="t")
    s.add(dataset)
    s.flush()
    s.add(QualityRule(project_id=1, dataset_id=dataset.id, name="r",
                      kind="not_null", column_name="id", config_json={},
                      schedule_cron="0 2 * * *", alert_on_fail=True,
                      enabled=True))
    s.commit()
    row = rule_summaries(s, 1)[0]
    assert row["schedule_cron"] == "0 2 * * *"
    assert row["alert_on_fail"] is True
