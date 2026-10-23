import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.db import Base
from odf.services.aksk_admin import issue_aksk, list_aksk, revoke_aksk
from odf.services.projects import add_member, create_project, list_members
from odf.services.users import (authenticate, create_user, set_active,
                                set_role)


@pytest.fixture()
def s():
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    with sessionmaker(bind=e)() as session:
        yield session


def test_create_and_authenticate(s):
    u = create_user(s, "alice", "pw", role="admin")
    assert authenticate(s, "alice", "pw").id == u.id
    assert authenticate(s, "alice", "bad") is None


def test_deactivate_blocks_login(s):
    u = create_user(s, "bob", "pw")
    set_active(s, u.id, False)
    assert authenticate(s, "bob", "pw") is None


def test_set_role(s):
    u = create_user(s, "carol", "pw")
    assert set_role(s, u.id, "approver").role == "approver"


def test_project_member(s):
    p = create_project(s, "p1", "P1")
    u = create_user(s, "dave", "pw")
    add_member(s, p.id, u.id, "editor")
    assert list_members(s, p.id)[0].role == "editor"


def test_aksk_issue_and_revoke(s):
    p = create_project(s, "p2", "P2")
    row, sk = issue_aksk(s, p.id)
    assert row.ak and sk and row.enabled
    revoke_aksk(s, row.ak)
    assert list_aksk(s, p.id)[0].enabled is False
