import uuid
from datetime import date, datetime, timezone

import pytest

from odf.db import SessionLocal
from odf.models import (ApiCallStat, Asset, AuditLog, Interface, Project,
                        QualityResult, QualityRule)
from odf.services import ratelimit
from odf.services.catalog import dataset_detail  # noqa: F401
from odf.services.quality import rule_summaries
from odf.services.interface import interface_history

PROJECT_ID = 916


def _project():
    with SessionLocal() as s:
        if not s.get(Project, PROJECT_ID):
            s.add(Project(id=PROJECT_ID, code="console-depth",
                          name="Console depth", status=1))
            s.commit()


def test_alert_rule_can_be_deleted():
    from odf.models import AlertRule
    from odf.services.alerts import create_rule, delete_rule

    _project()
    with SessionLocal() as s:
        rule = create_rule(s, PROJECT_ID, "rule-delete", "flow_health", {})
        delete_rule(s, PROJECT_ID, rule.id)
        assert s.get(AlertRule, rule.id) is None
        with pytest.raises(ValueError):
            delete_rule(s, PROJECT_ID, rule.id)


def test_api_stats_aggregate_days_and_keys():
    _project()
    with SessionLocal() as s:
        a = Asset(project_id=PROJECT_ID, type="api",
                  key=uuid.uuid4().hex, name="stats-api", owner="tester")
        s.add(a)
        s.commit()
        today = date.today()
        s.add_all([
            ApiCallStat(day=today, api_id=a.id, ak="ak1", count=4,
                        errors=1, total_ms=400),
            ApiCallStat(day=today, api_id=a.id, ak="ak2", count=2,
                        errors=0, total_ms=100),
            ApiCallStat(day=date(today.year, today.month, 1), api_id=a.id,
                        ak="ak1", count=10, errors=0, total_ms=1000),
        ])
        s.commit()
        out = ratelimit.stats_for_api(s, PROJECT_ID, a.id, days=7)
        assert out["total"]["count"] == 6
        assert out["total"]["errors"] == 1
        assert out["total"]["avg_ms"] == 83
        assert len(out["days"]) == 1
        assert {k["ak"] for k in out["keys"]} == {"ak1", "ak2"}
        assert ratelimit.stats_for_api(s, 9999, a.id, days=7) is None


def test_interface_history_lists_executions():
    _project()
    with SessionLocal() as s:
        iface = Interface(project_id=PROJECT_ID, datasource_id=1,
                          interface_key=uuid.uuid4().hex,
                          name="hist-iface", sql_text="select 1",
                          params_json=[], status=1)
        s.add(iface)
        s.commit()
        s.add(AuditLog(actor="openapi", action="query",
                       target=iface.interface_key,
                       detail_json={"rows": 3}))
        s.commit()
        rows = interface_history(s, PROJECT_ID, iface.id)
        assert rows[0]["detail"]["rows"] == 3
        assert rows[0]["actor"] == "openapi"
        assert interface_history(s, 9999, iface.id) is None


def test_quality_rule_summaries_carry_pass_rate():
    _project()
    with SessionLocal() as s:
        rule = QualityRule(project_id=PROJECT_ID, dataset_id=1,
                           name="summary-rule", kind="not_null",
                           column_name="id")
        s.add(rule)
        s.commit()
        now = datetime.now(timezone.utc)
        s.add_all([
            QualityResult(rule_id=rule.id, status="pass", detail_json={},
                          at=now),
            QualityResult(rule_id=rule.id, status="pass", detail_json={},
                          at=now),
            QualityResult(rule_id=rule.id, status="fail", detail_json={},
                          at=now),
        ])
        s.commit()
        rows = rule_summaries(s, PROJECT_ID)
        row = next(r for r in rows if r["id"] == rule.id)
        assert row["last_status"] == "fail"
        assert row["pass_rate"] == 67
        assert row["last_at"]


def test_connector_detail_parses_tasks_and_traces():
    from odf.cdc.service import parse_connector_status

    payload = {
        "connector": {"state": "RUNNING"},
        "tasks": [
            {"id": 0, "state": "RUNNING"},
            {"id": 1, "state": "FAILED",
             "trace": "java.lang.IllegalStateException: boom"},
        ],
    }
    out = parse_connector_status(payload)
    assert out["state"] == "RUNNING"
    assert len(out["tasks"]) == 2
    assert out["tasks"][1]["trace"].startswith("java.lang")
    assert out["failed_tasks"] == 1


