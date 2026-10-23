import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.assets.service import create_asset
from odf.db import Base
from odf.models import AkSk, Datasource, Project, User, WebhookSubscription
from odf.services.rotation import rotate_aksk, rotate_fernet


def _env():
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Project(id=1, code="r1", name="r1", status=1))
    s.commit()
    return s


def _enc(value, key):
    return Fernet(key).encrypt(value.encode()).decode()


def test_rotate_fernet_reencrypts_all_secrets():
    s = _env()
    old = Fernet.generate_key().decode()
    new = Fernet.generate_key().decode()
    s.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                     dsn_encrypted=_enc("sqlite://", old)))
    s.add(AkSk(project_id=1, ak="a", sk_encrypted=_enc("sk", old),
               enabled=True))
    s.add(WebhookSubscription(project_id=1, name="w",
                              url="http://127.0.0.1:9/h",
                              secret_encrypted=_enc("whsec", old),
                              events_json=[], enabled=True, created_by="u"))
    s.add(User(id=9, username="rot", password_hash="x", role="viewer",
               active=True, totp_enabled=True,
               totp_secret_encrypted=_enc("TOTPSECRET", old)))
    s.commit()
    counts = rotate_fernet(s, old, new)
    assert counts["datasources"] == 1
    assert counts["aksk"] == 1
    assert counts["webhooks"] == 1
    assert counts["totp"] == 1
    with pytest.raises(Exception):
        Fernet(old).decrypt(s.get(Datasource, 1).dsn_encrypted.encode())
    assert Fernet(new).decrypt(
        s.get(Datasource, 1).dsn_encrypted.encode()).decode() == "sqlite://"
    assert Fernet(new).decrypt(
        s.get(User, 9).totp_secret_encrypted.encode()).decode() == "TOTPSECRET"


def test_rotate_aksk_disables_old_and_issues_new():
    s = _env()
    s.add(AkSk(project_id=1, ak="old", sk_encrypted="x", enabled=True))
    s.commit()
    out = rotate_aksk(s, 1)
    assert out["ak"] != "old" and out["sk"]
    assert s.query(AkSk).filter_by(ak="old").first().enabled is False
    assert s.query(AkSk).filter_by(ak=out["ak"]).first().enabled is True

