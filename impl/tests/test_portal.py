import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.db import Base, SessionLocal
from odf.main import app
from odf.models import PortalSetting, Project, User
from odf.services.auth import create_token
from odf.portal.service import get_portal, update_portal


def _env():
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add_all([Project(id=1, code="p1", name="p1", status=1),
               Project(id=2, code="p2", name="p2", status=1)])
    s.commit()
    return s


def test_defaults_update_and_scope():
    s = _env()
    d = get_portal(s, 1)
    assert d["brand_name"] == "OpenDataFusion"
    assert d["primary_color"].startswith("#")
    out = update_portal(s, 1, {"brand_name": "Acme 数据",
                               "primary_color": "#ff0000",
                               "welcome_title": "你好",
                               "welcome_text": "欢迎",
                               "hidden_menus": ["/alerts"]}, "u")
    assert out["brand_name"] == "Acme 数据"
    assert out["hidden_menus"] == ["/alerts"]
    assert s.query(PortalSetting).count() == 1
    assert get_portal(s, 2)["brand_name"] == "OpenDataFusion"


def test_validation():
    s = _env()
    for fields in ({"primary_color": "red"},
                   {"primary_color": "#12345"},
                   {"brand_name": ""},
                   {"hidden_menus": ["/nope"]},
                   {"hidden_menus": "/alerts"},
                   {"welcome_text": "x" * 1001}):
        with pytest.raises(ValueError):
            update_portal(s, 1, fields, "u")


def _user(uid, role):
    with SessionLocal() as s:
        u = s.get(User, uid)
        if not u:
            u = User(id=uid, username="portal%d" % uid, password_hash="x",
                     role=role, active=True)
            s.add(u)
        else:
            u.role = role
            u.active = True
        s.commit()


def test_portal_routes():
    _user(1, "admin")
    c = TestClient(app)
    h = {"Authorization": "Bearer " + create_token(1, 1)}
    assert c.get("/api/v1/portal", headers=h).status_code == 200
    r = c.put("/api/v1/portal", json={"brand_name": "Portal X",
                                      "hidden_menus": []}, headers=h)
    assert r.status_code == 200 and r.json()["brand_name"] == "Portal X"
    _user(1, "editor")
    assert c.put("/api/v1/portal", json={"brand_name": "Editor"},
                 headers=h).status_code == 200
    assert c.put("/api/v1/portal", json={"allowed_menus": ["/datasets"]},
                 headers=h).status_code == 403
    _user(1, "viewer")
    assert c.put("/api/v1/portal", json={"brand_name": "X"},
                 headers=h).status_code == 403
    assert c.get("/api/v1/portal",
                 headers={"Authorization": "Bearer "
                          + create_token(1, 2)}).json()["brand_name"] != \
        "Portal X"


def test_blank_brand_is_rejected():
    s = _env()
    with pytest.raises(ValueError):
        update_portal(s, 1, {"brand_name": "   "}, "u")
