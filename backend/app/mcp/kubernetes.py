import asyncio
import json
import logging
import subprocess
from typing import Any, Dict, Optional

from app.mcp.registry import registry, ToolRegistry

logger = logging.getLogger(__name__)

KUBECTL_CMD = "kubectl"


def _run_kubectl(args: list[str]) -> dict:
    """Run a kubectl command and return parsed JSON or text result."""
    try:
        result = subprocess.run(
            [KUBECTL_CMD] + args,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            return {"status": "error", "error": result.stderr.strip()}
        if "-o json" in " ".join(args) or "--output=json" in " ".join(args):
            try:
                data = json.loads(result.stdout)
                return {"status": "success", "data": data}
            except json.JSONDecodeError:
                return {"status": "success", "output": result.stdout.strip()}
        return {"status": "success", "output": result.stdout.strip()}
    except FileNotFoundError:
        return {"status": "error", "error": "kubectl not found. Install kubectl to use Kubernetes MCP tools."}
    except subprocess.TimeoutExpired:
        return {"status": "error", "error": "kubectl command timed out after 60 seconds"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


class KubernetesMCP:
    """MCP adapter for Kubernetes cluster operations.

    All operations go through kubectl subprocess to support both
    in-cluster (service account) and local (kubeconfig) auth seamlessly.
    """

    def __init__(self, tool_registry: ToolRegistry):
        self.registry = tool_registry

    async def get_pods(self, args: dict, context: dict = None) -> dict:
        """List pods in a namespace, optionally filtered by label selector."""
        namespace = args.get("namespace", "default")
        cmd = ["get", "pods", "-n", namespace, "-o", "json"]
        label = args.get("label_selector")
        if label:
            cmd.extend(["-l", label])
        result = await asyncio.to_thread(_run_kubectl, cmd)
        if result["status"] == "success" and "data" in result:
            items = result["data"].get("items", [])
            pods = []
            for p in items:
                meta = p.get("metadata", {})
                status = p.get("status", {})
                container_statuses = status.get("containerStatuses", [])
                ready_count = sum(1 for c in container_statuses if c.get("ready"))
                total_count = len(container_statuses)
                pods.append({
                    "name": meta.get("name"),
                    "namespace": meta.get("namespace"),
                    "status": status.get("phase"),
                    "ready": f"{ready_count}/{total_count}",
                    "node": status.get("hostIP"),
                    "pod_ip": status.get("podIP"),
                    "age": meta.get("creationTimestamp"),
                    "labels": meta.get("labels", {}),
                })
            return {"status": "completed", "result": {"pods": pods, "count": len(pods), "namespace": namespace}}
        return {"status": "completed", "result": {"pods": [], "count": 0, "namespace": namespace, "error": result.get("error")}}

    async def get_logs(self, args: dict, context: dict = None) -> dict:
        """Fetch logs from a pod, optionally for a specific container."""
        pod = args.get("pod")
        namespace = args.get("namespace", "default")
        if not pod:
            return {"status": "completed", "result": {"error": "pod name is required"}}

        cmd = ["logs", "-n", namespace, pod]
        container = args.get("container")
        if container:
            cmd.extend(["-c", container])
        tail = args.get("tail", 100)
        cmd.extend(["--tail", str(tail)])

        result = await asyncio.to_thread(_run_kubectl, cmd)
        if result["status"] == "success":
            return {"status": "completed", "result": {"pod": pod, "namespace": namespace, "logs": result.get("output", ""), "lines": tail}}
        return {"status": "completed", "result": {"pod": pod, "namespace": namespace, "logs": "", "error": result.get("error")}}

    async def get_events(self, args: dict, context: dict = None) -> dict:
        """List Kubernetes events in a namespace."""
        namespace = args.get("namespace", "default")
        cmd = ["get", "events", "-n", namespace, "-o", "json"]
        result = await asyncio.to_thread(_run_kubectl, cmd)
        if result["status"] == "success" and "data" in result:
            items = result["data"].get("items", [])
            events = []
            for e in items:
                meta = e.get("metadata", {})
                inn = e.get("involvedObject", {})
                events.append({
                    "type": e.get("type"),
                    "reason": e.get("reason"),
                    "message": e.get("message"),
                    "object": f"{inn.get('kind', '')}/{inn.get('name', '')}",
                    "count": e.get("count", 0),
                    "age": e.get("lastTimestamp", meta.get("creationTimestamp")),
                })
            return {"status": "completed", "result": {"events": events, "count": len(events), "namespace": namespace}}
        return {"status": "completed", "result": {"events": [], "count": 0, "namespace": namespace, "error": result.get("error")}}

    async def describe_resource(self, args: dict, context: dict = None) -> dict:
        """Describe a Kubernetes resource (pod, deployment, service, etc.)."""
        kind = args.get("kind", "pod")
        name = args.get("name")
        namespace = args.get("namespace", "default")
        if not name:
            return {"status": "completed", "result": {"error": "resource name is required"}}

        cmd = ["get", kind, name, "-n", namespace, "-o", "json"]
        result = await asyncio.to_thread(_run_kubectl, cmd)
        if result["status"] == "success" and "data" in result:
            return {"status": "completed", "result": {"kind": kind, "name": name, "namespace": namespace, "resource": result["data"]}}
        return {"status": "completed", "result": {"kind": kind, "name": name, "namespace": namespace, "error": result.get("error")}}

    async def rollout_status(self, args: dict, context: dict = None) -> dict:
        """Check the rollout status of a deployment."""
        name = args.get("name")
        namespace = args.get("namespace", "default")
        if not name:
            return {"status": "completed", "result": {"error": "deployment name is required"}}

        cmd = ["rollout", "status", f"deployment/{name}", "-n", namespace]
        result = await asyncio.to_thread(_run_kubectl, cmd)
        return {"status": "completed", "result": {
            "deployment": name,
            "namespace": namespace,
            "status": result.get("output", result.get("error", "unknown")),
            "error": result.get("error") if result["status"] == "error" else None,
        }}

    async def restart_deployment(self, args: dict, context: dict = None) -> dict:
        """Restart a deployment (rolling restart)."""
        name = args.get("name")
        namespace = args.get("namespace", "default")
        if not name:
            return {"status": "completed", "result": {"error": "deployment name is required"}}

        cmd = ["rollout", "restart", f"deployment/{name}", "-n", namespace]
        result = await asyncio.to_thread(_run_kubectl, cmd)
        return {"status": "completed", "result": {
            "deployment": name,
            "namespace": namespace,
            "action": "restart",
            "message": result.get("output", result.get("error", "restart initiated")),
            "error": result.get("error") if result["status"] == "error" else None,
        }}

    async def scale_deployment(self, args: dict, context: dict = None) -> dict:
        """Scale a deployment to a specific replica count."""
        name = args.get("name")
        namespace = args.get("namespace", "default")
        replicas = args.get("replicas")
        if not name:
            return {"status": "completed", "result": {"error": "deployment name is required"}}
        if replicas is None:
            return {"status": "completed", "result": {"error": "replicas count is required"}}

        cmd = ["scale", f"deployment/{name}", "-n", namespace, "--replicas", str(replicas)]
        result = await asyncio.to_thread(_run_kubectl, cmd)
        return {"status": "completed", "result": {
            "deployment": name,
            "namespace": namespace,
            "replicas": replicas,
            "action": "scale",
            "message": result.get("output", result.get("error", f"scaled to {replicas}")),
            "error": result.get("error") if result["status"] == "error" else None,
        }}

    async def rollback_deployment(self, args: dict, context: dict = None) -> dict:
        """Rollback a deployment to a previous revision."""
        name = args.get("name")
        namespace = args.get("namespace", "default")
        revision = args.get("revision")
        if not name:
            return {"status": "completed", "result": {"error": "deployment name is required"}}

        cmd = ["rollout", "undo", f"deployment/{name}", "-n", namespace]
        if revision:
            cmd.extend(["--to-revision", str(revision)])
        result = await asyncio.to_thread(_run_kubectl, cmd)
        return {"status": "completed", "result": {
            "deployment": name,
            "namespace": namespace,
            "revision": revision,
            "action": "rollback",
            "message": result.get("output", result.get("error", "rollback initiated")),
            "error": result.get("error") if result["status"] == "error" else None,
        }}


k8s_adapter = KubernetesMCP(registry)

# ---- Register tools ----

registry.register(
    "k8s_get_pods",
    "List pods in a Kubernetes namespace with optional label selector filtering",
    {
        "type": "object",
        "properties": {
            "namespace": {"type": "string", "default": "default", "description": "Kubernetes namespace"},
            "label_selector": {"type": "string", "description": "Label selector filter (e.g. app=backend)"},
        },
    },
    k8s_adapter.get_pods,
)

registry.register(
    "k8s_get_logs",
    "Fetch logs from a Kubernetes pod, optionally for a specific container and with tail limit",
    {
        "type": "object",
        "properties": {
            "pod": {"type": "string", "description": "Pod name"},
            "namespace": {"type": "string", "default": "default"},
            "container": {"type": "string", "description": "Container name (optional)"},
            "tail": {"type": "integer", "default": 100, "description": "Number of recent log lines"},
        },
        "required": ["pod"],
    },
    k8s_adapter.get_logs,
)

registry.register(
    "k8s_get_events",
    "List Kubernetes events in a namespace, including warnings and normal events",
    {
        "type": "object",
        "properties": {
            "namespace": {"type": "string", "default": "default", "description": "Kubernetes namespace"},
        },
    },
    k8s_adapter.get_events,
)

registry.register(
    "k8s_describe",
    "Describe a Kubernetes resource (pod, deployment, service, node, etc.) in detail",
    {
        "type": "object",
        "properties": {
            "kind": {"type": "string", "default": "pod", "description": "Resource kind (pod, deployment, service, node, etc.)"},
            "name": {"type": "string", "description": "Resource name"},
            "namespace": {"type": "string", "default": "default"},
        },
        "required": ["name"],
    },
    k8s_adapter.describe_resource,
)

registry.register(
    "k8s_rollout_status",
    "Check the rollout status of a Kubernetes deployment",
    {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Deployment name"},
            "namespace": {"type": "string", "default": "default"},
        },
        "required": ["name"],
    },
    k8s_adapter.rollout_status,
)

registry.register(
    "k8s_restart",
    "Trigger a rolling restart of a Kubernetes deployment",
    {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Deployment name"},
            "namespace": {"type": "string", "default": "default"},
        },
        "required": ["name"],
    },
    k8s_adapter.restart_deployment,
)

registry.register(
    "k8s_scale",
    "Scale a Kubernetes deployment to a specific number of replicas",
    {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Deployment name"},
            "namespace": {"type": "string", "default": "default"},
            "replicas": {"type": "integer", "description": "Target replica count"},
        },
        "required": ["name", "replicas"],
    },
    k8s_adapter.scale_deployment,
)

registry.register(
    "k8s_rollback",
    "Rollback a Kubernetes deployment to a previous revision",
    {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Deployment name"},
            "namespace": {"type": "string", "default": "default"},
            "revision": {"type": "integer", "description": "Target revision number (optional; defaults to previous)"},
        },
        "required": ["name"],
    },
    k8s_adapter.rollback_deployment,
)


def get_k8s_mcp() -> KubernetesMCP:
    return k8s_adapter
