import uuid

import pytest

from odf.models import Dataset, Datasource, QualityRule
from odf.services.crypto import encrypt_secret
from odf.services.quality import create_rule, run_rule


@pytest.fixture()
def session():
    from odf.db import SessionLocal
    with SessionLocal() as s:
        yield s


def _trino_dataset(session):
    ds = Datasource(project_id=1, name="lq-%s" % uuid.uuid4().hex[:6],
                    kind="trino",
                    dsn_encrypted=encrypt_secret(
                        "trino://odf@trino:8080/iceberg/odf_bench"))
    session.add(ds)
    session.commit()
    session.refresh(ds)
    data = Dataset(datasource_id=ds.id, schema_name="odf_bench",
                   table_name="events")
    session.add(data)
    session.commit()
    session.refresh(data)
    return ds, data


def _patch_query(monkeypatch, rows):
    calls = []

    def fake(session_, ds, sql, params=None, max_rows=1000, **kw):
        calls.append(sql)
        return {"columns": list(rows[0]) if rows else [],
                "rows": rows, "row_count": len(rows), "truncated": False}

    monkeypatch.setattr("odf.services.query.execute_query", fake)
    return calls


def test_not_null_rule_runs_on_trino(session, monkeypatch):
    ds, data = _trino_dataset(session)
    calls = _patch_query(monkeypatch, [{"n": 0}])
    rule = create_rule(session, 1, data.id, "id not null", "not_null", "id")

    result = run_rule(session, rule.id, 1)

    assert result.status == "pass"
    assert result.detail_json == {"nulls": 0}
    assert calls and "IS NULL" in calls[0]
    assert '"odf_bench"."events"' in calls[0]


def test_row_count_rule_runs_on_trino(session, monkeypatch):
    ds, data = _trino_dataset(session)
    _patch_query(monkeypatch, [{"n": 60000000}])
    rule = create_rule(session, 1, data.id, "row count", "row_count",
                       config={"min": 1000})

    result = run_rule(session, rule.id, 1)

    assert result.status == "pass"
    assert result.detail_json["rows"] == 60000000


def test_failing_rule_is_recorded(session, monkeypatch):
    ds, data = _trino_dataset(session)
    _patch_query(monkeypatch, [{"n": 5}])
    rule = create_rule(session, 1, data.id, "nulls", "not_null", "id")

    result = run_rule(session, rule.id, 1)

    assert result.status == "fail"
    assert result.detail_json == {"nulls": 5}
