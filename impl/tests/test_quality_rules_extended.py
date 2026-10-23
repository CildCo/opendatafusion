from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from odf.db import Base
from odf.models import Dataset, Datasource, Project, QualityRule
from odf.services.crypto import encrypt_secret
from odf.services.metadata import sync_datasource
from odf.services.quality import run_rule


def _env(tmp_path):
    url = "sqlite:///" + str(tmp_path / "q.db")
    now = datetime.now(timezone.utc)
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table events "
                       "(id int, email text, ts text, stale text, "
                       "status text)"))
        c.execute(text(
            "insert into events values (:id,:email,:ts,:stale,:status)"),
            [
                {"id": 1, "email": "a@example.com",
                 "ts": now.isoformat(), "stale": "2020-01-01T00:00:00",
                 "status": "ok"},
                {"id": 2, "email": "bad-email",
                 "ts": (now - timedelta(minutes=5)).isoformat(),
                 "stale": "2020-01-01T00:00:00", "status": "bad"},
            ])
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Project(id=1, code="q", name="q", status=1))
    s.add(Datasource(id=1, project_id=1, name="q", kind="sqlite",
                     dsn_encrypted=encrypt_secret(url)))
    s.commit()
    sync_datasource(s, 1)
    ds = s.query(Dataset).filter_by(datasource_id=1).first()
    return s, ds


def _rule(s, ds, kind, column=None, **config):
    r = QualityRule(project_id=1, dataset_id=ds.id, name=kind, kind=kind,
                    column_name=column, config_json=config, enabled=True)
    s.add(r)
    s.commit()
    return r


def test_freshness_rule(tmp_path):
    s, ds = _env(tmp_path)
    good = _rule(s, ds, "freshness", "ts", max_age_hours=1)
    bad = _rule(s, ds, "freshness", "stale", max_age_hours=1)
    assert run_rule(s, good.id).status == "pass"
    out = run_rule(s, bad.id)
    assert out.status == "fail" and out.detail_json["max_age_hours"] == 1


def test_regex_and_accepted_values(tmp_path):
    s, ds = _env(tmp_path)
    regex = _rule(s, ds, "regex", "email", pattern=r"^[^@]+@[^@]+$")
    accepted = _rule(s, ds, "accepted_values", "status",
                     values=["ok"], allow_null=False)
    assert run_rule(s, regex.id).status == "fail"
    out = run_rule(s, accepted.id)
    assert out.status == "fail" and out.detail_json["invalid"] == 1


def test_schema_rule(tmp_path):
    s, ds = _env(tmp_path)
    good = _rule(s, ds, "schema", expected=["id", "email", "ts", "stale",
                                            "status"])
    bad = _rule(s, ds, "schema", expected=["id", "email", "missing"])
    assert run_rule(s, good.id).status == "pass"
    out = run_rule(s, bad.id)
    assert out.status == "fail"
    assert out.detail_json["missing"] == ["missing"]


def test_accepted_values_allows_nulls_when_configured(tmp_path):
    s, ds = _env(tmp_path)
    r = _rule(s, ds, "accepted_values", "status", values=["ok", "bad"])
    assert run_rule(s, r.id).status == "pass"
