import pytest

from odf.db import SessionLocal
from odf.models import (Column, Dataset, DatasetTag, Datasource, Project,
                        QualityResult, QualityRule, Tag)
from odf.services.crypto import encrypt_secret
from odf.services.datasource import (DatasourceInUse, delete_datasource,
                                     get_dsn, update_datasource)
from odf.services.quality import delete_rule


def _project(pid):
    with SessionLocal() as s:
        if not s.get(Project, pid):
            s.add(Project(id=pid, code="life%d" % pid, name="life"))
            s.commit()


def _datasource(s, pid=931):
    ds = Datasource(project_id=pid, name="before", kind="sqlite",
                    dsn_encrypted=encrypt_secret("sqlite:///old.db"))
    s.add(ds)
    s.commit()
    s.refresh(ds)
    return ds


def test_update_datasource_renames_and_reencrypts():
    _project(931)
    with SessionLocal() as s:
        ds = _datasource(s)
        update_datasource(s, 931, ds.id, name="after",
                          dsn="sqlite:///new.db")
        assert ds.name == "after"
        assert get_dsn(ds) == "sqlite:///new.db"
    with SessionLocal() as s:
        ds = s.query(Datasource).filter_by(project_id=931).first()
        s.query(Dataset).filter_by(datasource_id=ds.id).delete()
        s.delete(ds)
        s.commit()


def test_delete_datasource_requires_force_when_governed():
    _project(931)
    with SessionLocal() as s:
        ds = _datasource(s)
        d = Dataset(datasource_id=ds.id, schema_name="main", table_name="t")
        s.add(d)
        s.commit()
        s.add(Column(dataset_id=d.id, name="id", data_type="INTEGER"))
        service_tag = Tag(project_id=931, name="life-tag")
        s.add(service_tag)
        s.commit()
        s.add(DatasetTag(dataset_id=d.id, tag_id=service_tag.id))
        rule = QualityRule(project_id=931, dataset_id=d.id, name="r",
                           kind="not_null", column_name="id", config_json={})
        s.add(rule)
        s.commit()
        s.add(QualityResult(rule_id=rule.id, status="pass", detail_json={}))
        s.commit()
        dsid, did, rid = ds.id, d.id, rule.id
    with SessionLocal() as s:
        with pytest.raises(DatasourceInUse) as info:
            delete_datasource(s, 931, dsid)
        assert info.value.blockers["quality_rules"] == 1
        blockers = delete_datasource(s, 931, dsid, force=True)
        assert blockers["tags"] == 1
    with SessionLocal() as s:
        assert s.get(Datasource, dsid) is None
        assert s.get(Dataset, did) is None
        assert s.query(Column).filter_by(dataset_id=did).count() == 0
        assert s.query(DatasetTag).filter_by(dataset_id=did).count() == 0
        assert s.query(QualityRule).filter_by(id=rid).count() == 0
        assert s.query(QualityResult).filter_by(rule_id=rid).count() == 0


def test_delete_quality_rule_removes_results():
    _project(932)
    with SessionLocal() as s:
        ds = Datasource(project_id=932, name="q", kind="sqlite",
                        dsn_encrypted=encrypt_secret("sqlite:///q.db"))
        s.add(ds)
        s.commit()
        d = Dataset(datasource_id=ds.id, schema_name="main", table_name="t")
        s.add(d)
        s.commit()
        rule = QualityRule(project_id=932, dataset_id=d.id, name="r",
                           kind="not_null", column_name="id", config_json={})
        s.add(rule)
        s.commit()
        s.add(QualityResult(rule_id=rule.id, status="pass", detail_json={}))
        s.commit()
        rid = rule.id
    with SessionLocal() as s:
        delete_rule(s, 932, rid)
        assert s.get(QualityRule, rid) is None
        assert s.query(QualityResult).filter_by(rule_id=rid).count() == 0
        with pytest.raises(ValueError):
            delete_rule(s, 932, rid)
