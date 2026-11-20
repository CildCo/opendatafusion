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


def test_cannot_deactivate_the_last_active_administrator(s):
    admin = create_user(s, "root1", "pw", role="admin")
    with pytest.raises(ValueError):
        set_active(s, admin.id, False)
    assert s.get(type(admin), admin.id).active


def test_cannot_deactivate_yourself_even_with_another_admin(s):
    first = create_user(s, "root2", "pw", role="admin")
    second = create_user(s, "root3", "pw", role="admin")
    with pytest.raises(ValueError):
        set_active(s, second.id, False, actor_id=second.id)
    assert s.get(type(second), second.id).active
    set_active(s, first.id, False, actor_id=second.id)
    assert not s.get(type(first), first.id).active


def test_inactive_admins_do_not_count_as_coverage(s):
    active_admin = create_user(s, "root4", "pw", role="admin")
    dormant = create_user(s, "root5", "pw", role="admin")
    set_active(s, dormant.id, False, actor_id=active_admin.id)
    with pytest.raises(ValueError):
        set_active(s, active_admin.id, False)
    assert s.get(type(active_admin), active_admin.id).active


def test_cannot_remove_the_last_active_administrator_role(s):
    admin = create_user(s, "root6", "pw", role="admin")
    with pytest.raises(ValueError):
        set_role(s, admin.id, "viewer")
    assert s.get(type(admin), admin.id).role == "admin"


def test_cannot_change_your_own_role(s):
    first = create_user(s, "root7", "pw", role="admin")
    second = create_user(s, "root8", "pw", role="admin")
    with pytest.raises(ValueError):
        set_role(s, second.id, "viewer", actor_id=second.id)
    assert s.get(type(second), second.id).role == "admin"
    set_role(s, first.id, "viewer", actor_id=second.id)
    assert s.get(type(first), first.id).role == "viewer"


def test_break_glass_can_reenable_an_administrator(s):
    from odf.services.users import set_active_by_name
    admin = create_user(s, "root9", "pw", role="admin")
    admin.active = False
    s.commit()
    restored = set_active_by_name(s, "root9", True)
    assert restored.active is True
