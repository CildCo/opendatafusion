import ipaddress
import socket
import ssl
from urllib.parse import urlsplit

DEFAULT_MAX_BYTES = 10 * 1024 * 1024


def tls_context():
    context = ssl.create_default_context()
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    return context


def _host_allowed(host: str, allowed_hosts) -> bool:
    if not allowed_hosts:
        return True
    host = host.lower().rstrip(".")
    for item in allowed_hosts:
        rule = item.strip().lower().rstrip(".")
        if not rule:
            continue
        if rule.startswith("*."):
            if host.endswith(rule[1:]) and host != rule[2:]:
                return True
        elif host == rule:
            return True
    return False


def resolve_public_url(url, allow_private=False, allowed_hosts=(),
                       label="outbound"):
    if not isinstance(url, str) or len(url) > 2048 or \
            any(ord(c) < 32 for c in url):
        raise ValueError("invalid %s URL" % label)
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError("%s URL must be http(s)" % label)
    if parts.username or parts.password:
        raise ValueError("%s URL must not contain credentials" % label)
    if not _host_allowed(parts.hostname, allowed_hosts):
        raise ValueError("%s host is not in the allowed list" % label)
    try:
        port = parts.port or (443 if parts.scheme == "https" else 80)
    except ValueError:
        raise ValueError("invalid %s port" % label)
    try:
        infos = socket.getaddrinfo(parts.hostname, port,
                                   type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise ValueError("%s host cannot be resolved" % label)
    if not infos:
        raise ValueError("%s host cannot be resolved" % label)
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not allow_private and (
                ip.is_private or ip.is_loopback or ip.is_link_local or
                ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            raise ValueError("%s host is not allowed" % label)
    return parts, port, infos[0][4][0]


def request(url, method="GET", body=None, headers=None, allow_private=False,
            allowed_hosts=(), timeout=30, max_bytes=DEFAULT_MAX_BYTES):
    parts, port, ip = resolve_public_url(
        url, allow_private, allowed_hosts, label="outbound")
    headers = dict(headers or {})
    path = parts.path or "/"
    if parts.query:
        path += "?" + parts.query
    lines = ["%s %s HTTP/1.1" % (method.upper(), path),
             "Host: %s" % parts.netloc, "Connection: close"]
    if body is not None and "Content-Length" not in headers:
        headers["Content-Length"] = str(len(body))
    lines.extend("%s: %s" % (k, v) for k, v in headers.items())
    lines.extend(["", ""])
    raw = "\r\n".join(lines).encode() + (body or b"")
    sock = socket.create_connection((ip, port), timeout=timeout)
    try:
        if parts.scheme == "https":
            sock = tls_context().wrap_socket(
                sock, server_hostname=parts.hostname)
        sock.sendall(raw)
        data = b""
        while len(data) < max_bytes + 65536:
            chunk = sock.recv(65536)
            if not chunk:
                break
            data += chunk
    finally:
        sock.close()
    head, _, payload = data.partition(b"\r\n\r\n")
    lines = head.split(b"\r\n")
    status = lines[0].split()
    if len(status) < 2:
        raise ValueError("invalid HTTP response")
    code = int(status[1])
    resp_headers = {}
    for line in lines[1:]:
        key, _, value = line.partition(b":")
        resp_headers[key.decode("latin-1").strip().lower()] = \
            value.decode("latin-1").strip()
    if resp_headers.get("transfer-encoding", "").lower() == "chunked":
        payload = _dechunk(payload)
    if len(payload) > max_bytes:
        raise ValueError("HTTP response is too large")
    if not 200 <= code < 300:
        detail = payload[:300].decode("utf-8", "replace")
        raise ValueError("HTTP %d: %s" % (code, detail))
    return code, resp_headers, payload


def _dechunk(data: bytes) -> bytes:
    out = b""
    while data:
        line, sep, rest = data.partition(b"\r\n")
        if not sep:
            break
        try:
            size = int(line.split(b";")[0], 16)
        except ValueError:
            raise ValueError("invalid chunked response")
        if size == 0:
            break
        out += rest[:size]
        data = rest[size + 2:]
    return out
