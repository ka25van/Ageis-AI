import os
import glob
from pathlib import Path
from typing import Dict, List, Optional, Any

from app.mcp.registry import registry


class FilesystemMCP:
    """Filesystem MCP adapter for reading, writing, and searching files."""

    async def read_file(self, args: dict, context: dict = None) -> dict:
        """Read a file from the filesystem."""
        path = args.get("path")
        if not os.path.exists(path):
            return {"status": "failed", "error": "File not found"}

        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            return {"status": "completed", "content": content}
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    async def write_file(self, args: dict, context: dict = None) -> dict:
        """Write content to a file."""
        path = args.get("path")
        content = args.get("content")

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return {"status": "completed", "path": path}
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    async def search_files(self, args: dict, context: dict = None) -> dict:
        """Search for files matching a pattern."""
        pattern = args.get("pattern")
        path = args.get("path", ".")

        try:
            matches = glob.glob(os.path.join(path, pattern), recursive=True)
            return {"status": "completed", "files": matches}
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    async def list_directory(self, args: dict, context: dict = None) -> dict:
        """List contents of a directory."""
        path = args.get("path", ".")
        try:
            items = os.listdir(path)
            return {"status": "completed", "files": items}
        except Exception as e:
            return {"status": "failed", "error": str(e)}


filesystem_adapter = FilesystemMCP()

# Register tools
registry.register(
    "read_file",
    "Read the contents of a file",
    {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    },
    filesystem_adapter.read_file,
)

registry.register(
    "write_file",
    "Write content to a file",
    {
        "type": "object",
        "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
        "required": ["path", "content"],
    },
    filesystem_adapter.write_file,
)

registry.register(
    "search_files",
    "Search for files by pattern",
    {
        "type": "object",
        "properties": {"pattern": {"type": "string"}, "path": {"type": "string", "default": "."}},
        "required": ["pattern"],
    },
    filesystem_adapter.search_files,
)

registry.register(
    "list_directory",
    "List directory contents",
    {
        "type": "object",
        "properties": {"path": {"type": "string", "default": "."}},
        "required": [],
    },
    filesystem_adapter.list_directory,
)


def get_filesystem_mcp() -> FilesystemMCP:
    return filesystem_adapter