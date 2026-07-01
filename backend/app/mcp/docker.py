import subprocess
from typing import Dict

from app.mcp.registry import registry


class DockerMCP:
    """Docker MCP adapter for container operations."""

    async def build_image(self, args: dict, context: dict = None) -> dict:
        """Build a Docker image."""
        dockerfile = args.get("dockerfile", ".")
        tag = args.get("tag")
        context_path = args.get("context", ".")

        try:
            result = subprocess.run(
                ["docker", "build", "-t", tag, "-f", dockerfile, context_path],
                capture_output=True, text=True, timeout=300
            )
            return {"status": "completed" if result.returncode == 0 else "failed", "output": result.stdout + result.stderr}
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    async def run_container(self, args: dict, context: dict = None) -> dict:
        """Run a Docker container."""
        image = args.get("image")
        name = args.get("name", "aegis_container")
        ports = args.get("ports", {})
        env = args.get("env", {})
        detach = args.get("detach", True)

        try:
            cmd = ["docker", "run"]
            if detach:
                cmd.append("-d")
            cmd.extend(["--name", name, image])
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            return {"status": "completed" if result.returncode == 0 else "failed", "container_id": result.stdout.strip()}
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    async def stop_container(self, args: dict, context: dict = None) -> dict:
        """Stop a running Docker container."""
        container_id = args.get("container_id")
        try:
            result = subprocess.run(
                ["docker", "stop", container_id],
                capture_output=True, text=True, timeout=30
            )
            return {"status": "completed" if result.returncode == 0 else "failed"}
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    async def get_logs(self, args: dict, context: dict = None) -> dict:
        """Get logs from a Docker container."""
        container_id = args.get("container_id")
        try:
            result = subprocess.run(
                ["docker", "logs", container_id],
                capture_output=True, text=True, timeout=30
            )
            return {"status": "completed", "logs": result.stdout}
        except Exception as e:
            return {"status": "failed", "error": str(e)}


docker_adapter = DockerMCP()

registry.register(
    "build_image",
    "Build a Docker image",
    {
        "type": "object",
        "properties": {
            "dockerfile": {"type": "string", "default": "."},
            "tag": {"type": "string"},
            "context": {"type": "string", "default": "."},
        },
        "required": ["tag"],
    },
    docker_adapter.build_image,
)

registry.register(
    "run_container",
    "Run a Docker container",
    {
        "type": "object",
        "properties": {"image": {"type": "string"}, "name": {"type": "string"}, "detach": {"type": "boolean", "default": True}},
        "required": ["image"],
    },
    docker_adapter.run_container,
)

registry.register(
    "stop_container",
    "Stop a Docker container",
    {
        "type": "object",
        "properties": {"container_id": {"type": "string"}},
        "required": ["container_id"],
    },
    docker_adapter.stop_container,
)

registry.register(
    "get_logs",
    "Get Docker container logs",
    {
        "type": "object",
        "properties": {"container_id": {"type": "string"}},
        "required": ["container_id"],
    },
    docker_adapter.get_logs,
)


def get_docker_mcp() -> DockerMCP:
    return docker_adapter