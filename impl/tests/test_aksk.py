import base64
import hashlib
import hmac
from types import SimpleNamespace

from odf.services import aksk as aksk_mod
from odf.services.aksk import sign, sign_sha256, string_to_sign, verify


def test_signature_matches_known_shape():
    s2s = string_to_sign("POST", b'{"a":1}', "application/json",
                         "1700000000000", "/openapi/x")
    assert s2s.startswith("POST\n")
    assert s2s.endswith("/openapi/x")
    sig = sign("secret", s2s)
    assert base64.b64decode(sig) == hmac.new(b"secret", s2s.encode(),
                                             hashlib.sha1).digest()


def test_reject_old_date():
    assert not verify("ak", "sk", "GET", b"", "application/json", "1", "/x",
                      "ak:bad", 10 ** 13)


def test_reject_malformed_date():
    assert not verify("ak", "sk", "GET", b"", "application/json",
                      "Mon, 19 Oct 2026 10:00:00 GMT", "/x", "ak:bad",
                      10 ** 13)


def test_sha256_signature_and_sha1_can_be_disabled(monkeypatch):
    now = 1700000000000
    s2s = string_to_sign("GET", b"", "application/json", str(now), "/x")
    sha256 = "ak:" + sign_sha256("sk", s2s)
    sha1 = "ak:" + sign("sk", s2s)
    assert verify("ak", "sk", "GET", b"", "application/json", str(now),
                  "/x", sha256, now)
    monkeypatch.setattr(
        aksk_mod, "get_settings",
        lambda: SimpleNamespace(aksk_time_window_s=300,
                                aksk_allow_sha1=False))
    assert verify("ak", "sk", "GET", b"", "application/json", str(now),
                  "/x", sha256, now)
    assert not verify("ak", "sk", "GET", b"", "application/json", str(now),
                      "/x", sha1, now)
