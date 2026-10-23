import uvicorn
from mcp.server.mcpserver import MCPServer
from starlette.responses import JSONResponse

from odf.mcp.server import CURRENT_PROJECT, TOOLS

server = MCPServer("odf")
for name, fn in TOOLS.items():
    server.add_tool(fn, name=name)


class JWTAuth:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in scope.get("headers", [])
        }
        auth = headers.get("authorization", "")
        scheme, _, token = auth.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return await JSONResponse({"detail": "missing bearer token"},
                                      status_code=401)(scope, receive, send)
        try:
            from odf.db import SessionLocal
            from odf.models import User
            from odf.services.auth import decode_token
            claims = decode_token(token)
            with SessionLocal() as s:
                user = s.get(User, int(claims["sub"]))
                if not user or not user.active or int(
                        claims.get("ver", 0)) != int(user.token_version or 0):
                    raise ValueError("invalid session")
            reset = CURRENT_PROJECT.set(int(claims["project_id"]))
        except Exception:
            return await JSONResponse({"detail": "invalid or expired token"},
                                      status_code=401)(scope, receive, send)
        try:
            return await self.app(scope, receive, send)
        finally:
            CURRENT_PROJECT.reset(reset)


def app():
    return JWTAuth(server.streamable_http_app(host="0.0.0.0"))


def main():
    import os
    uvicorn.run(app(), host=os.environ.get("ODF_MCP_HOST", "0.0.0.0"),
                port=int(os.environ.get("ODF_MCP_PORT", "18082")))


if __name__ == "__main__":
    main()
