from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.db import Base
from odf.models import (Dataset, Datasource, Project, QualityResult,
                        QualityRule)
from odf.services.crypto import encrypt_secret
from odf.services.quality import trends


def _env():
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Project(id=1, code="p", name="P", status=1))
    s.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                     dsn_encrypted=encrypt_secret("sqlite://")))
    s.add(Dataset(id=1, datasource_id=1, schema_name="main",
                  table_name="t"))
    s.commit()
    return s


def _rule(s, name="r", sla=None):
    return QualityRule(project_id=1, dataset_id=1, name=name, kind="null",
                       column_name="v", enabled=True,
                       config_json={"sla_percent": sla} if sla else {})


def test_trends_rate_streak_and_sla():
    s = _env()
    rule = _rule(s, sla=90)
    s.add(rule)
    s.commit()
    now = datetime.now(timezone.utc)
    for index, status in enumerate(["fail", "fail", "pass", "pass"]):
        s.add(QualityResult(rule_id=rule.id, status=status,
                            detail_json={},
                            at=now - timedelta(days=index)))
    s.commit()
    out = trends(s, 1, 30)
    row = out["rules"][0]
    assert row["runs"] == 4
    assert row["pass_rate"] == 50
    assert row["streak"] == 2
    assert row["below_sla"] is True
    assert len(row["series"]) >= 1
    assert sum(item["pass"] for item in out["daily"]) == 2


def test_trends_without_results():
    s = _env()
    s.add(_rule(s))
    s.commit()
    row = trends(s, 1, 30)["rules"][0]
    assert row["runs"] == 0
    assert row["pass_rate"] is None
    assert row["streak"] == 0
    assert row["below_sla"] is False
