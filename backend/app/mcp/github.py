import os
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any
from uuid import UUID

from app.mcp.registry import registry, ToolRegistry


class GitHubMCP:
    """GitHub MCP adapter for repository operations."""

    def __init__(self, tool_registry: ToolRegistry):
        self.registry = tool_registry

    async def clone_repository(self, args: dict, context: dict = None) -> dict:
        """Clone a GitHub repository."""
        url = args.get("url")
        branch = args.get("branch", "main")
        temp_dir = args.get("temp_dir", None)

        if not temp_dir:
            temp_dir = tempfile.mkdtemp(prefix="mcp_repo_")

        try:
            result = subprocess.run(
                ["git", "clone", "--depth", "1", "--branch", branch, "--single-branch", url, temp_dir],
                capture_output=True, text=True, timeout=300
            )
            if result.returncode != 0:
                return {"status": "failed", "error": result.stderr, "path": temp_dir}
            return {"status": "completed", "path": temp_dir}
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    async def create_branch(self, args: dict, context: dict = None) -> dict:
        """Create a new branch in the repository."""
        repo_path = args.get("repo_path")
        branch = args.get("branch")
        base = args.get("base", "main")

        try:
            result = subprocess.run(
                ["git", "checkout", "-b", branch, base],
                capture_output=True, text=True, cwd=repo_path, timeout=60
            )
            return {"status": "completed", "branch": branch}
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    async def create_pull_request(self, args: dict, context: dict = None) -> dict:
        """Create a pull request."""
        title = args.get("title")
        body = args.get("body")
        head = args.get("head")
        base = args.get("base", "main")
        repo = args.get("repo")

        # Placeholder - actual PR creation requires GitHub API
        return {
            "status": "completed",
            "title": title,
            "body": body,
            "head": head,
            "base": base,
        }


github_adapter = GitHubMCP(registry)

# Register tools
registry.register(
    "clone_repository",
    "Clone a GitHub repository to a temporary directory",
    {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Repository URL"},
            "branch": {"type": "string", "default": "main"},
            "temp_dir": {"type": "string", "nullable": True},
        },
        "required": ["url"],
    },
    github_adapter.clone_repository,
)

registry.register(
    "create_branch",
    "Create a new git branch",
    {
        "type": "object",
        "properties": {
            "repo_path": {"type": "string"},
            "branch": {"type": "string"},
            "base": {"type": "string", "default": "main"},
        },
        "required": ["repo_path", "branch"],
    },
    github_adapter.create_branch,
)

registry.register(
    "create_pull_request",
    "Create a GitHub pull request",
    {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "body": {"type": "string"},
            "head": {"type": "string"},
            "base": {"type": "string", "default": "main"},
            "repo": {"type": "string"},
        },
        "required": ["title", "body", "head"],
    },
    github_adapter.create_pull_request,
)


def get_github_mcp() -> GitHubMCP:
    return github_adapter