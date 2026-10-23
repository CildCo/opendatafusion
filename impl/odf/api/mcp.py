from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from odf.db import get_session
from odf.models import User
from odf.mcp.server import (APPROVER_TOOLS, CURRENT_PROJECT, TOOLS,
                            WRITE_TOOLS, tool_catalog)
from odf.pipeline.runner import PipelineRunError
from odf.services.auth import require_user

router = APIRouter()


@router.get("/mcp/tools")
def tools(claims: dict = Depends(require_user)):
    return tool_catalog()


@router.post("/mcp/{tool_name}")
def call_tool(tool_name: str, args: dict,
              s: Session = Depends(get_session),
              claims: dict = Depends(require_user)):
    fn = TOOLS.get(tool_name)
    if fn is None:
        raise HTTPException(404, "unknown tool")
    user = s.get(User, int(claims["sub"]))
    role = user.role if user else "viewer"
    if tool_name in WRITE_TOOLS and role not in ("editor", "approver", "admin"):
        raise HTTPException(403, "editor role required")
    if tool_name in APPROVER_TOOLS and role not in ("approver", "admin"):
        raise HTTPException(403, "approver role required")
    token = CURRENT_PROJECT.set(claims["project_id"])
    try:
        try:
            return fn(**args)
        except PermissionError as e:
            raise HTTPException(403, str(e))
        except PipelineRunError as e:
            raise HTTPException(400, {"node_id": e.node_id,
                                      "errors": [e.message],
                                      "node_stats": e.stats})
        except (ValueError, KeyError, TypeError) as e:
            raise HTTPException(400, str(e))
    finally:
        CURRENT_PROJECT.reset(token)