def test_audit_list_shows_usernames_for_numeric_actors():
    from odf.models import AuditLog, User
    from odf.services.audit import list_audit

    _project()
    with SessionLocal() as s:
        u = s.get(User, 9902)
        if not u:
            u = User(id=9902, username="audit-actor", password_hash="x",
                     role="admin", active=True)
            s.add(u)
        s.commit()
        s.add(AuditLog(actor="9902", action="probe", target="1",
                       detail_json={}))
        s.commit()
        rows = list_audit(s, 5)
        assert rows[0]["actor"] == "audit-actor"


def test_portal_menu_set_covers_console_pages():
    from odf.portal.service import MENUS

    assert {"/engines", "/cdc", "/interfaces"} <= MENUS


def test_engine_job_shows_submitter_name():
    from odf.models import EngineJob, User
    from odf.services.engine_jobs import job_out

    _project()
    with SessionLocal() as s:
        user = s.get(User, 9903)
        if not user:
            user = User(id=9903, username="engine-actor", password_hash="x",
                        role="editor", active=True)
            s.add(user)
            s.commit()
        job = EngineJob(project_id=PROJECT_ID, engine="spark",
                        name="probe-%s" % uuid.uuid4().hex[:6],
                        submitted_by="9903")
        s.add(job)
        s.commit()
        assert job_out(job, s)["submitted_by"] == "engine-actor"


def test_engine_jobs_route_resolves_submitter():
    from fastapi.testclient import TestClient

    from odf.main import app
    from odf.models import User
    from odf.services.auth import create_token

    _project()
    with SessionLocal() as s:
        user = s.get(User, 9903)
        if not user:
            user = User(id=9903, username="engine-actor", password_hash="x",
                        role="editor", active=True)
            s.add(user)
            s.commit()
    client = TestClient(app)
    r = client.get("/api/v1/engine/jobs",
                   headers={"Authorization":
                            "Bearer " + create_token(9903, PROJECT_ID)})
    assert r.status_code == 200
    assert any(j["submitted_by"] == "engine-actor" for j in r.json())


def test_proposed_change_can_be_withdrawn():
    from odf.services.changes import propose, withdraw

    _project()
    with SessionLocal() as s:
        change = propose(s, PROJECT_ID, "tester", "pause_flow", 1, {})
        withdrawn = withdraw(s, change.id, "tester", PROJECT_ID)
        assert withdrawn.status == "withdrawn"
        with pytest.raises(ValueError):
            withdraw(s, change.id, "tester", PROJECT_ID)


def test_change_withdraw_route_is_project_scoped():
    from fastapi.testclient import TestClient

    from odf.main import app
    from odf.services.auth import create_token
    from odf.services.changes import propose

    _project()
    with SessionLocal() as s:
        from odf.models import User
        if not s.get(User, 9901):
            s.add(User(id=9901, username="change-requester", password_hash="x",
                       role="editor", active=True))
            s.commit()
        change = propose(s, PROJECT_ID, "9901", "pause_flow", 1, {})
    client = TestClient(app)
    own = {"Authorization": "Bearer " + create_token(9901, PROJECT_ID)}
    ok = client.post(f"/api/v1/changes/{change.id}/withdraw", headers=own)
    assert ok.status_code == 200
    assert ok.json()["status"] == "withdrawn"
    again = client.post(f"/api/v1/changes/{change.id}/withdraw", headers=own)
    assert again.status_code == 400


