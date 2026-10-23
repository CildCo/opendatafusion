from cryptography.fernet import Fernet

from odf.services.crypto import decrypt_secret, encrypt_secret
from odf.services.datasource import mask_dsn
from odf.settings import get_settings


def test_mask_dsn_hides_password():
    assert "secret" not in mask_dsn("postgresql://u:secret@h:5432/db")
    assert "u:***@h:5432/db" in mask_dsn("postgresql://u:secret@h:5432/db")


def test_secret_roundtrip(monkeypatch):
    monkeypatch.setenv("ODF_FERNET_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()
    s = "postgresql://u:secret@h:5432/db"
    assert decrypt_secret(encrypt_secret(s)) == s
    get_settings.cache_clear()


def test_mask_dsn_with_at_in_password():
    masked = mask_dsn("postgresql://u:p@ss@h:5432/db")
    assert "p@ss" not in masked
    assert "***" in masked
