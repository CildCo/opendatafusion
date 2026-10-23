import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote


def generate_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _key(secret):
    padded = secret + "=" * ((8 - len(secret) % 8) % 8)
    return base64.b32decode(padded, casefold=True)


def code_for(secret, at=None, digits=6, step=30):
    counter = int((at if at is not None else time.time()) // step)
    digest = hmac.new(_key(secret), struct.pack(">Q", counter),
                      hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(value % (10 ** digits)).zfill(digits)


def matching_step(secret, code, at=None, digits=6, step=30):
    if not secret or not isinstance(code, str):
        return None
    now = at if at is not None else time.time()
    base = int(now // step)
    for delta in (-1, 0, 1):
        if hmac.compare_digest(
                code_for(secret, (base + delta) * step, digits, step),
                code.strip()):
            return base + delta
    return None


def verify_code(secret, code, at=None, digits=6, step=30):
    return matching_step(secret, code, at, digits, step) is not None


def provisioning_uri(secret, username, issuer):
    label = quote("%s:%s" % (issuer, username))
    return ("otpauth://totp/%s?secret=%s&issuer=%s&digits=6&period=30"
            % (label, secret, quote(issuer)))
