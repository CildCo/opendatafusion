import asyncio
from types import SimpleNamespace

from fastapi import Response
from starlette.requests import Request

from odf.services.auth import create_token


def test_menu_middleware_releases_session_before_call_next(monkeypatch):
    token = create_token(1, 1)
    import odf.db

    class Session:
        closed = False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            Session.closed = True

        def get(self, model, key):
            return SimpleNamespace(id=1, role="admin", active=True)

    monkeypatch.setattr(odf.db, "SessionLocal", lambda: Session())
    from odf.main import menu_permission

    request = Request({
        "type": "http", "method": "GET",
        "path": "/api/v1/catalog/datasets", "root_path": "",
        "query_string": b"", "scheme": "http",
        "headers": [(b"authorization",
                     ("Bearer " + token).encode("ascii"))],
        "server": ("testserver", 80), "client": ("127.0.0.1", 1234),
    })

    async def call_next(req):
        assert Session.closed is True
        return Response("ok")

    response = asyncio.run(menu_permission(request, call_next))
    assert response.status_code == 200
