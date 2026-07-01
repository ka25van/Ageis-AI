from typing import Dict, List, Optional, Any, Callable, Awaitable
from uuid import UUID
import json


class ToolRegistry:
    """Registry for MCP tools available to agents."""

    def __init__(self):
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._handlers: Dict[str, Callable] = {}

    def register(self, name: str, description: str, schema: dict, handler: Callable) -> None:
        """Register a tool with its metadata and handler."""
        self._tools[name] = {
            "name": name,
            "description": description,
            "schema": schema,
            "handler": handler,
        }
        self._handlers[name] = handler

    def unregister(self, name: str) -> None:
        """Remove a tool from the registry."""
        self._tools.pop(name, None)
        self._handlers.pop(name, None)

    def list_tools(self) -> List[Dict]:
        """List all registered tools."""
        return [
            {
                "name": t["name"],
                "description": t["description"],
                "schema": t["schema"],
            }
            for t in self._tools.values()
        ]

    def get_tool(self, name: str) -> Optional[Dict]:
        """Get a specific tool by name."""
        return self._tools.get(name)

    async def execute(self, name: str, args: dict, context: dict = None) -> Any:
        """Execute a tool by name with arguments."""
        tool = self._tools.get(name)
        if not tool:
            raise ValueError(f"Tool '{name}' not found in registry")

        handler = tool["handler"]
        if context:
            return await handler(args, context)
        return await handler(args)

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools


# Global registry instance
registry = ToolRegistry()


def get_registry() -> ToolRegistry:
    """Get the global tool registry."""
    return registry