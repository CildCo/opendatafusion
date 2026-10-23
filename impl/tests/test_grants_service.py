import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from odf.assets.service import create_asset, publish_asset
from odf.db import Base
from odf.models import AuditLog, Datasource, InterfaceGrant, Project
from odf.services.crypto import encrypt_secret
from odf.services.grants import (can_access, decide_request, list_grants,
                                 list_requests, request_access,
                                 revoke_grant)


def _env(tmp_path):
    url = "sqlite:///" + str(tmp_path / "g.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table t (id int)"))
        c.execute(text("insert into t values (1)"))
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add_all([Project(id=1, code="p1", name="P1", status=1),
               Project(id=2, code="p2", name="P2", status=1)])
    s.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                     dsn_encrypted=encrypt_secret(url)))
    s.commit()
    content = {"mode": "visual",
               "query": {"datasource_id": 1, "table": "t",
                         "select": [{"column": "id"}]},
               "params": [], "sql": None}
    a = create_asset(s, 1, "api", "A", content, "admin", enabled=False)
    publish_asset(s, a.id, "admin")
    return s, a


def test_request_approve_and_revoke(tmp_path):
    s, a = _env(tmp_path)
    req = request_access(s, a.id, 2, "u2", "please")
    assert req["status"] == "pending"
    assert [r["id"] for r in list_requests(s, 1, "incoming")] == [req["id"]]
    assert [r["id"] for r in list_requests(s, 2, "outgoing")] == [req["id"]]
    with pytest.raises(ValueError):
        decide_request(s, req["id"], 2, "u2", True)
    out = decide_request(s, req["id"], 1, "admin", True)
    assert out["status"] == "approved"
    assert can_access(s, a, 2) is True
    grants = list_grants(s, 1)
    assert len(grants) == 1
    revoke_grant(s, grants[0]["id"], 1, "admin")
    assert can_access(s, a, 2) is False
    actions = [r.action for r in s.query(AuditLog).all()]
    assert "request_api_access" in actions
    assert "approve_api_access" in actions
    assert "revoke_api_grant" in actions


def test_self_project_duplicates_and_reject(tmp_path):
    s, a = _env(tmp_path)
    with pytest.raises(ValueError):
        request_access(s, a.id, 1, "u1")
    req = request_access(s, a.id, 2, "u2")
    with pytest.raises(ValueError):
        request_access(s, a.id, 2, "u2")
    decide_request(s, req["id"], 1, "admin", False)
    assert list_grants(s, 1) == []
    assert can_access(s, a, 2) is False
    assert s.query(InterfaceGrant).count() == 0
    with pytest.raises(ValueError):
        decide_request(s, req["id"], 1, "admin", True)


def test_active_grant_is_unique(tmp_path):
    from sqlalchemy.exc import IntegrityError
    s, a = _env(tmp_path)
    s.add(InterfaceGrant(interface_asset_id=a.id, owner_project_id=1,
                         grantee_project_id=2, granted_by="x"))
    s.commit()
    s.add(InterfaceGrant(interface_asset_id=a.id, owner_project_id=1,
                         grantee_project_id=2, granted_by="y"))
    with pytest.raises(IntegrityError):
        s.commit()
    s.rollback()
