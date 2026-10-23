import httpx

from bench.seed import seed_platform


def test_publish_runs_change_approve_apply():
    calls = []

    def handler(request):
        calls.append((request.method, request.url.path))
        if request.url.path.endswith("/changes"):
            return httpx.Response(200, json={"id": 7})
        if request.url.path.endswith("/changes/7/approve"):
            return httpx.Response(200, json={"approval_token": "tok"})
        if request.url.path.endswith("/changes/7/apply"):
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(200, json={})

    client = seed_platform.Client("http://bench", "u", "p",
                                  transport=httpx.MockTransport(handler))
    client.token = "t"
    client.publish("publish_pipeline", 42, 3)
    assert calls == [("POST", "/api/v1/changes"),
                     ("POST", "/api/v1/changes/7/approve"),
                     ("POST", "/api/v1/changes/7/apply")]