def test_audit_filters_and_csv_export():
    from fastapi.testclient import TestClient

    from odf.main import app
    from odf.models import AuditLog, User
    from odf.services.audit import list_audit
    from odf.services.auth import create_token

    _project()
    with SessionLocal() as s:
        u = s.get(User, 9904)
        if not u:
            u = User(id=9904, username="audit-admin", password_hash="x",
                     role="admin", active=True)
            s.add(u)
        s.commit()
        s.add(AuditLog(actor="9904", action="probe_csv", target="target-a",
                       detail_json={"k": 1}))
        s.commit()
        rows = list_audit(s, 10, q="probe_csv")
        assert rows and rows[0]["action"] == "probe_csv"
        assert list_audit(s, 10, actor="audit-admin")[0]["actor"] == "audit-admin"
    client = TestClient(app)
    headers = {"Authorization": "Bearer " + create_token(9904, PROJECT_ID)}
    resp = client.get("/api/v1/audit/export?q=probe_csv", headers=headers)
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "probe_csv" in resp.text
    assert resp.text.splitlines()[0].startswith("id,actor,action,target,at")


def test_interface_stats_aggregate_calls():
    from odf.models import Interface
    from odf.services.interface import interface_stats

    _project()
    with SessionLocal() as s:
        iface = Interface(project_id=PROJECT_ID, datasource_id=1,
                          interface_key=uuid.uuid4().hex,
                          name="stats-iface", sql_text="select 1",
                          params_json=[], status=1)
        s.add(iface)
        s.commit()
        s.add_all([
            AuditLog(actor="openapi", action="query",
                     target=iface.interface_key, detail_json={"rows": 3}),
            AuditLog(actor="openapi", action="query",
                     target=iface.interface_key, detail_json={"rows": 5}),
        ])
        s.commit()
        out = interface_stats(s, PROJECT_ID, iface.id, days=7)
        assert out["total"]["calls"] == 2
        assert out["total"]["rows"] == 8
        assert out["days"][0]["calls"] == 2
        assert interface_stats(s, 9999, iface.id, days=7) is None


def test_mute_rule_suppresses_matching_alerts():
    from odf.models import Alert, AlertRule
    from odf.services.alerts import create_rule, raise_alert

    _project()
    with SessionLocal() as s:
        create_rule(s, PROJECT_ID, "mute-spam", "mute",
                    {"title_contains": "spam"})
        suppressed = raise_alert(s, PROJECT_ID, "warning", "spam event")
        assert suppressed is None
        assert (s.query(Alert).filter_by(project_id=PROJECT_ID,
                                         title="spam event").first() is None)
        kept = raise_alert(s, PROJECT_ID, "warning", "real event")
        assert kept is not None and kept.title == "real event"
        s.query(Alert).filter_by(project_id=PROJECT_ID,
                                 title="real event").delete()
        s.query(AlertRule).filter_by(project_id=PROJECT_ID,
                                     name="mute-spam").delete()
        s.commit()


def test_mysql_connector_payload():
    from odf.cdc.service import connector_payload

    payload = connector_payload(
        {"engine": "mysql", "host": "db", "user": "u", "database": "shop",
         "schema_list": "shop", "table_list": "shop.orders"}, "pw")
    assert payload["connector.class"].endswith("MySqlConnector")
    assert payload["database.hostname"] == "db"
    assert payload["database.port"] == "3306"
    assert payload["database.include.list"] == "shop"
    assert payload["table.include.list"] == "shop.orders"
    assert payload["database.server.id"].isdigit()
    assert payload["database.password"] == "pw"
    assert (payload["schema.history.internal.kafka.bootstrap.servers"]
            == "kafka:9092")
    assert (payload["schema.history.internal.kafka.topic"]
            == "schema-history-odf")


def test_oracle_connector_payload():
    from odf.cdc.service import connector_payload

    payload = connector_payload(
        {"engine": "oracle", "host": "db", "user": "ODF", "database": "ORCL",
         "schema_list": "ODF", "table_list": "ODF.EVENTS"}, "pw")
    assert payload["connector.class"].endswith("OracleConnector")
    assert payload["database.port"] == "1521"
    assert payload["database.dbname"] == "ORCL"
    assert payload["database.connector"] == "logminer"
    assert payload["schema.include.list"] == "ODF"
    assert payload["table.include.list"] == "ODF.EVENTS"
    assert (payload["schema.history.internal.kafka.topic"]
            == "schema-history-odf")


def test_unknown_cdc_engine_is_rejected():
    import pytest as _pytest

    from odf.cdc.service import connector_payload

    with _pytest.raises(ValueError):
        connector_payload({"engine": "db2", "host": "h", "user": "u",
                           "database": "d"}, "pw")
