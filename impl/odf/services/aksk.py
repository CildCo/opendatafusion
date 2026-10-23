import base64
import hashlib
import hmac

from odf.settings import get_settings


def string_to_sign(method, body, content_type, date_ms, path) -> str:
    md5 = base64.b64encode(hashlib.md5(body or b"").digest()).decode()
    return "\n".join([method.upper(), md5, content_type or "", str(date_ms), path])


def sign(sk: str, s2s: str) -> str:
    digest = hmac.new(sk.encode(), s2s.encode(), hashlib.sha1).digest()
    return base64.b64encode(digest).decode()


def sign_sha256(sk: str, s2s: str) -> str:
    digest = hmac.new(sk.encode(), s2s.encode(), hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def verify(ak, sk, method, body, content_type, date_ms, path, auth_header,
           now_ms) -> bool:
    try:
        if abs(int(now_ms) - int(date_ms)) > \
                get_settings().aksk_time_window_s * 1000:
            return False
    except (TypeError, ValueError):
        return False
    s2s = string_to_sign(method, body, content_type, date_ms, path)
    auth_header = auth_header or ""
    prefix = "%s:" % ak
    if not auth_header.startswith(prefix):
        return False
    candidates = [sign_sha256(sk, s2s)]
    if get_settings().aksk_allow_sha1:
        candidates.append(sign(sk, s2s))
    return any(hmac.compare_digest("%s:%s" % (ak, sig), auth_header)
               for sig in candidates)
