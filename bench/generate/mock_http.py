import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

STATE = {"mode": "normal"}


def set_mode(mode: str) -> None:
    if mode not in ("normal", "error", "timeout", "slow"):
        raise ValueError("unknown mode")
    STATE["mode"] = mode


def _product(i: int) -> dict:
    return {"id": i, "name": f"华光手机数码旗舰版{i}",
            "category": "手机数码", "price": 100 + i % 900}


class Handler(BaseHTTPRequestHandler):
    def _json(self, code: int, payload: dict) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            return self._json(200, {"ok": True, "mode": STATE["mode"]})
        if STATE["mode"] == "error":
            return self._json(500, {"error": "injected"})
        if STATE["mode"] == "timeout":
            import time
            time.sleep(10)
            return self._json(200, {"items": []})
        if parsed.path == "/products":
            q = parse_qs(parsed.query)
            page = max(1, int(q.get("page", ["1"])[0]))
            size = min(100, max(1, int(q.get("size", ["20"])[0])))
            start = (page - 1) * size + 1
            return self._json(200, {"page": page, "size": size,
                                    "items": [_product(i) for i in range(start, start + size)]})
        return self._json(404, {"error": "not found"})

    def do_POST(self):
        if urlparse(self.path).path != "/mode":
            return self._json(404, {"error": "not found"})
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        set_mode(body.get("mode", "normal"))
        return self._json(200, {"mode": STATE["mode"]})

    def log_message(self, *args):
        pass


def make_server(port: int = 18183) -> ThreadingHTTPServer:
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def serve(port: int = 18183) -> None:
    make_server(port).serve_forever()


if __name__ == "__main__":
    serve()
