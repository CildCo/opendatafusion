import hashlib
import hmac
import time

from odf.settings import get_settings


def _sig(target_id: int, action: str, exp: int, nonce: str = "") -> str:
    msg = "%s:%s:%s" % (target_id, action, exp)
    if nonce:
        msg += ":" + nonce
    return hmac.new(get_settings().jwt_secret.encode(), msg.encode(),
                    hashlib.sha256).hexdigest()


def issue_token(target_id: int, action: str, ttl_s: int = 300,
                nonce: str = "") -> str:
    exp = int(time.time()) + ttl_s
    return "%s:%s" % (exp, _sig(target_id, action, exp, nonce))


def verify_token(target_id: int, action: str, token: str,
                 nonce: str = "") -> bool:
    try:
        exp_s, sig = token.split(":", 1)
        exp = int(exp_s)
    except Exception:
        return False
    if exp < time.time():
        return False
    return hmac.compare_digest(sig, _sig(target_id, action, exp, nonce))
