import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from odf.assets.service import create_asset
from odf.db import Base
from odf.models import AuditLog, Datasource, Project
from odf.services.approval import issue_token
from odf.services.changes import apply, propose
from odf.services.crypto import encrypt_secret

VALID = {
    "mode": "visual",
    "query": {"datasource_id": 1, "table": "t",
              "select": [{"column": "id"}]},
    "sql": None, "params": [], "auth": {"type": "aksk",
                                        "rate_limit_per_min": 60},
}


@pytest.fixture()
def s(tmp_path):
    url = "sqlite:///" + str(tmp_path / "ch.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table t (id int)"))
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    sess = sessionmaker(bind=e)()
    sess.add(Project(id=1, code="p", name="p", status=1))
    sess.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                        dsn_encrypted=encrypt_secret(url)))
    sess.commit()
    yield sess


def test_publish_enable_revoke(s):
    a = create_asset(s, 1, "api", "A", VALID, "actor", enabled=False)
    c = propose(s, 1, "actor", "publish_api", a.id)
    apply(s, c.id, issue_token(a.id, "publish_api"))
    s.refresh(a)
    assert a.enabled is True and a.published_version_id

    c = propose(s, 1, "actor", "revoke_api", a.id)
    apply(s, c.id, issue_token(a.id, "revoke_api"))
    s.refresh(a)
    assert a.enabled is False

    c = propose(s, 1, "actor", "enable_api", a.id)
    apply(s, c.id, issue_token(a.id, "enable_api"))
    s.refresh(a)
    assert a.enabled is True
    assert s.query(AuditLog).filter_by(action="publish_api").count() == 1


def test_wrong_token_rejected(s):
    a = create_asset(s, 1, "api", "A", VALID, "actor", enabled=False)
    c = propose(s, 1, "actor", "revoke_api", a.id)
    with pytest.raises(PermissionError):
        apply(s, c.id, issue_token(a.id, "publish_api"))
