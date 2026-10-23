from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.db import Base
from odf.models import Project, ProjectMember, User
from odf.services import oidc, ldap_auth


def _settings(**kw):
    base = {"oidc_issuer": "https://idp.example",
            "oidc_client_id": "cid", "oidc_client_secret": "secret",
            "oidc_redirect_uri": "https://odf.example/cb",
            "oidc_scopes": "openid profile email",
            "oidc_auto_provision": True, "jwt_secret": "state-secret",
            "ldap_url": "", "ldap_user_dn_template": "",
            "ldap_bind_dn": "", "ldap_bind_password": "",
            "ldap_auto_provision": True}
    base.update(kw)
    return SimpleNamespace(**base)


def _env():
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Project(id=1, code="o1", name="o1", status=1))
    s.commit()
    return s


def test_start_builds_authorize_url(monkeypatch):
    monkeypatch.setattr(oidc, "get_settings", lambda: _settings())
    class R:
        def json(self):
            return {"authorization_endpoint": "https://idp.example/auth",
                    "token_endpoint": "https://idp.example/token",
                    "userinfo_endpoint": "https://idp.example/me"}

        def raise_for_status(self):
            return None

    monkeypatch.setattr(oidc.httpx, "get", lambda *a, **k: R())
    url = oidc.start(1)
    assert url.startswith("https://idp.example/auth?")
    assert "code_challenge_method=S256" in url
    assert "state=" in url


def test_exchange_and_map_user(monkeypatch):
    monkeypatch.setattr(oidc, "get_settings", lambda: _settings())
    calls = []

    class R:
        def __init__(self, data):
            self._data = data

        def json(self):
            return self._data

        def raise_for_status(self):
            return None

    def get(url, **kw):
        if "openid-configuration" in url:
            return R({"authorization_endpoint": "https://idp.example/auth",
                      "token_endpoint": "https://idp.example/token",
                      "userinfo_endpoint": "https://idp.example/me"})
        calls.append((url, kw))
        return R({"sub": "s1", "preferred_username": "alice", "email": "a@example.com"})

    def post(url, **kw):
        calls.append((url, kw))
        return R({"access_token": "at"})

    monkeypatch.setattr(oidc.httpx, "get", get)
    monkeypatch.setattr(oidc.httpx, "post", post)
    state = oidc._state(1)
    project_id, info = oidc.exchange("code", state)
    assert project_id == 1 and info["preferred_username"] == "alice"
    s = _env()
    with pytest.raises(PermissionError):
        oidc.map_user(s, info, 1)
    user = s.query(User).filter_by(username="alice").first()
    assert user is not None
    s.add(ProjectMember(project_id=1, user_id=user.id, role="viewer"))
    s.commit()
    assert oidc.map_user(s, info, 1).id == user.id


def test_ldap_unconfigured():
    assert ldap_auth.authenticate_ldap("u", "p") is None


def test_state_hides_verifier_and_avoids_account_takeover(monkeypatch):
    monkeypatch.setattr(oidc, "get_settings", lambda: _settings())

    class R:
        def json(self):
            return {"authorization_endpoint": "https://idp.example/auth",
                    "token_endpoint": "https://idp.example/token",
                    "userinfo_endpoint": "https://idp.example/me"}

        def raise_for_status(self):
            return None

    monkeypatch.setattr(oidc.httpx, "get", lambda *a, **k: R())
    url, state, nonce = oidc.start_flow(1)
    claims = oidc._decode_state(state)
    assert nonce and claims["venc"] and "verifier" not in claims
    s = _env()
    from odf.services.users import create_user
    create_user(s, "admin", "GoodPassw0rd!", role="admin")
    with pytest.raises(PermissionError):
        oidc.map_user(s, {"sub": "evil", "preferred_username": "admin"}, 1)
    created = s.query(User).filter(User.oidc_sub == "evil").first()
    assert created is not None and created.username != "admin"
