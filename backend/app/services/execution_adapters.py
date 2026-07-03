"""Generic adapter factories that normalize execution targets into the common callable signature.

Common signature: async (context: ProjectContext) -> AgentResult

All execution types (agents, MCP tools, REST calls, Python functions) are normalized
to this signature at registration time via adapter functions in this module.
"""

import logging
from typing import Any, Callable, Dict, Optional

from app.services.agent_base import AgentResult
from app.services.context_builder import ProjectContext
from app.mcp.registry import ToolRegistry

logger = logging.getLogger(__name__)


def adapt_agent(agent_fn: Callable) -> Callable:
    """Agent functions already match the common signature.

    This is a pass-through identity function for clarity and symmetry.
    Agent .process() methods already accept (context: ProjectContext) -> AgentResult.
    """
    return agent_fn


def adapt_mcp(tool_name: str, mcp_registry: ToolRegistry) -> Callable:
    """Wrap an MCP tool into the common agent-callable signature.

    The returned callable reads parameters from context.step_input and
    dispatches to the MCP tool via ToolRegistry.execute().
    """
    async def wrapped(context: ProjectContext) -> AgentResult:
        args = context.step_input or {}
        try:
            result = await mcp_registry.execute(tool_name, args, {})
            status = result.get("status", "completed") if isinstance(result, dict) else "completed"
            return AgentResult(
                result=str(result.get("result", result.get("output", str(result)))),
                confidence=0.9,
                recommendations=[],
                follow_up_actions=[],
                details=result if isinstance(result, dict) else {"output": str(result)},
            )
        except Exception as e:
            logger.warning("MCP tool '%s' failed: %s", tool_name, str(e))
            return AgentResult(
                result=f"MCP tool '{tool_name}' error: {str(e)}",
                confidence=0.0,
                recommendations=[],
                follow_up_actions=[],
                details={"error": str(e), "tool": tool_name},
            )

    return wrapped


def adapt_rest(url: str = "", method: str = "GET") -> Callable:
    """Wrap a REST call into the common signature.

    Parameters come from context.step_input (body, headers, path params).
    Currently a stub — no real HTTP calls are made.
    """
    async def wrapped(context: ProjectContext) -> AgentResult:
        step_args = context.step_input or {}
        effective_url = step_args.get("url", url)
        effective_method = step_args.get("method", method)
        return AgentResult(
            result=f"[REST stub] {effective_method} {effective_url} — not implemented",
            confidence=0.0,
            recommendations=[],
            follow_up_actions=[],
            details={"url": effective_url, "method": effective_method, "status": "stub"},
        )

    return wrapped


def adapt_python(fn: Optional[Callable] = None) -> Callable:
    """Wrap a Python function into the common signature.

    If fn is provided, it is called with context.step_input as kwargs.
    If fn is None, the adapter returns a stub message.
    Currently limited — no sandboxing or dynamic code execution.
    """
    async def wrapped(context: ProjectContext) -> AgentResult:
        if fn is not None:
            try:
                step_args = context.step_input or {}
                result = await fn(**step_args) if fn else None
                return AgentResult(
                    result=str(result) if result else "[Python] completed",
                    confidence=0.9,
                    recommendations=[],
                    follow_up_actions=[],
                    details={"output": str(result)},
                )
            except Exception as e:
                logger.warning("Python adapter execution failed: %s", str(e))
                return AgentResult(
                    result=f"[Python] error: {str(e)}",
                    confidence=0.0,
                    recommendations=[],
                    follow_up_actions=[],
                    details={"error": str(e)},
                )
        return AgentResult(
            result="[Python stub] Python execution not configured",
            confidence=0.0,
            recommendations=[],
            follow_up_actions=[],
            details={"status": "stub"},
        )

    return wrapped
