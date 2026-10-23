import sqlite3
import threading

import httpx

from bench.generate import edge, mock_http


def test_edge_builds_sqlite(tmp_path):
    db = edge.build(tmp_path, rows=1000)
    con = sqlite3.connect(db)
    assert con.execute("select count(*) from local_orders").fetchone()[0] == 1000
    con.close()


def test_mock_http_modes():
    server = mock_http.make_server(port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    base = f"http://127.0.0.1:{port}"
    try:
        assert httpx.get(base + "/health").json()["ok"] is True
        page = httpx.get(base + "/products", params={"page": 1, "size": 5}).json()
        assert len(page["items"]) == 5
        assert any("一" <= ch <= "鿿" for ch in page["items"][0]["name"])
        httpx.post(base + "/mode", json={"mode": "error"})
        assert httpx.get(base + "/products").status_code == 500
        httpx.post(base + "/mode", json={"mode": "normal"})
        assert httpx.get(base + "/products").status_code == 200
    finally:
        server.shutdown()
        server.server_close()
