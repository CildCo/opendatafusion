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
