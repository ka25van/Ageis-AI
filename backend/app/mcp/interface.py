from typing import Dict, Any, Optional
from uuid import UUID

from app.mcp.registry import ToolRegistry, registry


class ToolInterface:
    """Common interface for all MCP tool adapters."""

    def __init__(self, tool_registry: ToolRegistry):
        self.registry = tool_registry

    async def execute(self, tool_name: str, args: dict, context: dict = None) -> Any:
        """Execute a tool through the registry."""
        return await self.registry.execute(tool_name, args, context)

    def list_available(self, category: Optional[str] = None) -> list:
        """List tools, optionally filtered by category."""
        all_tools = self.registry.list_tools()
        if category:
            return [t for t in all_tools if category in t.get("categories", [])]
        return all_tools


# Singleton
interface = ToolInterface(registry)


async def get_tool_interface() -> ToolInterface:
    """Dependency injection for tool interface."""
    return interface