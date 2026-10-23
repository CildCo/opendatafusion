import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from odf.assets.service import create_asset
from odf.db import Base
from odf.models import AuditLog, Datasource, Flow, Interface, Project
from odf.services.approval import issue_token
from odf.services.changes import apply, propose
from odf.services.crypto import encrypt_secret

PIPE = {"nodes": [
    {"id": "s", "type": "source",
     "config": {"datasource_id": 1, "table": "t", "pk": "id"}},
    {"id": "o", "type": "sink",
     "config": {"datasource_id": 1, "table": "t", "pk": ["id"]}}],
    "edges": [{"from": "s", "to": "o"}]}


@pytest.fixture()
def s(tmp_path):
    url = "sqlite:///" + str(tmp_path / "change.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table t (id int)"))
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    with sessionmaker(bind=e)() as session:
        session.add(Project(id=1, code="p", name="p", status=1))
        session.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                               dsn_encrypted=encrypt_secret(url)))
        session.commit()
        yield session


def test_pause_flow_change(s):
    f = Flow(project_id=1, name="copy", cron="0 */5 * * * ?", status=1)
    s.add(f)
    s.commit()
    c = propose(s, 1, "actor", "pause_flow", f.id)
    apply(s, c.id, issue_token(f.id, "pause_flow"))
    s.refresh(f)
    assert f.status == 0


def test_publish_interface_change(s):
    i = Interface(project_id=1, datasource_id=1, interface_key="k",
                  name="i", sql_text="select 1", params_json=[],
                  output_json=[], status=0)
    s.add(i)
    s.commit()
    c = propose(s, 1, "actor", "publish_interface", i.id)
    apply(s, c.id, issue_token(i.id, "publish_interface"))
    s.refresh(i)
    assert i.status == 1


def test_wrong_token_rejected(s):
    f = Flow(project_id=1, name="copy", cron="0 */5 * * * ?", status=1)
    s.add(f)
    s.commit()
    c = propose(s, 1, "actor", "pause_flow", f.id)
    with pytest.raises(PermissionError):
        apply(s, c.id, issue_token(f.id, "resume_flow"))


def test_rollback_flow_change(s):
    f = Flow(project_id=1, name="copy", cron="0 */5 * * * ?", status=1)
    s.add(f)
    s.commit()
    c = propose(s, 1, "actor", "rollback_flow", f.id, {"version": 3})
    apply(s, c.id, issue_token(f.id, "rollback_flow"))
    s.refresh(f)
    assert f.current_version == 3


def test_pipeline_publish_change_requires_token_and_is_audited(s):
    a = create_asset(s, 1, "pipeline", "p", PIPE, "actor")
    c = propose(s, 1, "actor", "publish_pipeline", a.id)
    with pytest.raises(PermissionError):
        apply(s, c.id, issue_token(a.id, "rollback_pipeline"))
    apply(s, c.id, issue_token(a.id, "publish_pipeline"))
    s.refresh(a)
    assert a.published_version_id is not None
    assert s.query(AuditLog).filter_by(
        action="publish_pipeline", target=str(a.id)).count() == 1
