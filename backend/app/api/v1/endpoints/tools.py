from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.api.v1.endpoints.auth import get_current_user
from app.core.di import get_db_session
from app.models.user import User
from app.models.project import Project
from app.mcp.registry import registry
from app.mcp.interface import ToolInterface, get_tool_interface

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("")
async def list_tools(
    current_user: User = Depends(get_current_user),
    interface: ToolInterface = Depends(get_tool_interface),
):
    """List all available MCP tools."""
    tools = interface.list_available()
    return {"tools": tools, "count": len(tools)}


@router.post("/{tool_name}/execute")
async def execute_tool(
    tool_name: str,
    args: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    interface: ToolInterface = Depends(get_tool_interface),
):
    """Execute a specific tool."""
    tool = registry.get_tool(tool_name)
    if not tool:
        raise HTTPException(
            status_code=404,
            detail=f"Tool '{tool_name}' not found",
        )

    result = await interface.execute(tool_name, args, {"user_id": str(current_user.id)})
    return result


@router.get("/{tool_name}")
async def get_tool_details(
    tool_name: str,
    current_user: User = Depends(get_current_user),
):
    """Get details about a specific tool."""
    tool = registry.get_tool(tool_name)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return {
        "name": tool["name"],
        "description": tool["description"],
        "schema": tool["schema"],
    }