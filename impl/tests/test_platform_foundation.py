import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.assets.service import DraftConflict, create_asset, update_draft
from odf.db import Base
from odf.models import (Asset, AssetVersion, Datasource, Flow, FlowVersion,
                        Interface, Job, Project, User)


def _session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(Project(id=1, code="p1", name="P1", status=1))
    session.add(User(id=1, username="u", password_hash="x", role="admin",
                     active=True))
    session.add(Datasource(id=1, project_id=1, name="one", kind="sqlite",
                           dsn_encrypted="x"))
    session.add(Datasource(id=2, project_id=1, name="two", kind="sqlite",
                           dsn_encrypted="x"))
    session.commit()
    return session


def test_page_assets_returns_total_and_slices():
    from odf.assets.service import page_assets
    s = _session()
    for i in range(60):
        create_asset(s, 1, "pipeline", "P%d" % i, {}, "u")
    rows, total, page, size = page_assets(s, 1, "pipeline", page=2,
                                          page_size=50)
    assert total == 60
    assert page == 2 and size == 50
    assert len(rows) == 10
    assert all(row.type == "pipeline" for row in rows)


def test_quality_custom_sql_and_anomaly_helpers():
    from odf.models import QualityResult, QualityRule
    from odf.services.quality import _anomaly_result, _custom_sql_result
    assert _custom_sql_result(0, {"expect": "zero"})[0] is True
    assert _custom_sql_result(2, {"expect": "zero"})[0] is False
    assert _custom_sql_result(2, {"expect": "nonzero"})[0] is True
    assert _custom_sql_result(5, {"expect": "max_rows", "value": 5})[0] is True
    assert _custom_sql_result(5, {"expect": "min_rows", "value": 6})[0] is False
    s = _session()
    rule = QualityRule(project_id=1, dataset_id=1, name="r",
                       kind="row_count_anomaly")
    s.add(rule)
    s.commit()
    for value in (100, 102, 98):
        s.add(QualityResult(rule_id=rule.id, status="pass",
                            detail_json={"rows": value}))
    s.commit()
    ok, detail = _anomaly_result(s, rule, 101, {"deviation_pct": 30})
    assert ok is True and detail["samples"] == 3
    ok, _ = _anomaly_result(s, rule, 500, {"deviation_pct": 30})
    assert ok is False


def test_alert_webhook_forwarding(monkeypatch):
    from odf.services import alerts as alert_service
    from odf.services import net
    captured = {}

    def fake_request(url, method="GET", body=None, **kwargs):
        captured["url"] = url
        captured["body"] = body
        return 200, {}, b""

    monkeypatch.setattr(net, "request", fake_request)
    monkeypatch.setattr(
        "odf.services.platform.get_doc",
        lambda session: {"alerts": {"webhook_url": "https://hooks.example/x"}})
    s = _session()
    row = alert_service.raise_alert(s, 1, "warning", "disk low",
                                    {"free": 3})
    assert row.id
    assert captured["url"] == "https://hooks.example/x"
    assert b"disk low" in captured["body"]


def test_notifications_list_and_read():
    from odf.services.notifications import list_for, mark_all_read, mark_read, notify
    s = _session()
    row = notify(s, 1, "publish", "已发布", "版本 v1", "/pipelines/1")
    out = list_for(s, 1, 1)
    assert out["items"][0]["id"] == row.id
    assert out["unread"] == 1
    mark_read(s, 1, 1, row.id)
    assert list_for(s, 1, 1)["unread"] == 0
    notify(s, 1, "alert", "告警")
    assert list_for(s, 1, 1)["unread"] == 1
    assert mark_all_read(s, 1, 1) == 1
    assert list_for(s, 1, 1)["unread"] == 0


def test_draft_conflict_rejects_stale_base_version():
    s = _session()
    asset = create_asset(s, 1, "dataset", "D", {}, "u")
    first = update_draft(s, asset.id, {"a": 1}, "u", base_version=1)
    assert first.version == 2
    with pytest.raises(DraftConflict):
        update_draft(s, asset.id, {"a": 2}, "u", base_version=1)
    second = update_draft(s, asset.id, {"a": 3}, "u", base_version=2)
    assert second.version == 3


def test_cancel_queued_job():
    from odf.services.jobs import cancel_job
    s = _session()
    asset = create_asset(s, 1, "pipeline", "P", {}, "u")
    job = Job(asset_id=asset.id, asset_type="pipeline", status="queued",
              attempts=0)
    s.add(job)
    s.commit()
    cancel_job(s, 1, job.id)
    s.refresh(job)
    assert job.status == "cancelled"
    assert job.cancel_requested is False


def test_migrate_legacy_flow_to_pipeline():
    from odf.services.legacy import migrate_flow
    s = _session()
    flow = Flow(project_id=1, name="legacy", cron="0 2 * * *", status=1)
    s.add(flow)
    s.flush()
    s.add(FlowVersion(flow_id=flow.id, version=1, created_by="u", dag_json={
        "source_ds_id": 1, "sink_ds_id": 2,
        "source_table": "src", "sink_table": "dst",
        "cursor_column": "id", "pk": "id", "batch": 200,
    }))
    s.commit()
    asset = migrate_flow(s, 1, flow.id, "u")
    assert asset.type == "pipeline"
    assert asset.cron == "0 2 * * *"
    version = s.get(AssetVersion, asset.draft_version_id)
    nodes = version.content_json["nodes"]
    assert [node["type"] for node in nodes] == ["source", "sink"]
    s.refresh(flow)
    assert flow.status == 0
    assert flow.migrated_asset_id == asset.id


def test_migrate_legacy_interface_to_api():
    from odf.services.legacy import migrate_interface
    s = _session()
    row = Interface(project_id=1, datasource_id=1, interface_key="iface_x",
                    name="legacy api", sql_text="select 1", status=1,
                    params_json=[])
    s.add(row)
    s.commit()
    asset = migrate_interface(s, 1, row.id, "u")
    assert asset.type == "api"
    assert asset.key == "iface_x"
    version = s.get(AssetVersion, asset.draft_version_id)
    assert version.content_json["mode"] == "sql"
    s.refresh(row)
    assert row.status == 0
    assert row.migrated_asset_id == asset.id


def test_sample_project_creates_published_assets(tmp_path, monkeypatch):
    import odf.filesource as filesource
    from odf.services.sample import create_sample
    monkeypatch.setattr(filesource, "_allowed_roots", lambda: [tmp_path])
    s = _session()
    result = create_sample(s, 1, "u")
    assert result["dashboard"]["id"]
    kinds = {a.type for a in s.query(Asset).filter_by(project_id=1).all()}
    assert {"pipeline", "dataset", "metric", "dashboard", "api"} <= kinds
    for kind in ("pipeline", "dataset", "metric", "dashboard", "api"):
        asset = (s.query(Asset)
                 .filter_by(project_id=1, type=kind).first())
        assert asset.published_version_id is not None
